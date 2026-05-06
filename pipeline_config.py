import argparse
from dataclasses import dataclass
from pathlib import Path

from ollama_models import get_model


DEFAULT_OLLAMA_MODEL = get_model("qwen_coder_small")
DEFAULT_LIBRARIES_ROOT = Path("libraries_small")
DEFAULT_TARGET_LIBRARY = "commons-cli-1.2"

# Path relative to libraries_small/<TARGET_LIBRARY>/src/main/java.
DEFAULT_TARGET_SOURCE_RELATIVE_PATH = Path("org/apache/commons/cli/AlreadySelectedException.java")

DEFAULT_MAX_REPAIR_ATTEMPTS = 2
MAVEN_TIMEOUT_SECONDS = 120
ERROR_CONTEXT_CHARS = 5000


SYSTEM_PROMPT = """
You are an expert Java test engineer generating JUnit 4 tests for an existing Maven project.

Your job is to produce useful, compiling, passing test classes that increase meaningful behavior coverage
of the class under test. Prefer tests that exercise public or package-private behavior observable from the
source code. Do not invent APIs, dependencies, constructors, fields, or behavior that are not present in
the provided source.

When repairing tests, fix compilation/runtime errors first, but also preserve or improve coverage. Do not
make the build pass by deleting useful tests unless they are invalid for the source; replace removed tests
with valid tests covering similar behavior.

Output only one complete Java test file inside a single ```java fenced code block. Do not include explanations,
analysis, markdown outside the code block, or partial snippets.
""".strip()


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
        description="Generate and repair JUnit 4 tests for one class in libraries_small."
    )
    parser.add_argument("--library", default=DEFAULT_TARGET_LIBRARY, help="Folder under libraries_small.")
    parser.add_argument(
        "--source",
        default=str(DEFAULT_TARGET_SOURCE_RELATIVE_PATH),
        help="Java file relative to src/main/java in the selected library.",
    )
    parser.add_argument("--model", default=DEFAULT_OLLAMA_MODEL, help="Ollama model name.")
    parser.add_argument("--attempts", type=int, default=DEFAULT_MAX_REPAIR_ATTEMPTS)
    return parser.parse_args()


def config_from_args(args: argparse.Namespace) -> PipelineConfig:
    return PipelineConfig(
        library=args.library,
        source=Path(args.source),
        model=args.model,
        attempts=args.attempts,
    )
