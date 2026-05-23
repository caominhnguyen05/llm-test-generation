import time
from dataclasses import dataclass
from pathlib import Path

from pipeline_config import PipelineConfig
from pipeline_failures import record_compile_failure, write_compile_failure_summary
from pipeline_files import count_generated_test_classes, delete_generated_test, delete_generated_test_for_source, save_test_code
from pipeline_generation import generate_initial_test, generate_repair_test, validate_test
from pipeline_metrics import (
    LibraryRuntimeMetrics,
    append_library_coverage,
    append_library_runtime_metrics,
    append_zero_library_coverage,
)
from preprocess import check_testability, extract_package_and_class, read_source_file
from validation import ValidationResult


@dataclass(frozen=True)
class PipelineResult:
    succeeded: bool
    message: str = ""

    def __bool__(self) -> bool:
        return self.succeeded


def find_testable_sources(config: PipelineConfig) -> list[Path]:
    """Return Java source files in a library that are likely worth testing."""
    if not config.source_root.exists():
        print(f"Error: source root not found: {config.source_root}")
        return []

    selected_sources: list[Path] = []
    skipped_sources: list[tuple[Path, str]] = []
    for path in sorted(config.source_root.rglob("*.java")):
        decision = check_testability(path, config.source_root)
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


def run_pipeline(
    config: PipelineConfig,
    source: Path,
    metrics: LibraryRuntimeMetrics | None = None,
) -> PipelineResult:
    """Generate, save, validate, and repair a test for one Java source file."""
    if not config.library_path.exists():
        print(f"Error: library folder not found: {config.library_path}")
        return PipelineResult(False, "library folder not found")

    target_java_file = config.source_root / source
    source_code = read_source_file(target_java_file)
    package_name, class_name = extract_package_and_class(target_java_file, config.source_root)
    test_class = f"{class_name}Test"
    output_test_file = config.test_root / package_name.replace(".", "/") / f"{test_class}.java"

    print_pipeline_target(config, target_java_file, package_name, class_name, output_test_file)

    test_code = generate_initial_test(source_code, package_name, class_name, metrics)
    save_test_code(output_test_file, test_code, "Initial")

    for attempt in range(config.attempts + 1):
        print(f"\nValidating {test_class} on attempt {attempt}/{config.attempts}...")
        validation_result = validate_test(test_code, test_class)

        if validation_result.passed:
            print(f"SUCCESS: {test_class} - all tests passed on attempt {attempt}.")
            return PipelineResult(True)

        if attempt >= config.attempts:
            return handle_final_validation_failure(
                config,
                source,
                output_test_file,
                test_class,
                validation_result.stage,
                validation_result.message,
            )

        print(f"{validation_result.stage.title()} validation failed for {test_class}.")
        print(f"Error: {validation_result.message}")
        print(f"Starting repair loop {attempt + 1}/{config.attempts}...")

        test_code = generate_repair_test(
            test_code,
            validation_result,
            source_code,
            package_name,
            class_name,
            metrics,
        )
        save_test_code(output_test_file, test_code, "Repaired")

    return PipelineResult(False, "validation failed")


def run_library_pipeline(config: PipelineConfig) -> None:
    """Run the test-generation pipeline for every Java source file in a library."""
    pipeline_started_at = time.monotonic()
    metrics = LibraryRuntimeMetrics()
    testable_sources = find_testable_sources(config)

    if not testable_sources:
        print(f"No Java source files found under {config.source_root}")
        finish_library_run(config, 0, metrics, pipeline_started_at)
        return

    failures = process_sources(config, testable_sources, metrics)
    print_library_summary(failures)

    generated_test_classes = count_generated_test_classes(config, testable_sources)
    if generated_test_classes == 0:
        print("\nNo generated test classes survived. Writing zero coverage row.")
        append_zero_library_coverage(config, len(testable_sources))
        finish_library_run(config, len(testable_sources), metrics, pipeline_started_at)
        return

    append_library_coverage(config, len(testable_sources), generated_test_classes)
    finish_library_run(config, len(testable_sources), metrics, pipeline_started_at)


def process_sources(
    config: PipelineConfig,
    sources: list[Path],
    metrics: LibraryRuntimeMetrics,
) -> list[tuple[Path, str]]:
    failures: list[tuple[Path, str]] = []
    print(f"Found {len(sources)} testable Java source files in {config.library}.")

    for index, source in enumerate(sources, start=1):
        print(f"\n=== [{index}/{len(sources)}] {source} ===")
        try:
            result = run_pipeline(config, source, metrics)
            if not result.succeeded:
                failures.append((source, result.message))
        except Exception as exc:
            failures.append((source, str(exc)))
            print(f"ERROR: failed while processing {source}.")
            print(exc)
            delete_generated_test_for_source(config, source, f"pipeline exception: {exc}")

    return failures


def print_pipeline_target(
    config: PipelineConfig,
    target_java_file: Path,
    package_name: str,
    class_name: str,
    output_test_file: Path,
) -> None:
    print(f"  Library: {config.library}")
    print(f"  Source: {target_java_file}")
    print(f"  Package: {package_name}")
    print(f"  Class: {class_name}")
    print(f"  Output: {output_test_file}")


def handle_final_validation_failure(
    config: PipelineConfig,
    source: Path,
    output_test_file: Path,
    test_class: str,
    stage: str,
    message: str,
) -> PipelineResult:
    print(f"FAILURE: max repair attempts ({config.attempts}) reached.")
    print(f"Validation failed for {test_class}: {message}")

    if stage in {"compile", "structure"}:
        if config.record_failures:
            record_compile_failure(config, source, test_class, ValidationResult(False, stage, message))
        delete_generated_test(output_test_file, f"{stage} validation failed")
    else:
        print(f"Keeping generated test file with assertion/runtime errors: {output_test_file}")

    return PipelineResult(False, f"{stage} validation failed after max repair attempts")


def print_library_summary(failures: list[tuple[Path, str]]) -> None:
    if failures:
        print(f"\nCompleted with {len(failures)} failed source file(s):")
        for source, message in failures:
            print(f"- {source}: {message}")
    else:
        print("\nCompleted successfully with no failed source files.")


def finish_library_run(
    config: PipelineConfig,
    total_sources: int,
    metrics: LibraryRuntimeMetrics,
    pipeline_started_at: float,
) -> None:
    if config.record_failures:
        write_compile_failure_summary()
    metrics.total_pipeline_runtime_seconds = time.monotonic() - pipeline_started_at
    append_library_runtime_metrics(config, total_sources, metrics)