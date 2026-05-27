import subprocess
import sys

from coverage.ignore_tests import ignore_failing_test_methods
from coverage.jacoco import build_coverage_row, run_jacoco_coverage
from coverage.models import TestCounts
from coverage.surefire import read_surefire_test_results
from pipeline.config import PipelineConfig


def run_coverage_after_ignoring_failures(
    config: PipelineConfig,
    timeout: int,
    testable_source_files: int,
    generated_test_classes: int,
) -> dict[str, str]:
    """Ignore failing/erroring tests, run JaCoCo, and return one coverage CSV row."""
    if generated_test_classes == 0:
        return zero_coverage_row(config, testable_source_files)

    test_counts = collect_failures_and_ignore_tests(config, timeout)
    run_jacoco_coverage(config, timeout)

    return build_coverage_row(
        config,
        testable_source_files=testable_source_files,
        generated_test_classes=generated_test_classes,
        test_counts=test_counts,
    )


def zero_coverage_row(
    config: PipelineConfig,
    testable_source_files: int,
) -> dict[str, str]:
    """Return one zero-coverage CSV row when no generated test class compiled."""
    return {
        "group_id": config.group_id,
        "artifact_id": config.artifact_id,
        "version": config.version,
        "source": "LLM",
        "instruction_coverage": "0",
        "branch_coverage": "0",
        "line_coverage": "0",
        "complexity_coverage": "0",
        "method_coverage": "0",
        "class_coverage": "0",
        "testable_source_files": str(testable_source_files),
        "generated_test_classes": "0",
        "compilation_success_rate": "0",
        "tests_total": "0",
        "tests_passed": "0",
        "tests_failed_assertions": "0",
        "tests_runtime_errors": "0",
        "runtime_success_rate": "0",
        "failed_assertion_rate": "0",
        "runtime_error_rate": "0",
    }


def collect_failures_and_ignore_tests(config: PipelineConfig, timeout: int) -> TestCounts:
    """Run tests once, parse Surefire XML, and add @Ignore to failing/erroring methods."""
    print(f"Collecting Surefire failures for {config.library}...", file=sys.stderr)
    result = subprocess.run(
        [
            "mvn.cmd",
            "-q",
            "clean",
            "test",
            "-Dmaven.test.failure.ignore=true",
        ],
        cwd=config.library_path,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if result.returncode != 0:
        output = result.stdout + "\n" + result.stderr
        print(
            f"Initial test run failed for {config.library}:\n{output.strip()[-3000:]}",
            file=sys.stderr,
        )

    # Read Surefire reports to count tests and identify failing/erroring methods.
    test_counts, failing_tests = read_surefire_test_results(config.library_path)

    # Adds @Ignore to failing/erroring test methods
    ignored_methods = ignore_failing_test_methods(config.library_path, failing_tests)
    if ignored_methods > 0:
        print(f"Ignored {ignored_methods} failing/erroring test method(s) from {config.library}.")

    return TestCounts(
        total=test_counts.total,
        passed=test_counts.passed,
        failed_assertions=test_counts.failed_assertions,
        runtime_errors=test_counts.runtime_errors,
        ignored_methods=ignored_methods,
    )