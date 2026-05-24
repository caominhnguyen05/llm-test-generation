from pathlib import Path

from pipeline_config import PipelineConfig
from postprocess import write_file
from preprocess import extract_package_and_class


def generated_test_path(config: PipelineConfig, source: Path) -> Path:
    source_file = config.source_folder / source
    package_name, class_name = extract_package_and_class(source_file, config.source_folder)
    test_class = f"{class_name}Test"
    return config.test_folder / package_name.replace(".", "/") / f"{test_class}.java"


def save_test_code(output_test_file: Path, test_code: str, label: str) -> None:
    """Save generated test code to src/test/java, creating directories as needed."""
    write_file(output_test_file, test_code)
    print(f"{label} test saved to {output_test_file}")


def count_generated_test_classes(config: PipelineConfig, sources: list[Path]) -> int:
    """Count surviving generated tests for the sources processed in this run."""
    return sum(1 for source in sources if generated_test_path(config, source).exists())


def delete_generated_test_for_source(config: PipelineConfig, source: Path, reason: str) -> None:
    """Delete the generated test file for a source after an unrecoverable exception."""
    try:
        test_file = generated_test_path(config, source)
    except Exception as exc:
        print(f"Could not identify generated test for {source}: {exc}")
        return

    delete_generated_test(test_file, reason)


def delete_generated_test(output_test_file: Path, reason: str) -> None:
    """Delete a generated test file that would break later Maven/JaCoCo runs."""
    if output_test_file.exists():
        output_test_file.unlink()
        print(f"Deleted generated test: {output_test_file}")
        print(f"   Reason: {reason}")