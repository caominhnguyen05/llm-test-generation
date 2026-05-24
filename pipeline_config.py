import argparse
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_LIBRARIES_ROOT = Path("libraries_no_repair")
DEFAULT_TARGET_LIBRARY = "commons-cli:commons-cli:1.2"

MAX_REPAIR_ATTEMPTS = 2
MAVEN_TIMEOUT_SECONDS = 100
ERROR_CONTEXT_CHARS = 6000

COVERAGE_CSV = REPO_ROOT / "results/coverage_ollama/coverage_repair_1.csv"
COST_CSV = REPO_ROOT / "results/cost_ollama/runtime_repair_1.csv"
COMPILE_FAILURES_CSV = REPO_ROOT / "results/errors/compile_failures_1.csv"
COMPILE_FAILURE_SUMMARY_CSV = REPO_ROOT / "results/errors/compile_failure_summary_1.csv"


@dataclass(frozen=True)
class PipelineConfig:
    library: str
    attempts: int
    libraries_csv: Path | None = None
    record_failures: bool = True

    @property
    def group_id(self) -> str:
        return parse_coordinate(self.library)[0]

    @property
    def artifact_id(self) -> str:
        return parse_coordinate(self.library)[1]

    @property
    def version(self) -> str:
        return parse_coordinate(self.library)[2]

    @property
    def library_path(self) -> Path:
        return DEFAULT_LIBRARIES_ROOT / self.group_id / self.artifact_id / self.version

    @property
    def source_folder(self) -> Path:
        return self.library_path / "src/main/java"

    @property
    def test_folder(self) -> Path:
        return self.library_path / "src/test/java"


def parse_args() -> PipelineConfig:
    parser = argparse.ArgumentParser(
        description="Generate and repair JUnit 4 tests for Java classes in downloaded libraries."
    )

    parser.add_argument(
        "--library",
        default=DEFAULT_TARGET_LIBRARY,
        help=(
            "Maven coordinates in the form groupId:artifactId:version. "
            "Example: commons-cli:commons-cli:1.2"
        ),
    )

    parser.add_argument(
        "--attempts",
        type=int,
        default=MAX_REPAIR_ATTEMPTS,
        help="Maximum number of repair attempts per generated test.",
    )

    parser.add_argument(
        "--record_failures",
        type=parse_bool,
        default=True,
        help="Whether to record compile/structure failures to CSV. Use --record_failures=False to disable.",
    )

    parser.add_argument(
        "--libraries_csv",
        type=Path,
        default=None,
        help="CSV file containing group_id, artifact_id, and version columns.",
    )

    args = parser.parse_args()

    return PipelineConfig(
        library=args.library,
        attempts=args.attempts,
        libraries_csv=args.libraries_csv,
        record_failures=args.record_failures,
    )


def parse_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value

    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise argparse.ArgumentTypeError("Expected true or false.")


def parse_coordinate(library: str) -> tuple[str, str, str]:
    parts = library.split(":")

    if len(parts) != 3 or any(not part for part in parts):
        raise ValueError(
            f"Invalid Maven coordinates: {library!r}. "
            "Expected format: groupId:artifactId:version."
        )

    group_id, artifact_id, version = parts
    return group_id, artifact_id, version