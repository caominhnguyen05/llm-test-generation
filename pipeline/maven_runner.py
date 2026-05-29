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
) -> subprocess.CompletedProcess[str]:
    """Run Maven with the platform-specific executable."""
    return subprocess.run(
        [get_maven_command(), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=MAVEN_TIMEOUT_SECONDS,
    )