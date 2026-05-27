import subprocess
import sys
from pathlib import Path

from coverage.ignore_tests import ignore_failing_test_methods
from coverage.jacoco import run_jacoco_coverage
from coverage.models import CoveragePrepResult
from coverage.surefire import read_surefire_test_results


def run_coverage_after_ignoring_failures(project_path: Path, timeout: int) -> CoveragePrepResult:
    """Ignore failing/erroring tests, then run JaCoCo while preserving original test counts."""
    prep_result = collect_failures_and_ignore_tests(project_path, timeout)
    run_jacoco_coverage(project_path, timeout)
    return prep_result


def collect_failures_and_ignore_tests(project_path: Path, timeout: int) -> CoveragePrepResult:
    """Run tests once, parse Surefire XML, and add @Ignore to failing/erroring methods."""
    print(f"Collecting Surefire failures for {project_path.name}...", file=sys.stderr)
    result = subprocess.run(
        [
            "mvn.cmd",
            "-q",
            "clean",
            "test",
            "-Dmaven.test.failure.ignore=true",
        ],
        cwd=project_path,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if result.returncode != 0:
        output = result.stdout + "\n" + result.stderr
        print(f"Initial test run failed for {project_path.name}:\n{output.strip()[-3000:]}", file=sys.stderr)

    # Read Surefire test reports to identify failing/erroring tests
    test_counts, failing_tests = read_surefire_test_results(project_path)

    # Adds @Ignore to failing/erroring test methods
    ignored_methods = ignore_failing_test_methods(project_path, failing_tests)
    if ignored_methods > 0:
        print(f"Ignored {ignored_methods} failing/erroring test method(s) from {project_path.name}.")

    return CoveragePrepResult(test_counts, ignored_methods)