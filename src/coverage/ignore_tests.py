import re
import sys
from pathlib import Path


IGNORE_LINE = '@Ignore("Ignored due to assertion/runtime failure")'


def ignore_failing_test_methods(project_path: Path, failing_tests: dict[str, set[str]]) -> int:
    ignored_methods = 0
    for classname, method_names in failing_tests.items():
        test_file = find_test_file(project_path, classname)
        if test_file is None:
            print(f"Could not find source file for failing test class {classname}", file=sys.stderr)
            continue

        ignored_methods += ignore_methods_in_java_file(test_file, method_names)
    return ignored_methods


def find_test_file(project_path: Path, classname: str) -> Path | None:
    test_root = project_path / "src/test/java"
    package_path = test_root / Path(*classname.split(".")).with_suffix(".java")
    if package_path.exists():
        return package_path

    simple_name = classname.rsplit(".", 1)[-1]
    matches = sorted(test_root.rglob(f"{simple_name}.java")) if test_root.exists() else []
    return matches[0] if matches else None


def ignore_methods_in_java_file(test_file: Path, method_names: set[str]) -> int:
    lines = test_file.read_text(encoding="utf-8").splitlines(keepends=True)
    insertion_indexes = find_ignore_annotation_indexes(lines, method_names)
    if not insertion_indexes:
        print(f"No matching failing method(s) found in {test_file}: {sorted(method_names)}", file=sys.stderr)
        return 0

    for index in sorted(insertion_indexes, reverse=True):
        indent = re.match(r"\s*", lines[index]).group(0)
        lines.insert(index, f"{indent}{IGNORE_LINE}\n")

    test_file.write_text("".join(lines), encoding="utf-8")
    return len(insertion_indexes)


def find_ignore_annotation_indexes(lines: list[str], method_names: set[str]) -> list[int]:
    insertion_indexes: list[int] = []
    index = 0

    while index < len(lines):
        if not lines[index].strip().startswith("@Test"):
            index += 1
            continue

        annotation_start = annotation_block_start(lines, index)
        signature_index = first_line_after_annotations(lines, index + 1)

        if has_ignore_annotation(lines, annotation_start, signature_index):
            index = signature_index + 1
            continue

        method_index = matching_method_signature_index(lines, signature_index, method_names)
        if method_index is None:
            index += 1
            continue

        insertion_indexes.append(annotation_start)
        index = method_index + 1

    return insertion_indexes


def annotation_block_start(lines: list[str], test_annotation_index: int) -> int:
    start = test_annotation_index
    while start > 0 and lines[start - 1].strip().startswith("@"):
        start -= 1
    return start


def first_line_after_annotations(lines: list[str], index: int) -> int:
    while index < len(lines) and lines[index].strip().startswith("@"):
        index += 1
    return index


def has_ignore_annotation(lines: list[str], start: int, end: int) -> bool:
    annotation_text = " ".join(line.strip() for line in lines[start:end])
    return "Ignore" in annotation_text


def matching_method_signature_index(lines: list[str], start: int, method_names: set[str]) -> int | None:
    signature_parts: list[str] = []

    for index in range(start, len(lines)):
        signature_parts.append(lines[index].strip())
        signature_text = " ".join(signature_parts)

        if matches_any_method(signature_text, method_names):
            return index
        if "{" in lines[index] or ";" in lines[index]:
            return None

    return None


def matches_any_method(signature_text: str, method_names: set[str]) -> bool:
    return any(re.search(rf"\b{re.escape(method_name)}\s*\(", signature_text) for method_name in method_names)
