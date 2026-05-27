import time
from pathlib import Path
from shutil import rmtree

from library_prep.prep_library import prepare_library
from pipeline.config import PipelineConfig
from pipeline.failures import record_compile_failure, write_compile_failure_summary
from pipeline.files import (
    delete_test,
    save_test,
    count_generated_tests,
)
from pipeline.generation import generate_initial_test, generate_repair_test
from pipeline.metrics import (
    CostMetrics,
    append_library_coverage,
    append_library_runtime_metrics,
)
from pipeline.preprocess import extract_package_and_class, find_testable_sources, read_java_source
from pipeline.validation import validate_compile, validate_structure, validate_test


def process_one_source(
    config: PipelineConfig,
    source: Path,
    metrics: CostMetrics,
) -> str:
    source_file = config.source_folder / source
    source_code = read_java_source(source_file)
    package_name, class_name = extract_package_and_class(source_file, config.source_folder)

    test_class = f"{class_name}Test"
    test_file = config.test_folder / package_name.replace(".", "/") / f"{test_class}.java"

    test_code = generate_initial_test(
        source_code, package_name, class_name, config.llm_backend, metrics
    )

    for attempt in range(config.attempts + 1):
        structure_result = validate_structure(test_code, test_class)
        if not structure_result.passed:
            print(f"Structure check failed for {test_class}: {structure_result.message}")
            record_compile_failure(config, source, structure_result)

            if test_file.exists():
                compile_result = validate_compile(config, test_class)
                if not compile_result.passed:
                    delete_test(test_file, "structure validation failed and saved test does not compile")

            return "structure check failed"

        save_test(test_file, test_code)
        result = validate_test(config, test_class)

        if result.passed:
            print(f"SUCCESS: {test_class} - all tests passed after {attempt} repair attempt(s).")
            return "success"

        if attempt == config.attempts:
            print(f"FAILURE: max repair attempts ({config.attempts}) reached.")

            if result.stage == "compile":
                record_compile_failure(config, source, result)
                delete_test(test_file, "compile validation failed")
            else:
                print(f"Keeping generated test file with assertion/runtime errors: {test_file}")

            return f"{result.stage} validation failed after max repair attempts"

        print(f"{result.stage.title()} validation failed for {test_class}.")
        print(f"Error: {result.message}")
        print(f"Repair attempt {attempt + 1}/{config.attempts}...")

        test_code = generate_repair_test(
            test_code,
            result.message,
            source_code,
            package_name,
            class_name,
            config.llm_backend,
            metrics,
        )

def print_failure_summary(failures: list[tuple[Path, str]]) -> None:
    print(f"\nCompleted with {len(failures)} failed source file(s).")
    for source, result in failures:
        print(f"- {source}: {result}")


def run_library_pipeline(config: PipelineConfig) -> None:
    """Run the LLM test generation pipeline for one library."""
    # 1. Download and construct library 
    if not prepare_library(config):
        print(f"Skipping {config.library}: library preparation failed.")
        return

    # Remove old generated tests before writing new ones
    test_root = config.library_path / "src/test"
    if test_root.exists():
        rmtree(test_root)

    started_at = time.monotonic() # Start timer for calculating pipeline runtime
    metrics = CostMetrics()

    # 2. Identify testable classes in the library
    testable_sources = find_testable_sources(config)
    num_testable = len(testable_sources)
    if num_testable == 0:
        print(f"\nSkipping {config.library}: no testable Java source files found in {config.source_folder}")
        return

    print(f"\nFound {num_testable} testable Java source files in {config.library}.")
    failures = []

    # 3. Generate, validate, and repair tests for each testable source file
    for index, source in enumerate(testable_sources, start=1):
        print(f"\n=== [{index}/{num_testable}] {source} ===")
        try:
            result = process_one_source(config, source, metrics)
            if result != "success":
                failures.append((source, result))
        except Exception as exc:
            failures.append((source, str(exc)))
            print(f"ERROR: failed while processing {source}.")
            print(exc)

    print_failure_summary(failures)

    num_generated_tests = count_generated_tests(config)

    # 3. Record coverage
    append_library_coverage(config, num_testable, num_generated_tests)

    # 4. Write compile failure summary and runtime metrics
    write_compile_failure_summary(config)

    metrics.total_pipeline_runtime_seconds = time.monotonic() - started_at
    append_library_runtime_metrics(config, num_testable, metrics)