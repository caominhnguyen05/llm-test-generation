from pathlib import Path


def save_test_code(output_test_file: Path, test_code: str, label: str) -> None:
    """Save generated test code to src/test/java, creating directories as needed."""
    output_test_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_test_file, "w", encoding="utf-8", newline="\n") as file:
        file.write(test_code.rstrip() + "\n")

    print(f"{label} test saved to {output_test_file}")


def delete_generated_test(output_test_file: Path, reason: str) -> None:
    """Delete a generated test file that would break later Maven/JaCoCo runs."""
    if output_test_file.exists():
        output_test_file.unlink()
        print(f"Deleted generated test: {output_test_file}")
        print(f"   Reason: {reason}")