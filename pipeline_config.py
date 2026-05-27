import argparse
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_TARGET_LIBRARY = "commons-cli:commons-cli:1.2"


@dataclass(frozen=True)
class PipelineConfig:
    library: str
    attempts: int
    mode: str
    llm_backend: str

    @property
    def libraries_csv(self) -> Path:
        return REPO_ROOT / "csv_data" / f"libraries_{self.mode}.csv"

    @property
    def libraries_root(self) -> Path:
        if self.mode == "final":
            return Path("libraries_final")
        return Path(f"libraries_repair_{self.attempts}")
    
    @property
    def results_root(self) -> Path:
        if self.mode == "repair":
            return REPO_ROOT / "results" / "repair"
        return REPO_ROOT / "results" / "final"
    
    @property
    def coverage_csv(self) -> Path:
        if self.mode == "final":
            return self.results_root / f"{self.llm_backend}" / "coverage.csv"
        return self.results_root / f"repair_{self.attempts}" / "coverage.csv"

    @property
    def cost_csv(self) -> Path:
        if self.mode == "final":
            return self.results_root / f"{self.llm_backend}" / "cost.csv"
        return self.results_root / f"repair_{self.attempts}" / "cost.csv"

    @property
    def compile_failures_csv(self) -> Path:
        if self.mode == "final":
            return self.results_root / f"{self.llm_backend}" / "compile_failures.csv"
        return self.results_root / f"repair_{self.attempts}" / "compile_failures.csv"
    
    @property
    def compile_failure_summary_csv(self) -> Path:
        if self.mode == "final":
            return self.results_root / f"{self.llm_backend}" / "compile_failures_summary.csv"
        return self.results_root / f"repair_{self.attempts}" / "compile_failures_summary.csv"

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
        "--llm_backend",
        choices=["ollama", "openrouter"],
        default="ollama",
        help="LLM backend to use: ollama or openrouter. Default is ollama.",
    )

    args = parser.parse_args()

    return PipelineConfig(
        library=args.library,
        attempts=args.attempts,
        mode=args.mode,
        llm_backend=args.llm_backend,
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


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("--attempts must be at least 0.")
    return parsed