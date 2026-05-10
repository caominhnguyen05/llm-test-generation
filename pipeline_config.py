import argparse
from dataclasses import dataclass
from pathlib import Path

from llm.config import get_model, available_model_names


DEFAULT_OLLAMA_MODEL_NAME = "qwen_coder_small"
DEFAULT_LIBRARIES_ROOT = Path("libraries_sample")
DEFAULT_TARGET_LIBRARY = "commons-cli:commons-cli:1.2"
DEFAULT_TARGET_SOURCE_RELATIVE_PATH = Path("org/apache/commons/cli/AlreadySelectedException.java")

DEFAULT_MAX_REPAIR_ATTEMPTS = 2
MAVEN_TIMEOUT_SECONDS = 120
ERROR_CONTEXT_CHARS = 5000


@dataclass(frozen=True)
class PipelineConfig:
    library: str
    source: Path
    model: str
    attempts: int
    libraries_root: Path = DEFAULT_LIBRARIES_ROOT

    @property
    def library_path(self) -> Path:
        return resolve_library_path(self.libraries_root, self.library)

    @property
    def source_root(self) -> Path:
        return self.library_path / "src/main/java"

    @property
    def test_root(self) -> Path:
        return self.library_path / "src/test/java"

    @property
    def target_java_file(self) -> Path:
        return self.source_root / self.source


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate and repair JUnit 4 tests for Java classes in downloaded libraries."
    )
    parser.add_argument(
        "--library",
        default=DEFAULT_TARGET_LIBRARY,
        help=(
            "Maven coordinates in the downloaded folder structure. "
            "Examples: commons-cli:commons-cli:1.2, org.apache.commons:commons-csv:1.8."
        ),
    )
    parser.add_argument(
        "--libraries-root",
        default=str(DEFAULT_LIBRARIES_ROOT),
        help="Root folder containing libraries downloaded by libraries_builder/download.py.",
    )
    parser.add_argument(
        "--source",
        help="Optional Java file relative to src/main/java when running a single class.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_OLLAMA_MODEL_NAME,
        choices=available_model_names(),
        help="Ollama model preset name.",
    )
    parser.add_argument("--attempts", type=int, default=DEFAULT_MAX_REPAIR_ATTEMPTS)
    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> PipelineConfig:
    return PipelineConfig(
        library=args.library,
        source=Path(args.source) if args.source else DEFAULT_TARGET_SOURCE_RELATIVE_PATH,
        model=get_model(args.model),
        attempts=args.attempts,
        libraries_root=Path(args.libraries_root),
    )


def resolve_library_path(libraries_root: Path, library: str) -> Path:
    """Resolve Maven coordinates to libraries_root/groupId/artifactId/version."""
    coordinate_path = coordinate_to_path(libraries_root, library)
    if coordinate_path is not None:
        return coordinate_path

    safe_name = library.replace("/", "_").replace("\\", "_").replace(":", "_")
    return libraries_root / "__invalid_maven_coordinates__" / safe_name


def coordinate_to_path(libraries_root: Path, library: str) -> Path | None:
    parts = library.split(":")
    if len(parts) != 3:
        return None

    group_id, artifact_id, version = parts
    if not group_id or not artifact_id or not version:
        return None

    return libraries_root / group_id / artifact_id / version
