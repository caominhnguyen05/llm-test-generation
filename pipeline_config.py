import argparse
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
OLLAMA_MODEL = "qwen2.5-coder:7b"
DEFAULT_LIBRARIES_ROOT = Path("libraries_no_repair")
DEFAULT_TARGET_LIBRARY = "commons-cli:commons-cli:1.2"

MAX_REPAIR_ATTEMPTS = 2
MAVEN_TIMEOUT_SECONDS = 100
ERROR_CONTEXT_CHARS = 5000

LLM_COVERAGE_CSV = REPO_ROOT / "results/coverage_no_repair.csv"
LLM_RUNTIME_CSV = REPO_ROOT / "results/runtime_no_repair.csv"
COMPILE_FAILURES_CSV = REPO_ROOT / "results/llm_compile_failures.csv"
COMPILE_FAILURE_SUMMARY_CSV = REPO_ROOT / "results/llm_compile_failure_summary.csv"


@dataclass(frozen=True)
class PipelineConfig:
    library: str
    attempts: int
    libraries_root: Path
    model: str = OLLAMA_MODEL

    @property
    def library_path(self) -> Path:
        return coordinate_to_path(self.libraries_root, self.library)

    @property
    def source_root(self) -> Path:
        return self.library_path / "src/main/java"

    @property
    def test_root(self) -> Path:
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
        "--libraries-root",
        type=Path,
        default=DEFAULT_LIBRARIES_ROOT,
        help="Root folder containing downloaded libraries.",
    )

    parser.add_argument(
        "--attempts",
        type=int,
        default=MAX_REPAIR_ATTEMPTS,
        help="Maximum number of repair attempts per generated test.",
    )

    args = parser.parse_args()

    return PipelineConfig(
        library=args.library,
        attempts=args.attempts,
        libraries_root=args.libraries_root,
    )


def coordinate_to_path(libraries_root: Path, library: str) -> Path:
    """Convert groupId:artifactId:version to libraries_root/groupId/artifactId/version."""
    parts = library.split(":")

    if len(parts) != 3 or any(not part for part in parts):
        raise ValueError(
            f"Invalid Maven coordinates: {library!r}. "
            "Expected format: groupId:artifactId:version."
        )

    group_id, artifact_id, version = parts
    return libraries_root / group_id / artifact_id / version