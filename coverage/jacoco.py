import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
import requests

from coverage.models import TestCounts
from pipeline.config import LibConfig, REPO_ROOT


JACOCO_VERSION = "0.8.12"
JACOCO_CLI_JAR = REPO_ROOT / "coverage" / "jacococli.jar"
JACOCO_CLI_URL = (
    "https://repo1.maven.org/maven2/org/jacoco/org.jacoco.cli/"
    f"{JACOCO_VERSION}/org.jacoco.cli-{JACOCO_VERSION}-nodeps.jar"
)


def download_jacoco_cli() -> Path:
    if JACOCO_CLI_JAR.exists():
        return JACOCO_CLI_JAR

    print(f"Downloading JaCoCo CLI {JACOCO_VERSION}...", file=sys.stderr)
    JACOCO_CLI_JAR.parent.mkdir(parents=True, exist_ok=True)

    response = requests.get(JACOCO_CLI_URL, timeout=30)
    response.raise_for_status()
    JACOCO_CLI_JAR.write_bytes(response.content)

    return JACOCO_CLI_JAR


def project_relative(project_path: Path, path: Path) -> str:
    return str(path.relative_to(project_path))


def run_jacoco_coverage(config: LibConfig, timeout: int) -> bool:
    project_path = config.library_path
    print(f"Running JaCoCo for {config.library}...")

    test_result = subprocess.run(
        [
            "mvn.cmd",
            "-q",
            "clean",
            f"org.jacoco:jacoco-maven-plugin:{JACOCO_VERSION}:prepare-agent",
            "test",
            "-Dmaven.test.failure.ignore=true",
        ],
        cwd=project_path,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if test_result.returncode != 0:
        output = test_result.stdout + "\n" + test_result.stderr
        print(f"JaCoCo test run failed for {config.library}:\n{output.strip()[-3000:]}")
        return False

    exec_file = project_path / "target/jacoco.exec"
    classfiles = project_path / "artifacts" / f"{config.artifact_id}-{config.version}.jar"
    sourcefiles = project_path / "prompt_sources"
    report_dir = project_path / "target/site/jacoco"
    xml_report = report_dir / "jacoco.xml"
    jacoco_cli_jar = download_jacoco_cli()

    missing = [
        str(path)
        for path in (exec_file, classfiles, sourcefiles, jacoco_cli_jar)
        if not path.exists()
    ]

    if missing:
        print(f"Cannot run JaCoCo CLI; missing: {', '.join(missing)}", file=sys.stderr)
        return False

    report_dir.mkdir(parents=True, exist_ok=True)

    report_result = subprocess.run(
        [
            "java",
            "-jar",
            str(jacoco_cli_jar),
            "report",
            str(exec_file),
            "--classfiles",
            str(classfiles),
            "--sourcefiles",
            str(sourcefiles),
            "--xml",
            str(xml_report),
            "--html",
            str(report_dir),
        ],
        cwd=project_path,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if report_result.returncode == 0:
        return True

    output = report_result.stdout + "\n" + report_result.stderr
    print(f"JaCoCo CLI failed for {config.library}:\n{output.strip()[-3000:]}")
    return False


def build_coverage_row(
    config: LibConfig,
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
    config: LibConfig,
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