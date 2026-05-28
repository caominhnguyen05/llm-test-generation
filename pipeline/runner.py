import time
from pathlib import Path
from shutil import rmtree

from library_prep.prep_library import prepare_library
from pipeline.config import LibConfig
from pipeline.experiment_logs import clear_library_logs, save_error
from pipeline.failures import record_compile_failure, write_compile_failure_summary
from pipeline.files import (
    delete_test,
    save_test,
    count_generated_tests,
)
from pipeline.generation import create_initial_test, create_repair_test
from pipeline.metrics import (
    CostMetrics,
    record_library_coverage,
    record_library_cost_metrics,
)
from pipeline.preprocess import extract_api_summary, extract_package_and_class, find_testable_sources, read_java_source
from pipeline.validation import validate_compile, validate_structure, validate_test


def process_one_source(config: LibConfig, source: Path, metrics: CostMetrics) -> str:
    source_file = config.source_folder / source
    source_code = read_java_source(source_file)
    package_name, class_name = extract_package_and_class(source_file, config.source_folder)

    api_summary = extract_api_summary(
        java_file=source_file,
        class_name=class_name,
    )

    test_class = f"{class_name}Test"
    test_file = config.test_folder / package_name.replace(".", "/") / f"{test_class}.java"

    test_code = create_initial_test(
        config, source_code, package_name, class_name, api_summary, metrics
    )

    for attempt in range(config.attempts + 1):
        phase = f"attempt_{attempt}"
        structure_result = validate_structure(test_code, test_class)
        if not structure_result.passed:
            save_error(config, class_name, package_name, phase, structure_result.message)

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

        save_error(config, class_name, package_name, phase, result.message)

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

        test_code = create_repair_test(
            config,
            test_code,
            result.message,
            source_code,
            package_name,
            class_name,
            api_summary,
            metrics,
            attempt + 1,
        )

def print_failure_summary(failures: list[tuple[Path, str]]) -> None:
    print(f"\nCompleted with {len(failures)} failed source file(s).")
    for source, result in failures:
        print(f"- {source}: {result}")

def setup_library(config: LibConfig) -> bool:
    if not prepare_library(config):
        print(f"Skipping {config.library}: library preparation failed.")
        return False
    
    clear_library_logs(config)
    test_root = config.library_path / "src/test"
    if test_root.exists():
        rmtree(test_root)
    
    return True

def run_library_pipeline(config: LibConfig) -> None:
    """Run the LLM test generation pipeline for one library."""
    # 1. Download and construct library 
    if not setup_library(config):
        return

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
    had_pipeline_error = False

    # 3. Generate, validate, and repair tests for each testable source file
    for index, source in enumerate(testable_sources, start=1):
        print(f"\n=== [{index}/{num_testable}] {source} ===")
        try:
            result = process_one_source(config, source, metrics)
            if result != "success":
                failures.append((source, result))
        except Exception as exc:
            had_pipeline_error = True
            failures.append((source, str(exc)))
            print(f"ERROR: failed while processing {source}.")
            print(exc)

    print_failure_summary(failures)

    if had_pipeline_error:
        print(f"Skipping {config.library}: one or more source files failed with a pipeline error.")
        return

    num_generated_tests = count_generated_tests(config)

    # 4. Record coverage, failures and cost metrics
    record_library_coverage(config, num_testable, num_generated_tests)
    write_compile_failure_summary(config)

    metrics.total_pipeline_runtime_seconds = time.monotonic() - started_at
    record_library_cost_metrics(config, num_testable, metrics)