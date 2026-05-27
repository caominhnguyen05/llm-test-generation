import time
from pathlib import Path
from shutil import rmtree

from library_prep.prep_library import prepare_library
from pipeline.config import PipelineConfig
from pipeline.failures import record_compile_failure, write_compile_failure_summary
from pipeline.files import (
    delete_generated_test,
    save_test_code,
)
from pipeline.generation import generate_initial_test, generate_repair_test
from pipeline.metrics import (
    LibraryRuntimeMetrics,
    append_library_coverage,
    append_library_runtime_metrics,
    append_zero_coverage_row,
)
from pipeline.preprocess import extract_package_and_class, find_testable_sources, read_java_source
from pipeline.validation import ValidationResult, validate_compile, validate_structure, validate_test


def process_one_source(
    config: PipelineConfig,
    source: Path,
    metrics: LibraryRuntimeMetrics,
) -> str:
    source_file = config.source_folder / source
    source_code = read_java_source(source_file)
    package_name, class_name = extract_package_and_class(source_file, config.source_folder)

    test_class = f"{class_name}Test"
    test_file = config.test_folder / package_name.replace(".", "/") / f"{test_class}.java"

    print(f"  Library: {config.library}")

    test_code = generate_initial_test(source_code, package_name, class_name, config.llm_backend, metrics)
    structure_result = validate_structure(test_code, class_name)
    if not structure_result.passed:
        return handle_structure_failure(config, source, test_file, test_class, structure_result.message)

    save_test_code(test_file, test_code, "Initial")

    for attempt in range(config.attempts + 1):
        print(f"\nValidating {test_class} on attempt {attempt}/{config.attempts}...")
        result = validate_test(config, test_class)

        if result.passed:
            print(f"SUCCESS: {test_class} - all tests passed on attempt {attempt}.")
            return "success"

        if attempt == config.attempts:
            return handle_validation_failure(config, source, test_file, test_class, result)

        print(f"{result.stage.title()} validation failed for {test_class}.")
        print(f"Error: {result.message}")
        print(f"Starting repair loop {attempt + 1}/{config.attempts}...")

        test_code = generate_repair_test(
            test_code,
            result,
            source_code,
            package_name,
            class_name,
            config.llm_backend,
            metrics,
        )
        structure_result = validate_structure(test_code, class_name)
        if not structure_result.passed:
            return handle_structure_failure(config, source, test_file, test_class, structure_result.message)

        save_test_code(test_file, test_code, "Repaired")

    return "validation failed"


def handle_structure_failure(
    config: PipelineConfig,
    source: Path,
    test_file: Path,
    test_class: str,
    message: str,
) -> str:
    print(f"Structure validation failed for {test_class}: {message}")

    record_compile_failure(
        config,
        source,
        test_class,
        ValidationResult(False, "structure", message),
    )

    if test_file.exists():
        compile_result = validate_compile(config, test_class)
        if not compile_result.passed:
            delete_generated_test(test_file, "structure validation failed and saved test no longer compiles")
        else:
            print(f"Keeping previously generated compiling test after structure failure: {test_file}")

    return "structure validation failed"


def handle_validation_failure(
    config: PipelineConfig,
    source: Path,
    test_file: Path,
    test_class: str,
    result: ValidationResult,
) -> str:
    print(f"FAILURE: max repair attempts ({config.attempts}) reached.")
    print(f"Validation failed for {test_class}: {result.message}")

    if result.stage in {"compile", "structure"}:
        record_compile_failure(config, source, test_class, result)
        delete_generated_test(test_file, f"{result.stage} validation failed")
    else:
        print(f"Keeping generated test file with assertion/runtime errors: {test_file}")

    return f"{result.stage} validation failed after max repair attempts"


def run_library_pipeline(config: PipelineConfig) -> None:
    if not config.library_path.exists():
        print(f"Library folder does not exist, preparing {config.library}: {config.library_path}")
        if not prepare_library(config):
            print(f"Skipping {config.library}: library preparation failed.")
            return

    # Remove old generated tests before writing new ones
    test_root = config.library_path / "src/test"
    if test_root.exists():
        rmtree(test_root)
        print(f"Removed existing test folder: {test_root}")

    started_at = time.monotonic() # Start timer for calculating pipeline runtime
    metrics = LibraryRuntimeMetrics()

    # 1. Identify testable classes in the library
    testable_sources = find_testable_sources(config)
    if not testable_sources:
        print(f"Skipping {config.library}: no testable Java source files found in {config.source_folder}")
        return

    print(f"Found {len(testable_sources)} testable Java source files in {config.library}.")
    failures = []

    # 2. Generate, validate, and repair tests for each testable source file
    for index, source in enumerate(testable_sources, start=1):
        print(f"\n=== [{index}/{len(testable_sources)}] {source} ===")
        try:
            result = process_one_source(config, source, metrics)
            if result != "success":
                failures.append((source, result))
        except Exception as exc:
            failures.append((source, str(exc)))
            print(f"ERROR: failed while processing {source}.")
            print(exc)

    if failures:
        print(f"\nCompleted with {len(failures)} failed source file(s):")
        for source, result in failures:
            print(f"- {source}: {result}")
    else:
        print("\nCompleted successfully with no failed source files.")

    num_generated_tests = sum(1 for _ in config.test_folder.rglob("*.java")) if config.test_folder.exists() else 0

    # 3. Record coverage
    if num_generated_tests == 0:
        append_zero_coverage_row(config, len(testable_sources))
    else:
        append_library_coverage(config, len(testable_sources), num_generated_tests)

    # 4. Write compile failure summary and runtime metrics
    write_compile_failure_summary(config)

    metrics.total_pipeline_runtime_seconds = time.monotonic() - started_at
    append_library_runtime_metrics(config, len(testable_sources), metrics)