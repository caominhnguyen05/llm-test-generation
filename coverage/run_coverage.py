import csv
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from coverage.config import FIELDNAMES
from pipeline_config import PipelineConfig


@dataclass(frozen=True)
class TestCounts:
    total: int = 0
    passed: int = 0
    failed_assertions: int = 0
    runtime_errors: int = 0


@dataclass(frozen=True)
class CoveragePrepResult:
    test_counts: TestCounts
    ignored_methods: int = 0


def run_jacoco_coverage(project_path: Path, timeout: int) -> bool:
    print(f"Running JaCoCo for {project_path.name}...", file=sys.stderr)
    command = [
        "mvn.cmd",
        "-q",
        "clean",
        "jacoco:prepare-agent",
        "test",
        "jacoco:report",
        "-Drat.skip=true",
        "-Danimal.sniffer.skip=true",
        "-Dmaven.test.failure.ignore=true",
    ]

    result = subprocess.run(
        command,
        cwd=project_path,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    output = result.stdout + "\n" + result.stderr
    if result.returncode == 0:
        return True

    print(f"JaCoCo failed for {project_path.name}:\n{output.strip()[-3000:]}", file=sys.stderr)
    return False


def run_tests_and_ignore_failures(project_path: Path, timeout: int) -> CoveragePrepResult:
    """Run tests once, parse Surefire XML, and ignore failing/erroring test methods."""
    print(f"Collecting Surefire failures for {project_path.name}...", file=sys.stderr)
    command = [
        "mvn.cmd",
        "-q",
        "clean",
        "test",
        "-Dmaven.test.failure.ignore=true",
        "-Drat.skip=true",
        "-Danimal.sniffer.skip=true",
    ]

    result = subprocess.run(
        command,
        cwd=project_path,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        output = result.stdout + "\n" + result.stderr
        print(f"Initial test run failed for {project_path.name}:\n{output.strip()[-3000:]}", file=sys.stderr)

    test_counts, failing_tests = read_surefire_test_results(project_path)
    ignored_methods = ignore_failing_test_methods(project_path, failing_tests)
    if ignored_methods:
        print(f"Ignored {ignored_methods} failing/erroring test method(s) from {project_path.name}.")
    return CoveragePrepResult(test_counts, ignored_methods)


def run_coverage_after_ignoring_failures(project_path: Path, timeout: int) -> CoveragePrepResult:
    """Ignore failing/erroring tests before running JaCoCo, preserving original runtime counts."""
    prep_result = run_tests_and_ignore_failures(project_path, timeout)
    run_jacoco_coverage(project_path, timeout)
    return prep_result


def build_coverage_row(
    config: PipelineConfig,
    testable_source_files: int,
    generated_test_classes: int,
    test_counts: TestCounts = TestCounts(),
) -> dict[str, str]:
    row = {
        "group_id": config.group_id,
        "artifact_id": config.artifact_id,
        "version": config.version,
        "source": "LLM",
        "instruction_coverage": "",
        "branch_coverage": "",
        "line_coverage": "",
        "complexity_coverage": "",
        "method_coverage": "",
        "class_coverage": "",
        "testable_source_files": str(testable_source_files),
        "generated_test_classes": str(generated_test_classes),
        "compilation_success_rate": _rate(generated_test_classes, testable_source_files),
        "tests_total": str(test_counts.total),
        "tests_passed": str(test_counts.passed),
        "tests_failed_assertions": str(test_counts.failed_assertions),
        "tests_runtime_errors": str(test_counts.runtime_errors),
        "runtime_success_rate": _rate(test_counts.passed, test_counts.total),
        "failed_assertion_rate": _rate(test_counts.failed_assertions, test_counts.total),
        "runtime_error_rate": _rate(test_counts.runtime_errors, test_counts.total),
    }

    report_path = config.library_path / "target/site/jacoco/jacoco.xml"
    if not report_path.exists():
        print(f"Missing JaCoCo XML report: {report_path}", file=sys.stderr)
        return row

    report_root = ET.parse(report_path).getroot()
    for counter in report_root.findall("counter"):
        field_name = _coverage_field_name(counter.attrib.get("type", ""))
        if field_name in row:
            row[field_name] = _coverage_percent(counter.attrib)

    return row


def read_surefire_test_results(project_path: Path) -> tuple[TestCounts, dict[str, set[str]]]:
    reports_dir = project_path / "target/surefire-reports"
    if not reports_dir.exists():
        return TestCounts(), {}

    total = 0
    failed_assertions = 0
    runtime_errors = 0
    skipped = 0
    failing_tests: dict[str, set[str]] = {}

    for report_path in sorted(reports_dir.glob("TEST-*.xml")):
        try:
            root = ET.parse(report_path).getroot()
        except ET.ParseError as exc:
            print(f"Could not parse Surefire report {report_path}: {exc}", file=sys.stderr)
            continue

        for testcase in root.iter():
            if _local_xml_name(testcase.tag) != "testcase":
                continue
            total += 1
            classname = testcase.attrib.get("classname") or root.attrib.get("name", "")
            test_name = _java_method_name(testcase.attrib.get("name", ""))
            has_failure = _has_child(testcase, "failure")
            has_error = _has_child(testcase, "error")
            has_skip = _has_child(testcase, "skipped")

            if has_failure:
                failed_assertions += 1
            if has_error:
                runtime_errors += 1
            if has_skip:
                skipped += 1
            if classname and test_name and (has_failure or has_error):
                failing_tests.setdefault(classname, set()).add(test_name)

    passed = total - failed_assertions - runtime_errors - skipped
    return TestCounts(total, passed, failed_assertions, runtime_errors), failing_tests


def ignore_failing_test_methods(project_path: Path, failing_tests: dict[str, set[str]]) -> int:
    ignored_methods = 0
    for classname, method_names in failing_tests.items():
        test_file = _find_test_file(project_path, classname)
        if test_file is None:
            print(f"Could not find source file for failing test class {classname}", file=sys.stderr)
            continue

        ignored_methods += _ignore_methods_in_java_file(test_file, method_names)
    return ignored_methods


def append_coverage_row(row: dict[str, str], output_path: Path) -> None:
    """Append one coverage row without modifying existing CSV rows."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    should_write_header = not output_path.exists() or output_path.stat().st_size == 0

    with open(output_path, "a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        if should_write_header:
            writer.writeheader()
        writer.writerow(_project_fieldnames(row))


def _coverage_percent(counter_attributes: dict[str, str]) -> str:
    missed = int(counter_attributes.get("missed", "0"))
    covered = int(counter_attributes.get("covered", "0"))
    total = missed + covered
    if total == 0:
        return ""
    return f"{covered / total * 100:.2f}"


def _coverage_field_name(counter_type: str) -> str:
    return f"{counter_type.lower()}_coverage"


def _project_fieldnames(row: dict[str, str]) -> dict[str, str]:
    return {fieldname: row.get(fieldname, "") for fieldname in FIELDNAMES}


def _java_method_name(testcase_name: str) -> str:
    """Normalize Surefire names such as parameterized testName[0] to Java method names."""
    return testcase_name.split("[", 1)[0].strip()


def _find_test_file(project_path: Path, classname: str) -> Path | None:
    test_root = project_path / "src/test/java"
    package_path = test_root / Path(*classname.split(".")).with_suffix(".java")
    if package_path.exists():
        return package_path

    simple_name = classname.rsplit(".", 1)[-1]
    matches = sorted(test_root.rglob(f"{simple_name}.java")) if test_root.exists() else []
    return matches[0] if matches else None


def _ignore_methods_in_java_file(test_file: Path, method_names: set[str]) -> int:
    lines = test_file.read_text(encoding="utf-8").splitlines(keepends=True)
    insertion_indexes = _find_ignore_annotation_indexes(lines, method_names)
    if not insertion_indexes:
        print(f"No matching failing method(s) found in {test_file}: {sorted(method_names)}", file=sys.stderr)
        return 0

    for index in sorted(insertion_indexes, reverse=True):
        indent = re.match(r"\s*", lines[index]).group(0)
        lines.insert(index, f'{indent}@Ignore("Ignored after failing during coverage collection")\n')

    test_file.write_text("".join(lines), encoding="utf-8")
    return len(insertion_indexes)


def _find_ignore_annotation_indexes(lines: list[str], method_names: set[str]) -> list[int]:
    insertion_indexes: list[int] = []
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped.startswith("@Test"):
            index += 1
            continue

        annotation_start = _annotation_block_start(lines, index)
        signature_index = index + 1
        while signature_index < len(lines) and lines[signature_index].strip().startswith("@"):
            signature_index += 1

        annotation_text = " ".join(line.strip() for line in lines[annotation_start:signature_index])
        if "Ignore" in annotation_text:
            index = signature_index + 1
            continue

        signature_parts: list[str] = []
        search_index = signature_index
        while search_index < len(lines):
            signature_parts.append(lines[search_index].strip())
            signature_text = " ".join(signature_parts)
            method_name = _matching_method_name(signature_text, method_names)
            if method_name:
                insertion_indexes.append(annotation_start)
                index = search_index + 1
                break
            if "{" in lines[search_index] or ";" in lines[search_index]:
                break
            search_index += 1
        else:
            break

        if index <= signature_index:
            index += 1

    return insertion_indexes


def _annotation_block_start(lines: list[str], test_annotation_index: int) -> int:
    start = test_annotation_index
    while start > 0 and lines[start - 1].strip().startswith("@"):
        start -= 1
    return start


def _matching_method_name(signature_text: str, method_names: set[str]) -> str | None:
    for method_name in method_names:
        if re.search(rf"\b{re.escape(method_name)}\s*\(", signature_text):
            return method_name
    return None


def _rate(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return ""
    return f"{numerator / denominator:.4f}"


def _local_xml_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _has_child(element: ET.Element, child_name: str) -> bool:
    return any(_local_xml_name(child.tag) == child_name for child in element)
