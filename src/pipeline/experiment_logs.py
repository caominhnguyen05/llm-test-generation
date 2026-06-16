from datetime import datetime
from pathlib import Path
from shutil import rmtree

from pipeline.config import LibConfig


LOG_ROOT = Path("experiment_logs")


def get_library_log_dir(config: LibConfig) -> Path:
    library_name = f"{config.group_id}_{config.artifact_id}_{config.version}"
    if config.mode == "final":
        return LOG_ROOT / f"final_{config.llm_backend}" / library_name
    return LOG_ROOT / f"repair_{config.attempts}" / library_name


def clear_library_logs(config: LibConfig) -> None:
    """Delete existing experiment logs for this library."""
    log_dir = get_library_log_dir(config)
    if log_dir.exists():
        rmtree(log_dir)


def append_log_entry(
    path: Path,
    title: str,
    content: str,
    phase: str,
    package_name: str,
    class_name: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat(timespec="seconds")

    with path.open("a", encoding="utf-8") as log_file:
        log_file.write(f"\n\n===== {title} | {phase} | {timestamp} =====\n")
        log_file.write(f"class: {package_name}.{class_name}\n\n")
        log_file.write(content.rstrip())


def save_log(
    config: LibConfig,
    class_name: str,
    package_name: str,
    phase: str,
    filename: str,
    title: str,
    content: str,
) -> None:
    log_dir = get_library_log_dir(config) / f"{package_name}.{class_name}"

    append_log_entry(
        path=log_dir / filename,
        title=title,
        content=content,
        phase=phase,
        package_name=package_name,
        class_name=class_name,
    )


def save_prompt(
    config: LibConfig,
    class_name: str,
    package_name: str,
    phase: str,
    prompt: str,
) -> None:
    save_log(config, class_name, package_name, phase, "prompts.txt", "Prompt", prompt)


def save_response(
    config: LibConfig,
    class_name: str,
    package_name: str,
    phase: str,
    response: str,
) -> None:
    save_log(config, class_name, package_name, phase, "response.txt", "LLM Response", response)


def save_error(
    config: LibConfig,
    class_name: str,
    package_name: str,
    phase: str,
    error: str,
) -> None:
    save_log(config, class_name, package_name, phase, "error.txt", "Validation Error", error)