from pathlib import Path
from pipeline.config import PipelineConfig


def save_test(output_test_file: Path, test_code: str) -> None:
    """Save generated test code to src/test/java, creating directories as needed."""
    output_test_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_test_file, "w", encoding="utf-8", newline="\n") as file:
        file.write(test_code.rstrip() + "\n")

    print(f"Test saved to {output_test_file}")


def delete_test(test_file: Path, reason: str) -> None:
    """Delete a generated test file that would break later Maven/JaCoCo runs."""
    if test_file.exists():
        test_file.unlink()
        print(f"Deleted test: {test_file}")
        print(f"   Reason: {reason}")


def count_generated_tests(config: PipelineConfig) -> int:
    if not config.test_folder.exists():
        return 0

    return sum(1 for _ in config.test_folder.rglob("*.java"))