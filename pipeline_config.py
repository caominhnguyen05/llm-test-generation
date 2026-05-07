import argparse
from dataclasses import dataclass
from pathlib import Path

from llm.config import get_model, available_model_names


DEFAULT_OLLAMA_MODEL_NAME = "qwen_coder_small"
DEFAULT_LIBRARIES_ROOT = Path("libraries_small")
DEFAULT_TARGET_LIBRARY = "commons-cli-1.2"
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
        return self.libraries_root / self.library

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
        description="Generate and repair JUnit 4 tests for Java classes in libraries_small."
    )
    parser.add_argument("--library", default=DEFAULT_TARGET_LIBRARY, help="Folder under libraries_small.")
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
    )