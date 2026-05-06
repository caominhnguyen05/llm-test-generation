import subprocess
from pathlib import Path

from pipeline_config import ERROR_CONTEXT_CHARS, MAVEN_TIMEOUT_SECONDS


def run_maven_test_compile(library_path: Path, test_class: str) -> tuple[bool, str]:
    print(f"\nCompiling test class {test_class}...")

    command = [
        "mvn.cmd",
        "-q",
        "test-compile",
        f"-Dtest={test_class}",
    ]


    result = subprocess.run(
        command,
        cwd=library_path,
        capture_output=True,
        text=True,
        timeout=MAVEN_TIMEOUT_SECONDS,
    )

    if result.returncode == 0:
        return True, ""

    error_output = result.stdout + "\n" + result.stderr
    return False, error_output[-ERROR_CONTEXT_CHARS:]


def run_maven_test_ignore_failures(library_path: Path, test_class: str) -> tuple[bool, str]:
    print(f"\nRunning Maven tests for {test_class}, ignoring assertion failures...")
    command = [
        "mvn.cmd",
        "-q",
        "test",
        f"-Dtest={test_class}",
        "-Dmaven.test.failure.ignore=true",
    ]

    result = subprocess.run(
        command,
        cwd=library_path,
        capture_output=True,
        text=True,
        timeout=MAVEN_TIMEOUT_SECONDS,
    )

    output = result.stdout + "\n" + result.stderr
    return True, output[-ERROR_CONTEXT_CHARS:]
