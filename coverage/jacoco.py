import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from coverage.models import TestCounts
from pipeline_config import PipelineConfig


def run_jacoco_coverage(project_path: Path, timeout: int) -> bool:
    print(f"Running JaCoCo for {project_path.name}...", file=sys.stderr)
    result = subprocess.run(
        [
            "mvn.cmd",
            "-q",
            "clean",
            "jacoco:prepare-agent",
            "test",
            "jacoco:report",
            "-Drat.skip=true",
            "-Danimal.sniffer.skip=true",
            "-Dmaven.test.failure.ignore=true",
        ],
        cwd=project_path,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if result.returncode == 0:
        return True

    output = result.stdout + "\n" + result.stderr
    print(f"JaCoCo failed for {project_path.name}:\n{output.strip()[-3000:]}", file=sys.stderr)
    return False


def build_coverage_row(
    config: PipelineConfig,
    testable_source_files: int,
    generated_test_classes: int,
    test_counts: TestCounts = TestCounts(),
) -> dict[str, str]:
    """Build one row for the coverage CSV"""
    row = empty_coverage_row(config, testable_source_files, generated_test_classes, test_counts)
    report_path = config.library_path / "target/site/jacoco/jacoco.xml"

    if not report_path.exists():
        print(f"Missing JaCoCo XML report: {report_path}", file=sys.stderr)
        return row

    report_root = ET.parse(report_path).getroot()
    for counter in report_root.findall("counter"):
        field_name = coverage_field_name(counter.attrib.get("type", ""))
        if field_name in row:
            row[field_name] = coverage_percent(counter.attrib)

    return row


def empty_coverage_row(
    config: PipelineConfig,
    testable_source_files: int,
    generated_test_classes: int,
    test_counts: TestCounts,
) -> dict[str, str]:
    return {
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
        "compilation_success_rate": rate(generated_test_classes, testable_source_files),
        "tests_total": str(test_counts.total),
        "tests_passed": str(test_counts.passed),
        "tests_failed_assertions": str(test_counts.failed_assertions),
        "tests_runtime_errors": str(test_counts.runtime_errors),
        "runtime_success_rate": rate(test_counts.passed, test_counts.total),
        "failed_assertion_rate": rate(test_counts.failed_assertions, test_counts.total),
        "runtime_error_rate": rate(test_counts.runtime_errors, test_counts.total),
    }


def coverage_percent(counter_attributes: dict[str, str]) -> str:
    missed = int(counter_attributes.get("missed", "0"))
    covered = int(counter_attributes.get("covered", "0"))
    total = missed + covered
    if total == 0:
        return ""
    return f"{covered / total * 100:.2f}"


def coverage_field_name(counter_type: str) -> str:
    return f"{counter_type.lower()}_coverage"


def rate(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return ""
    return f"{numerator / denominator:.4f}"