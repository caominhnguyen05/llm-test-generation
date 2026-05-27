import argparse
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_TARGET_LIBRARY = "commons-cli:commons-cli:1.2"

MAVEN_TIMEOUT_SECONDS = 100
ERROR_CONTEXT_CHARS = 6000

COVERAGE_CSV = REPO_ROOT / "results/coverage_ollama/coverage_repair.csv"
COST_CSV = REPO_ROOT / "results/cost_ollama/runtime_repair.csv"
COMPILE_FAILURES_CSV = REPO_ROOT / "results/errors/compile_failures.csv"
COMPILE_FAILURE_SUMMARY_CSV = REPO_ROOT / "results/errors/compile_failure_summary.csv"


@dataclass(frozen=True)
class PipelineConfig:
    library: str
    attempts: int
    mode: str
    libraries_csv: Path | None = None

    @property
    def libraries_root(self) -> Path:
        if self.mode == "final":
            return Path("libraries_final")
        return Path(f"libraries_repair_{self.attempts}")

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
        return self.libraries_root / self.group_id / self.artifact_id / self.version

    @property
    def source_folder(self) -> Path:
        return self.library_path / "prompt_sources"

    @property
    def test_folder(self) -> Path:
        return self.library_path / "src/test/java"


def parse_args() -> PipelineConfig:
    parser = argparse.ArgumentParser(
        description="Generate and repair JUnit 4 tests for Java classes in downloaded libraries."
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["repair", "final"],
        required=True,
        help="Experiment mode: repair for repair-attempt comparison, final for final coverage experiment.",
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
        type=non_negative_int,
        required=True,
        help="Maximum number of repair attempts per generated test.",
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
        mode=args.mode,
    )


def parse_coordinate(library: str) -> tuple[str, str, str]:
    parts = library.split(":")

    if len(parts) != 3 or any(not part for part in parts):
        raise ValueError(
            f"Invalid Maven coordinates: {library!r}. "
            "Expected format: groupId:artifactId:version."
        )

    group_id, artifact_id, version = parts
    return group_id, artifact_id, version


def coordinate_to_path(libraries_root: Path, library: str) -> Path | None:
    try:
        group_id, artifact_id, version = parse_coordinate(library)
    except ValueError:
        return None
    return libraries_root / group_id / artifact_id / version

def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("--attempts must be at least 0.")
    return parsed