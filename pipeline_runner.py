import time
from pathlib import Path
from shutil import rmtree

from pipeline_config import PipelineConfig
from pipeline_failures import record_compile_failure, write_compile_failure_summary
from pipeline_files import (
    count_generated_test_classes,
    delete_generated_test,
    save_test_code,
)
from pipeline_generation import generate_initial_test, generate_repair_test, validate_test
from pipeline_metrics import (
    LibraryRuntimeMetrics,
    append_library_coverage,
    append_library_runtime_metrics,
    append_zero_coverage_row,
)
from preprocess import check_testability, extract_package_and_class, read_java_source
from validation import ValidationResult


def find_testable_sources(config: PipelineConfig) -> list[Path]:
    if not config.source_folder.exists():
        print(f"Error: source folder not found: {config.source_folder}")
        return []

    sources = []
    skipped = []

    for path in sorted(config.source_folder.rglob("*.java")):
        decision = check_testability(path, config.source_folder)
        relative_path = path.relative_to(config.source_folder)

        if decision.testable:
            sources.append(relative_path)
        else:
            skipped.append((relative_path, decision.reason))

    if skipped:
        print(f"Preprocessing skipped {len(skipped)} likely non-testable source files:")
        for source, reason in skipped:
            print(f"- {source}: {reason}")

    return sources


def process_one_source(
    config: PipelineConfig,
    source: Path,
    metrics: LibraryRuntimeMetrics,
) -> str | None:
    source_file = config.source_folder / source
    source_code = read_java_source(source_file)
    package_name, class_name = extract_package_and_class(source_file, config.source_folder)

    test_class = f"{class_name}Test"
    test_file = config.test_folder / package_name.replace(".", "/") / f"{test_class}.java"

    print(f"  Library: {config.library}")
    print(f"  Class: {class_name}")

    test_code = generate_initial_test(source_code, package_name, class_name, metrics)
    save_test_code(test_file, test_code, "Initial")

    for attempt in range(config.attempts + 1):
        print(f"\nValidating {test_class} on attempt {attempt}/{config.attempts}...")
        result = validate_test(config, test_code, test_class)

        if result.passed:
            print(f"SUCCESS: {test_class} - all tests passed on attempt {attempt}.")
            return None

        if attempt == config.attempts:
            return handle_validation_failure(
                config, source, test_file, test_class, result.stage, result.message
            )

        print(f"{result.stage.title()} validation failed for {test_class}.")
        print(f"Error: {result.message}")
        print(f"Starting repair loop {attempt + 1}/{config.attempts}...")

        test_code = generate_repair_test(
            test_code,
            result,
            source_code,
            package_name,
            class_name,
            metrics,
        )
        save_test_code(test_file, test_code, "Repaired")

    return "validation failed"


def handle_validation_failure(
    config: PipelineConfig,
    source: Path,
    test_file: Path,
    test_class: str,
    stage: str,
    message: str,
) -> str:
    print(f"FAILURE: max repair attempts ({config.attempts}) reached.")
    print(f"Validation failed for {test_class}: {message}")

    if stage in {"compile", "structure"}:
        if config.record_failures:
            record_compile_failure(
                config,
                source,
                test_class,
                ValidationResult(False, stage, message),
            )
        delete_generated_test(test_file, f"{stage} validation failed")
    else:
        print(f"Keeping generated test file with assertion/runtime errors: {test_file}")

    return f"{stage} validation failed after max repair attempts"


def run_library_pipeline(config: PipelineConfig) -> None:
    if not config.library_path.exists():
        print(f"Error: library folder not found: {config.library_path}")
        return

    test_root = config.library_path / "src/test"
    if test_root.exists():
        rmtree(test_root)
        print(f"Deleted existing test folder: {test_root}")

    started_at = time.monotonic()
    metrics = LibraryRuntimeMetrics()
    sources = find_testable_sources(config)

    if not sources:
        print(f"No testable Java source files found under {config.source_folder}")
        return

    failures = []
    print(f"Found {len(sources)} testable Java source files in {config.library}.")

    for index, source in enumerate(sources, start=1):
        print(f"\n=== [{index}/{len(sources)}] {source} ===")
        try:
            error = process_one_source(config, source, metrics)
            if error:
                failures.append((source, error))
        except Exception as exc:
            failures.append((source, str(exc)))
            print(f"ERROR: failed while processing {source}.")
            print(exc)

    if failures:
        print(f"\nCompleted with {len(failures)} failed source file(s):")
        for source, error in failures:
            print(f"- {source}: {error}")
    else:
        print("\nCompleted successfully with no failed source files.")

    generated_tests = count_generated_test_classes(config, sources)

    if generated_tests == 0:
        print("\nNo generated test classes survived. Writing zero coverage row.")
        append_zero_coverage_row(config, len(sources))
    else:
        append_library_coverage(config, len(sources), generated_tests)

    if config.record_failures:
        write_compile_failure_summary()

    metrics.total_pipeline_runtime_seconds = time.monotonic() - started_at
    append_library_runtime_metrics(config, len(sources), metrics)