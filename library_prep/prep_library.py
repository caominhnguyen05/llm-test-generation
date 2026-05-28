import shutil
import subprocess
import zipfile
from pathlib import Path

import requests

from pipeline.config import LibConfig
from library_prep.pom import create_minimal_pom

MAVEN_CENTRAL_URL = "https://repo1.maven.org/maven2"


def artifact_filename(config: LibConfig, suffix: str = "") -> str:
    return f"{config.artifact_id}-{config.version}{suffix}.jar"


def artifact_path(config: LibConfig, suffix: str = "") -> Path:
    return config.library_path / "artifacts" / artifact_filename(config, suffix)


def artifact_url(config: LibConfig, suffix: str = "") -> str:
    group_path = config.group_id.replace(".", "/")
    filename = artifact_filename(config, suffix)

    return (
        f"{MAVEN_CENTRAL_URL}/"
        f"{group_path}/"
        f"{config.artifact_id}/"
        f"{config.version}/"
        f"{filename}"
    )


def delete_library(config: LibConfig, reason: str) -> None:
    if config.library_path.exists():
        shutil.rmtree(config.library_path)
        print(f"Deleted {config.library_path}: {reason}")


def download_library_jars(config: LibConfig) -> bool:
    artifacts = ["", "-sources"]
    downloads: list[tuple[Path, bytes]] = []

    for suffix in artifacts:
        url = artifact_url(config, suffix)
        path = artifact_path(config, suffix)

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"Failed to download {url}: {exc}")
            return False

        downloads.append((path, response.content))

    for path, content in downloads:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    return True


def extract_source_jar(config: LibConfig) -> bool:
    source_jar = artifact_path(config, "-sources")
    prompt_sources = config.source_folder

    try:
        if prompt_sources.exists():
            shutil.rmtree(prompt_sources)

        prompt_sources.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(source_jar) as jar:
            jar.extractall(prompt_sources)

        if not any(prompt_sources.rglob("*.java")):
            return False

        shutil.rmtree(prompt_sources / "META-INF", ignore_errors=True)
        return True

    except (OSError, zipfile.BadZipFile) as exc:
        print(f"Source extraction failed: {source_jar} -> {exc}")
        delete_library(config, "source jar extraction failed")
        return False


def compile_library(config: LibConfig) -> bool:
    result = subprocess.run(
        ["mvn.cmd", "-q", "test-compile"],
        cwd=config.library_path,
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode == 0:
        return True

    output = result.stdout + "\n" + result.stderr

    print(f"Compile failed: {config.library}")
    print(output.strip()[-4000:])

    return False


def prepare_library(config: LibConfig) -> bool:
    print(f"\nPreparing library: {config.library}")

    if config.library_path.exists():
        print(f"Already prepared.")
        return True

    steps = [
        ("- Downloading artifacts", download_library_jars),
        ("- Extracting source jar", extract_source_jar),
        ("- Creating minimal pom.xml", create_minimal_pom),
        ("- Compiling library", compile_library),
    ]

    for message, step in steps:
        print(f"{message}...")
        if not step(config):
            print(f"Preparation failed during: {message}")
            delete_library(config, "preparation failed")
            return False

    print(f"Prepared library: {config.library}")
    return True