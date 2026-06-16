import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from coverage.models import TestCounts


def read_surefire_test_results(project_path: Path) -> tuple[TestCounts, dict[str, set[str]]]:
    """Parse Surefire XML reports to count total/passed/failed/skipped tests and identify failing/erroring test methods."""
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
            if local_xml_name(testcase.tag) != "testcase":
                continue

            total += 1
            classname = testcase.attrib.get("classname") or root.attrib.get("name", "")
            test_name = java_method_name(testcase.attrib.get("name", ""))
            has_failure = has_child(testcase, "failure")
            has_error = has_child(testcase, "error")
            has_skip = has_child(testcase, "skipped")

            failed_assertions += int(has_failure)
            runtime_errors += int(has_error)
            skipped += int(has_skip)

            if classname and test_name and (has_failure or has_error):
                failing_tests.setdefault(classname, set()).add(test_name)

    passed = total - failed_assertions - runtime_errors - skipped
    return TestCounts(
        total=total,
        passed=passed,
        failed_assertions=failed_assertions,
        runtime_errors=runtime_errors,
    ), failing_tests


def java_method_name(testcase_name: str) -> str:
    """Normalize Surefire names such as parameterized testName[0] to Java method names."""
    return testcase_name.split("[", 1)[0].strip()


def local_xml_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def has_child(element: ET.Element, child_name: str) -> bool:
    return any(local_xml_name(child.tag) == child_name for child in element)