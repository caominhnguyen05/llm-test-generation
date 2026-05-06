import subprocess
from pathlib import Path

from pipeline_config import ERROR_CONTEXT_CHARS, MAVEN_TIMEOUT_SECONDS


def run_maven_test(library_path: Path, test_class: str) -> tuple[bool, str]:
    print(f"\nRunning Maven tests for {test_class}...")
    command = ["mvn.cmd", "-q", "test", f"-Dtest={test_class}"]

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
