from pathlib import Path

from pipeline_config import PipelineConfig
from preprocess import extract_package_and_class


def generated_test_path(config: PipelineConfig, source: Path) -> Path:
    source_file = config.source_folder / source
    package_name, class_name = extract_package_and_class(source_file, config.source_folder)
    test_class = f"{class_name}Test"
    return config.test_folder / package_name.replace(".", "/") / f"{test_class}.java"


def save_test_code(output_test_file: Path, test_code: str, label: str) -> None:
    """Save generated test code to src/test/java, creating directories as needed."""
    output_test_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_test_file, "w", encoding="utf-8", newline="\n") as file:
        file.write(test_code.rstrip() + "\n")

    print(f"{label} test saved to {output_test_file}")


def count_generated_test_classes(config: PipelineConfig, sources: list[Path]) -> int:
    """Count surviving generated tests for the sources processed in this run."""
    return sum(1 for source in sources if generated_test_path(config, source).exists())


def delete_generated_test(output_test_file: Path, reason: str) -> None:
    """Delete a generated test file that would break later Maven/JaCoCo runs."""
    if output_test_file.exists():
        output_test_file.unlink()
        print(f"Deleted generated test: {output_test_file}")
        print(f"   Reason: {reason}")