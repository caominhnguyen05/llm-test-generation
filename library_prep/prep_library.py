import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

import requests

from pipeline.config import LibConfig
from pipeline.maven_runner import run_maven
from library_prep.pom import create_minimal_pom

MAVEN_CENTRAL_URL = "https://repo1.maven.org/maven2"


@dataclass(frozen=True)
class MavenArtifactFile:
    path: Path
    url: str


def maven_central_artifact_url(config: LibConfig, filename: str) -> str:
    group_path = config.group_id.replace(".", "/")
    return (
        f"{MAVEN_CENTRAL_URL}/"
        f"{group_path}/"
        f"{config.artifact_id}/"
        f"{config.version}/"
        f"{filename}"
    )


def artifact_file(config: LibConfig, filename: str) -> MavenArtifactFile:
    return MavenArtifactFile(
        path=config.library_path / "artifacts" / filename,
        url=maven_central_artifact_url(config, filename),
    )


def library_jar_artifact(config: LibConfig) -> MavenArtifactFile:
    return artifact_file(config, f"{config.artifact_id}-{config.version}.jar")


def source_jar_artifact(config: LibConfig) -> MavenArtifactFile:
    return artifact_file(config, f"{config.artifact_id}-{config.version}-sources.jar")


def pom_artifact(config: LibConfig) -> MavenArtifactFile:
    return artifact_file(config, f"{config.artifact_id}-{config.version}.pom")


def delete_library(config: LibConfig, reason: str) -> None:
    if config.library_path.exists():
        shutil.rmtree(config.library_path)
        print(f"Deleted {config.library_path}: {reason}")


def download_artifacts(config: LibConfig) -> bool:
    artifacts = [
        library_jar_artifact(config),
        source_jar_artifact(config),
        pom_artifact(config),
    ]
    downloads: list[tuple[Path, bytes]] = []

    for artifact in artifacts:
        try:
            response = requests.get(artifact.url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"Failed to download {artifact.url}: {exc}")
            return False

        downloads.append((artifact.path, response.content))

    for path, content in downloads:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    return True


def install_library_in_local_repo(config: LibConfig) -> bool:
    jar_artifact = library_jar_artifact(config)
    pom = pom_artifact(config)
    config.local_maven_repo.mkdir(parents=True, exist_ok=True)

    result = run_maven(
        [
            "-q",
            "org.apache.maven.plugins:maven-install-plugin:3.1.4:install-file",
            f"-Dfile={jar_artifact.path.resolve()}",
            f"-DpomFile={pom.path.resolve()}",
            f"-DlocalRepositoryPath={config.local_maven_repo.resolve()}",
        ],
        cwd=config.library_path,
    )
    return result.returncode == 0


def extract_source_jar(config: LibConfig) -> bool:
    source_jar = source_jar_artifact(config).path
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
    result = run_maven(
        ["-q", "test-compile"],
        cwd=config.library_path,
        local_repo=config.local_maven_repo,
    )

    if result.returncode == 0:
        return True

    print(f"Compile failed: {config.library}")
    print(f"{result.stdout}\n{result.stderr}")
    return False


def prepare_library(config: LibConfig) -> bool:
    print(f"\nPreparing library: {config.library}")

    if config.library_path.exists() and config.source_folder.exists():
        print(f"Already prepared.")
        return True

    steps = [
        ("- Downloading artifacts", download_artifacts),
        ("- Extracting source jar", extract_source_jar),
        ("- Installing artifact into isolated Maven repo", install_library_in_local_repo),
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