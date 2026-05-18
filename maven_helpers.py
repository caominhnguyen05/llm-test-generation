import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from shutil import move
from pipeline_config import ERROR_CONTEXT_CHARS, MAVEN_TIMEOUT_SECONDS


@contextmanager
def only_test_class_visible(library_path: Path, test_class: str):
    test_root = library_path / "src/test/java"
    if not test_root.exists():
        yield
        return

    hidden_files: list[tuple[Path, Path]] = []
    with tempfile.TemporaryDirectory(prefix=".pipeline-hidden-tests-", dir=library_path) as temp_dir:
        temp_root = Path(temp_dir)
        try:
            for test_file in test_root.rglob("*Test.java"):
                if test_file.stem == test_class:
                    continue

                hidden_file = temp_root / test_file.relative_to(test_root)
                hidden_file.parent.mkdir(parents=True, exist_ok=True)
                move(str(test_file), str(hidden_file))
                hidden_files.append((hidden_file, test_file))
            yield
        finally:
            for hidden_file, original_file in reversed(hidden_files):
                original_file.parent.mkdir(parents=True, exist_ok=True)
                if hidden_file.exists():
                    move(str(hidden_file), str(original_file))


def run_maven_test_compile(library_path: Path, test_class: str) -> tuple[bool, str]:
    print(f"\nCompiling test class {test_class}...")

    command = [
        "mvn.cmd",
        "-q",
        "clean",
        "test-compile",
        "-Drat.skip=true",
        "-Danimal.sniffer.skip=true",
    ]

    with only_test_class_visible(library_path, test_class):
        result = subprocess.run(
            command,
            cwd=library_path,
            capture_output=True,
            text=True,
            timeout=MAVEN_TIMEOUT_SECONDS,
        )

    if result.returncode == 0:
        print(f"✅ {test_class} compiled successfully.")
        return True, ""

    error_output = result.stdout + "\n" + result.stderr
    return False, error_output[-ERROR_CONTEXT_CHARS:]


def run_maven_test_runtime(library_path: Path, test_class: str) -> tuple[bool, str]:
    print(f"\nRunning Maven tests for {test_class}...")

    command = [
        "mvn.cmd",
        "-q",
        "test",
        f"-Dtest={test_class}",
        "-Drat.skip=true",
        "-Danimal.sniffer.skip=true",
    ]

    with only_test_class_visible(library_path, test_class):
        result = subprocess.run(
            command,
            cwd=library_path,
            capture_output=True,
            text=True,
            timeout=MAVEN_TIMEOUT_SECONDS,
        )

    output = result.stdout + "\n" + result.stderr
    return result.returncode == 0, output[-ERROR_CONTEXT_CHARS:]