import subprocess
import platform
from collections.abc import Sequence
from pathlib import Path

MAVEN_TIMEOUT_SECONDS = 100


def get_maven_command() -> str:
    return "mvn.cmd" if platform.system() == "Windows" else "mvn"


def run_maven(
    args: Sequence[str],
    cwd: Path,
    local_repo: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run Maven with the platform-specific executable."""
    command = [get_maven_command()]
    if local_repo is not None:
        command.append(f"-Dmaven.repo.local={local_repo.resolve()}")
    command.extend(args)

    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=MAVEN_TIMEOUT_SECONDS,
    )