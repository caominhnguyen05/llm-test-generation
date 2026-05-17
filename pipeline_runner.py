import csv
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path

from llm.main import LLMCallMetrics, generate_llm_response, get_generation_prompt, get_repair_prompt
from pipeline_config import PipelineConfig
from postprocess import normalize_test_code, write_file
from preprocess import assess_source_testability, extract_package_and_class, read_source_file
from validation import ValidationResult, validate_compile, validate_runtime, validate_structure
from coverage.run_coverage import append_row, read_coverage, read_maven_project, run_pruned_jacoco

REPO_ROOT = Path(__file__).resolve().parent
COVERAGE_DIR = REPO_ROOT / "coverage"
if str(COVERAGE_DIR) not in sys.path:
    sys.path.insert(0, str(COVERAGE_DIR))

LLM_COVERAGE_CSV = REPO_ROOT / "results/llm_coverage_final.csv"
LLM_RUNTIME_CSV = REPO_ROOT / "results/llm_runtime_final.csv"
COMPILE_FAILURES_CSV = REPO_ROOT / "results/llm_compile_failures.csv"
COMPILE_FAILURE_SUMMARY_CSV = REPO_ROOT / "results/llm_compile_failure_summary.csv"

LLM_RUNTIME_FIELDNAMES = [
    "group_id",
    "artifact_id",
    "version",
    "total_classes_under_test",
    "total_llm_calls",
    "initial_generation_calls",
    "repair_calls",
    "total_llm_generation_time_seconds",
    "average_llm_generation_time_per_class_seconds",
    "total_pipeline_runtime_seconds",
    "average_pipeline_runtime_per_class_seconds",
    "total_prompt_tokens",
    "total_output_tokens",
    "number_of_repair_attempts",
]
COMPILE_FAILURE_FIELDNAMES = [
    "library",
    "source_file",
    "test_class",
    "stage",
    "category",
    "message",
]
COMPILE_FAILURE_SUMMARY_FIELDNAMES = [
    "library",
    "category",
    "compile_failures",
    "percentage",
]
@dataclass(frozen=True)
class PipelineResult:
    succeeded: bool
    message: str = ""

    def __bool__(self) -> bool:
        return self.succeeded


@dataclass
class LibraryRuntimeMetrics:
    total_llm_calls: int = 0
    initial_generation_calls: int = 0
    repair_calls: int = 0
    total_llm_generation_time_ns: int = 0
    total_prompt_tokens: int = 0
    total_output_tokens: int = 0
    total_pipeline_runtime_seconds: float = 0.0

    def record_initial_call(self, metrics: LLMCallMetrics) -> None:
        self.initial_generation_calls += 1
        self._record_call(metrics)

    def record_repair_call(self, metrics: LLMCallMetrics) -> None:
        self.repair_calls += 1
        self._record_call(metrics)

    def _record_call(self, metrics: LLMCallMetrics) -> None:
        self.total_llm_calls += 1
        self.total_llm_generation_time_ns += metrics.total_duration_ns
        self.total_prompt_tokens += metrics.prompt_tokens
        self.total_output_tokens += metrics.output_tokens


def iter_library_sources(config: PipelineConfig) -> list[Path]:
    """Return Java source files in a library that are likely worth testing."""
    if not config.source_root.exists():
        print(f"❌ Error: source root not found: {config.source_root}")
        return []
    selected_sources: list[Path] = []
    skipped_sources: list[tuple[Path, str]] = []
    for path in sorted(config.source_root.rglob("*.java")):
        decision = assess_source_testability(path, config.source_root)
        relative_path = path.relative_to(config.source_root)
        if decision.testable:
            selected_sources.append(relative_path)
        else:
            skipped_sources.append((relative_path, decision.reason))

    if skipped_sources:
        print(f"Preprocessing skipped {len(skipped_sources)} likely non-testable source files:")
        for source, reason in skipped_sources:
            print(f"- {source}: {reason}")

    return selected_sources


def validate_inputs(config: PipelineConfig) -> bool:
    """Check that the selected library and source file exist before running."""
    if not config.library_path.exists():
        print(f"❌ Error: library folder not found: {config.library_path}")
        return False
    if not config.target_java_file.exists():
        print(f"❌ Error: source file not found: {config.target_java_file}")
        return False
    return True


def save_test_code(output_test_file: Path, test_code: str, class_name: str, label: str) -> None:
    """Save the generated test code to the library src/test/java folder, creating directories as needed."""
    structure_result = validate_structure(test_code, class_name)
    if not structure_result.passed:
        print(f"Quick structure warnings before Maven: {structure_result.message}")
    write_file(output_test_file, test_code)
    print(f"{label} test saved to {output_test_file}")


def generate_initial_test(
    config: PipelineConfig,
    source_code: str,
    package_name: str,
    class_name: str,
    metrics: LibraryRuntimeMetrics | None = None,
) -> str:
    """Ask the LLM to generate the first version of the JUnit test class.

    The raw LLM response is normalized so the result is a complete Java test
    file with the expected package and class name.
    """
    print(f"\n[Attempt 0] Asking Ollama ({config.model}) to generate tests...")
    llm_output, call_metrics = generate_llm_response(
        get_generation_prompt(source_code, package_name, class_name),
        config.model,
        return_metrics=True,
    )
    if metrics is not None:
        metrics.record_initial_call(call_metrics)
    return normalize_test_code(llm_output, package_name, class_name, source_code)


def generate_repair_test(
    config: PipelineConfig,
    test_code: str,
    validation_result: ValidationResult,
    source_code: str,
    package_name: str,
    class_name: str,
    metrics: LibraryRuntimeMetrics | None = None,
) -> str:
    """Ask the LLM to repair a generated test after validation fails.

    The repair prompt includes the current test, the source under test, and the
    validation error output so the model can fix structure, compile, or runtime
    execution problems.
    """
    print(f"Asking Ollama ({config.model}) to repair the test...")
    llm_output, call_metrics = generate_llm_response(
        get_repair_prompt(test_code, validation_result.message, source_code, package_name, class_name),
        config.model,
        return_metrics=True,
    )
    if metrics is not None:
        metrics.record_repair_call(call_metrics)
    return normalize_test_code(llm_output, package_name, class_name, source_code)


def validate_generated_test(config: PipelineConfig, test_code: str, test_class: str) -> ValidationResult:
    """Validate a generated test through structure, compile, and runtime checks.

    Validation stops at the first failing stage so the repair loop receives the
    most relevant error message. Runtime validation checks whether Maven can run
    the test class; depending on Maven settings, assertion failures may be kept.
    """
    structure_result = validate_structure(test_code, test_class.removesuffix("Test"))
    if not structure_result.passed:
        return structure_result

    compile_result = validate_compile(config, test_class)
    if not compile_result.passed:
        return compile_result

    runtime_result = validate_runtime(config, test_class)
    if not runtime_result.passed:
        return runtime_result

    return ValidationResult(True, "complete", runtime_result.message)


def run_pipeline(config: PipelineConfig, metrics: LibraryRuntimeMetrics | None = None) -> PipelineResult:
    """Generate, save, validate, and repair a test for one Java source file.

    The pipeline reads the target source file, asks the LLM for an initial test,
    writes it to src/test/java, validates it, and then runs repair attempts until
    the test is valid or the configured repair limit is reached.
    """
    if not validate_inputs(config):
        return PipelineResult(False, "invalid input")

    testability = assess_source_testability(config.target_java_file, config.source_root)
    if not testability.testable:
        print(f"Skipping {config.target_java_file}: {testability.reason}.")
        return PipelineResult(True, f"skipped: {testability.reason}")

    source_code = read_source_file(config.target_java_file)
    package_name, class_name = extract_package_and_class(config.target_java_file, config.source_root)
    test_class = f"{class_name}Test"
    output_test_file = config.test_root / package_name.replace(".", "/") / f"{test_class}.java"

    print(f"  Library: {config.library}")
    print(f"  Source: {config.target_java_file}")
    print(f"  Package: {package_name}")
    print(f"  Class: {class_name}")
    print(f"  Output: {output_test_file}")

    test_code = generate_initial_test(config, source_code, package_name, class_name, metrics)
    save_test_code(output_test_file, test_code, class_name, "Initial")

    for attempt in range(config.attempts + 1):
        print(f"\nValidating {test_class} on attempt {attempt}/{config.attempts}...")
        validation_result = validate_generated_test(config, test_code, test_class)

        if validation_result.passed:
            print(f"✅ SUCCESS: {test_class} - all tests passed on attempt {attempt}.")
            return PipelineResult(True)

        if attempt >= config.attempts:
            print(f"❌ FAILURE: max repair attempts ({config.attempts}) reached.")
            print(f"❌ Validation failed for {test_class}: {validation_result.message}")
            if validation_result.stage in {"compile", "structure"}:
                record_compile_failure(config, test_class, validation_result)
                delete_generated_test(output_test_file, f"{validation_result.stage} validation failed")
            else:
                print(f"Keeping generated test file with assertion/runtime errors: {output_test_file}")

            return PipelineResult(False, f"{validation_result.stage} validation failed after max repair attempts")


        print(f"❌ {validation_result.stage.title()} validation failed for {test_class}.")
        print(f"Error: {validation_result.message}")
        print(f"Starting repair loop {attempt + 1}/{config.attempts}...")

        test_code = generate_repair_test(
            config,
            test_code,
            validation_result,
            source_code,
            package_name,
            class_name,
            metrics,
        )
        save_test_code(output_test_file, test_code, class_name, "Repaired")

    return PipelineResult(False, "validation failed")


def run_library_pipeline(config: PipelineConfig) -> None:
    """Run the test-generation pipeline for every Java source file in a library.

    If one test class fails to compile or run, the error is logged and the pipeline
    continues with the next source file.
    """
    pipeline_started_at = time.monotonic()
    metrics = LibraryRuntimeMetrics()
    sources = iter_library_sources(config)
    if not sources:
        print(f"No Java source files found under {config.source_root}")
        metrics.total_pipeline_runtime_seconds = time.monotonic() - pipeline_started_at
        append_library_runtime_metrics(config, 0, metrics)
        return

    failures: list[tuple[Path, str]] = []
    print(f"Found {len(sources)} testable Java source files in {config.library}.")

    for index, source in enumerate(sources, start=1):
        print(f"\n=== [{index}/{len(sources)}] {source} ===")
        try:
            result = run_pipeline(replace(config, source=source), metrics)
            if not result.succeeded:
                failures.append((source, result.message))
        except Exception as exc:
            failures.append((source, str(exc)))
            print(f"ERROR: failed while processing {source}.")
            print(exc)
            print("Keeping any generated test file and continuing with the next class.")

    if failures:
        print(f"\nCompleted with {len(failures)} failed source file(s):")
        for source, message in failures:
            print(f"❌ {source}: {message}")
    else:
        print("\nCompleted successfully with no failed source files.")

    generated_test_classes = count_generated_test_classes(config, sources)
    if generated_test_classes == 0:
        print("\nSkipping JaCoCo coverage because no generated test classes survived.")
        write_compile_failure_summary()
        metrics.total_pipeline_runtime_seconds = time.monotonic() - pipeline_started_at
        append_library_runtime_metrics(config, len(sources), metrics)
        return

    append_library_coverage(config, len(sources), generated_test_classes)
    write_compile_failure_summary()
    metrics.total_pipeline_runtime_seconds = time.monotonic() - pipeline_started_at
    append_library_runtime_metrics(config, len(sources), metrics)


def append_library_coverage(config: PipelineConfig, testable_source_files: int, generated_test_classes: int) -> None:
    """Run JaCoCo once for the completed library and append its coverage row."""
    print(f"\nRunning JaCoCo coverage for completed library: {config.library}")
    project = read_maven_project(config.library_path)
    _, maven_output, prune_result = run_pruned_jacoco(project.path, 300)
    append_row(
        read_coverage(
            project,
            maven_output,
            testable_source_files=testable_source_files,
            generated_test_classes=generated_test_classes,
            test_counts=prune_result.test_counts,
        ),
        LLM_COVERAGE_CSV,
    )
    print(f"Coverage row written to {LLM_COVERAGE_CSV}")


def append_library_runtime_metrics(
    config: PipelineConfig,
    total_classes_under_test: int,
    metrics: LibraryRuntimeMetrics,
) -> None:
    """Append one per-library runtime and LLM usage row."""
    project = read_maven_project(config.library_path)
    total_llm_seconds = metrics.total_llm_generation_time_ns / 1_000_000_000
    total_pipeline_seconds = metrics.total_pipeline_runtime_seconds
    row = {
        "group_id": project.group_id,
        "artifact_id": project.artifact_id,
        "version": project.version,
        "total_classes_under_test": str(total_classes_under_test),
        "total_llm_calls": str(metrics.total_llm_calls),
        "initial_generation_calls": str(metrics.initial_generation_calls),
        "repair_calls": str(metrics.repair_calls),
        "total_llm_generation_time_seconds": f"{total_llm_seconds:.4f}",
        "average_llm_generation_time_per_class_seconds": _average_seconds(total_llm_seconds, total_classes_under_test),
        "total_pipeline_runtime_seconds": f"{total_pipeline_seconds:.4f}",
        "average_pipeline_runtime_per_class_seconds": _average_seconds(total_pipeline_seconds, total_classes_under_test),
        "total_prompt_tokens": str(metrics.total_prompt_tokens),
        "total_output_tokens": str(metrics.total_output_tokens),
        "number_of_repair_attempts": str(config.attempts),
    }
    append_csv_row(LLM_RUNTIME_CSV, LLM_RUNTIME_FIELDNAMES, row)
    print(f"Runtime metrics row written to {LLM_RUNTIME_CSV}")


def count_generated_test_classes(config: PipelineConfig, sources: list[Path]) -> int:
    """Count surviving generated tests for the sources processed in this run."""
    generated_count = 0
    for source in sources:
        source_file = config.source_root / source
        package_name, class_name = extract_package_and_class(source_file, config.source_root)
        test_class = f"{class_name}Test"
        test_file = config.test_root / package_name.replace(".", "/") / f"{test_class}.java"
        if test_file.exists():
            generated_count += 1
    return generated_count


def categorize_compile_error(message: str, stage: str = "compile") -> str:
    """Return a coarse regex-based category for a Maven compile error."""
    if stage == "structure":
        return "structure_error"

    normalized = message.lower()
    patterns = [
        ("junit_version_mismatch", r"org\.junit\.jupiter|jupiter.*does not exist|package org\.junit\.jupiter does not exist"),
        ("missing_import", r"package .+ does not exist|import .+ cannot be resolved"),
        ("method_signature_mismatch", r"method .+ cannot be applied|no suitable method|actual and formal argument lists differ"),
        ("cannot_find_symbol", r"cannot find symbol|symbol:\s*(class|method|variable)"),
        ("constructor_mismatch", r"constructor .+ cannot be applied|no suitable constructor"),
        ("access_modifier_error", r"has private access|has protected access|is not public in|cannot be accessed from outside package"),
        (
            "abstract_class_or_interface_instantiation",
            r"is abstract; cannot be instantiated|is abstract and cannot be instantiated|is an interface; cannot be instantiated",
        ),
        ("unchecked_exception_not_handled", r"unreported exception|must be caught or declared to be thrown"),
        ("generic_type_mismatch", r"incompatible types|inference variable|type argument|cannot infer type"),
        ("dependency_missing", r"could not resolve dependencies|dependency .+ not found|package .+ does not exist"),
        ("syntax_error", r"';' expected|illegal start of|reached end of file while parsing|not a statement|class, interface, enum, or record expected"),
    ]
    for category, pattern in patterns:
        if re.search(pattern, normalized, re.DOTALL):
            return category
    return "other_compile_error"


def record_compile_failure(config: PipelineConfig, test_class: str, validation_result: ValidationResult) -> None:
    """Append one compile/structure failure row before deleting the generated test."""
    category = categorize_compile_error(validation_result.message, validation_result.stage)
    row = {
        "library": config.library,
        "source_file": str(config.source),
        "test_class": test_class,
        "stage": validation_result.stage,
        "category": category,
        "message": compact_csv_message(validation_result.message),
    }
    append_csv_row(COMPILE_FAILURES_CSV, COMPILE_FAILURE_FIELDNAMES, row)
    print(f"Recorded {validation_result.stage} failure category for {test_class}: {category}")


def write_compile_failure_summary() -> None:
    """Write category counts and percentages from the compile failure detail CSV."""
    if not COMPILE_FAILURES_CSV.exists():
        return

    library_counts: dict[str, Counter[str]] = {}
    with open(COMPILE_FAILURES_CSV, "r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            library = row.get("library", "")
            if not library:
                continue
            category = row.get("category", "other_compile_error")
            library_counts.setdefault(library, Counter())[category] += 1

    if not library_counts:
        return

    COMPILE_FAILURE_SUMMARY_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(COMPILE_FAILURE_SUMMARY_CSV, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=COMPILE_FAILURE_SUMMARY_FIELDNAMES)
        writer.writeheader()
        for library, category_counts in sorted(library_counts.items()):
            total_failures = sum(category_counts.values())
            for category, count in sorted(category_counts.items()):
                writer.writerow(
                    {
                        "library": library,
                        "category": category,
                        "compile_failures": str(count),
                        "percentage": f"{(count / total_failures) * 100:.2f}",
                    }
                )
    print(f"Compile failure summary written to {COMPILE_FAILURE_SUMMARY_CSV}")


def append_csv_row(output_path: Path, fieldnames: list[str], row: dict[str, str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    should_write_header = not output_path.exists() or output_path.stat().st_size == 0
    with open(output_path, "a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if should_write_header:
            writer.writeheader()
        writer.writerow(row)


def compact_csv_message(message: str) -> str:
    return re.sub(r"\s+", " ", message).strip()[-1000:]


def _average_seconds(total_seconds: float, count: int) -> str:
    if count == 0:
        return ""
    return f"{total_seconds / count:.4f}"


def delete_generated_test(output_test_file: Path, reason: str) -> None:
    """Delete a generated test file that would break later Maven/JaCoCo runs."""
    if output_test_file.exists():
        output_test_file.unlink()
        print(f"Deleted generated test: {output_test_file}")
        print(f"   Reason: {reason}")
