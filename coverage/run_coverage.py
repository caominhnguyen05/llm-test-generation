import argparse
import csv
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from coverage.config import FIELDNAMES, COUNTER_FIELDS


@dataclass(frozen=True)
class MavenProject:
    path: Path
    group_id: str
    artifact_id: str
    version: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run JaCoCo coverage for Maven libraries and output CSV.")
    parser.add_argument("root", nargs="?", default="libraries_small", help="Folder containing Maven library folders.")
    parser.add_argument("--output", "-o", help="Optional CSV output file. Defaults to stdout.")
    return parser.parse_args()


def find_maven_projects(root: Path) -> list[Path]:
    if (root / "pom.xml").exists():
        return [root]
    return sorted(path for path in root.iterdir() if path.is_dir() and (path / "pom.xml").exists())


def read_maven_project(project_path: Path) -> MavenProject:
    pom_path = project_path / "pom.xml"
    root = ET.parse(pom_path).getroot()
    namespace = _xml_namespace(root)

    group_id = _find_text(root, "groupId", namespace) or _find_text(root, "parent/groupId", namespace)
    artifact_id = _find_text(root, "artifactId", namespace)
    version = _find_text(root, "version", namespace) or _find_text(root, "parent/version", namespace)

    return MavenProject(
        path=project_path,
        group_id=group_id or "",
        artifact_id=artifact_id or project_path.name,
        version=version or "",
    )


def run_jacoco(project_path: Path, timeout: int) -> tuple[bool, str]:
    print(f"Running JaCoCo for {project_path.name}...", file=sys.stderr)
    command = [
        "mvn.cmd",
        "-q",
        "clean",
        "jacoco:prepare-agent",
        "test",
        "jacoco:report",
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

    output = result.stdout + "\n" + result.stderr
    if result.returncode == 0:
        return True, output

    print(f"JaCoCo failed for {project_path.name}:\n{output.strip()[-3000:]}", file=sys.stderr)
    return False, output


def read_coverage(project: MavenProject, jacoco_success: bool, maven_output: str) -> dict[str, str]:
    tests_passed, tests_total = _parse_test_counts(maven_output)
    row = {
        "group_id": project.group_id,
        "artifact_id": project.artifact_id,
        "version": project.version,
        "source": "LLM",
        "instruction_coverage": "",
        "branch_coverage": "",
        "line_coverage": "",
        "complexity_coverage": "",
        "method_coverage": "",
        "class_coverage": "",
        "tests_passed": tests_passed,
        "tests_total": tests_total,
        "jacoco_success": str(jacoco_success).lower(),
        "percentage_passed": (
            f"{(int(tests_passed) / int(tests_total)) * 100:.2f}"
            if tests_total.isdigit() and int(tests_total) > 0
            else ""
        ),
    }

    report_path = project.path / "target/site/jacoco/jacoco.xml"
    if not report_path.exists():
        print(f"Missing JaCoCo XML report: {report_path}", file=sys.stderr)
        return row

    report_root = ET.parse(report_path).getroot()
    for counter in report_root.findall("counter"):
        counter_type = counter.attrib.get("type")
        field_name = COUNTER_FIELDS.get(counter_type or "")
        if field_name:
            row[field_name] = _coverage_percent(counter.attrib)

    return row


def write_rows(rows: list[dict[str, str]], output_path: str | None) -> None:
    if output_path:
        with open(output_path, "w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)
        return

    writer = csv.DictWriter(sys.stdout, fieldnames=FIELDNAMES)
    writer.writeheader()
    writer.writerows(rows)


def append_row(row: dict[str, str], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    should_write_header = not output_path.exists() or output_path.stat().st_size == 0
    with open(output_path, "a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        if should_write_header:
            writer.writeheader()
        writer.writerow(row)


def _coverage_percent(counter_attributes: dict[str, str]) -> str:
    missed = int(counter_attributes.get("missed", "0"))
    covered = int(counter_attributes.get("covered", "0"))
    total = missed + covered
    if total == 0:
        return ""
    return f"{covered / total * 100:.2f}"


def _parse_test_counts(maven_output: str) -> tuple[str, str]:
    matches = list(
        re.finditer(
            r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)",
            maven_output,
        )
    )
    if not matches:
        return "", ""

    tests_total = 0
    tests_not_passed = 0
    for match in matches:
        tests_run = int(match.group(1))
        failures = int(match.group(2))
        errors = int(match.group(3))
        skipped = int(match.group(4))
        tests_total += tests_run
        tests_not_passed += failures + errors + skipped

    return str(tests_total - tests_not_passed), str(tests_total)


def _xml_namespace(root: ET.Element) -> str:
    if root.tag.startswith("{"):
        return root.tag.split("}", 1)[0].strip("{")
    return ""


def _find_text(root: ET.Element, path: str, namespace: str) -> str | None:
    if namespace:
        namespaced_path = "/".join(f"{{{namespace}}}{part}" for part in path.split("/"))
        element = root.find(namespaced_path)
    else:
        element = root.find(path)
    if element is None or element.text is None:
        return None
    return element.text.strip()


def main() -> None:
    args = parse_args()
    root = Path(args.root)
    if not root.exists():
        raise SystemExit(f"Root folder not found: {root}")

    rows = []
    for project_path in find_maven_projects(root):
        project = read_maven_project(project_path)
        jacoco_success, maven_output = run_jacoco(project.path, 300)
        rows.append(read_coverage(project, jacoco_success, maven_output))

    write_rows(rows, args.output)


if __name__ == "__main__":
    main()
