import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET

import requests

from pipeline.config import PipelineConfig
from library_prep.config import FIXED_DEPENDENCIES, FIXED_PLUGINS


MAVEN_CENTRAL_URL = "https://repo1.maven.org/maven2"
POM_NS = "http://maven.apache.org/POM/4.0.0"
DEFAULT_JAVA_VERSION = "8"
COMPILER_PLUGIN_VERSION = "3.11.0"

ET.register_namespace("", POM_NS)


@dataclass(frozen=True)
class MavenArtifact:
    group_id: str
    artifact_id: str
    version: str

    @property
    def label(self) -> str:
        return f"{self.group_id}:{self.artifact_id}:{self.version}"

    @property
    def jar_name(self) -> str:
        return f"{self.artifact_id}-{self.version}.jar"

    @property
    def sources_jar_name(self) -> str:
        return f"{self.artifact_id}-{self.version}-sources.jar"

    def maven_url(self, suffix: str) -> str:
        group_path = self.group_id.replace(".", "/")
        filename = f"{self.artifact_id}-{self.version}{suffix}"
        return f"{MAVEN_CENTRAL_URL}/{group_path}/{self.artifact_id}/{self.version}/{filename}"


def tag(name: str) -> str:
    return f"{{{POM_NS}}}{name}"


def set_text(parent: ET.Element, name: str, value: str) -> ET.Element:
    element = ET.SubElement(parent, tag(name))
    element.text = value
    return element


def parse_pom_block(xml: str) -> ET.Element:
    return ET.fromstring(f'<snippet xmlns="{POM_NS}">{xml}</snippet>')[0]


def artifact_jar_path(lib_dir: Path, artifact: MavenArtifact) -> Path:
    return lib_dir / "artifacts" / artifact.jar_name


def sources_jar_path(lib_dir: Path, artifact: MavenArtifact) -> Path:
    return lib_dir / "artifacts" / artifact.sources_jar_name


def delete_library(lib_dir: Path, reason: str) -> None:
    if lib_dir.exists():
        shutil.rmtree(lib_dir)
        print(f"Deleted {lib_dir}: {reason}")


def download_library_jars(artifact: MavenArtifact, lib_dir: Path) -> bool:
    jar_downloads = [
        (artifact.maven_url(".jar"), artifact_jar_path(lib_dir, artifact)),
        (artifact.maven_url("-sources.jar"), sources_jar_path(lib_dir, artifact)),
    ]

    downloaded_files: list[tuple[Path, bytes]] = []

    for url, output_path in jar_downloads:
        try:
            response = requests.get(url, timeout=30)
            if response.status_code != 200:
                print(f"Failed ({response.status_code}): {url}")
                return False

            downloaded_files.append((output_path, response.content))

        except requests.RequestException as exc:
            print(f"Error downloading {url}: {exc}")
            return False

    for output_path, content in downloaded_files:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(content)

    print(f"Downloaded artifacts: {artifact.label}")
    return True


def extract_source_jar(lib_dir: Path, artifact: MavenArtifact) -> bool:
    source_jar = sources_jar_path(lib_dir, artifact)
    prompt_sources = lib_dir / "prompt_sources"

    try:
        if prompt_sources.exists():
            shutil.rmtree(prompt_sources)

        prompt_sources.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(source_jar) as jar:
            jar.extractall(prompt_sources)

        if not any(prompt_sources.rglob("*.java")):
            delete_library(lib_dir, "source jar contains no Java files")
            return False

        shutil.rmtree(prompt_sources / "META-INF", ignore_errors=True)
        return True

    except (OSError, zipfile.BadZipFile) as exc:
        print(f"Source extraction failed: {source_jar} -> {exc}")
        delete_library(lib_dir, "source jar extraction failed")
        return False


def create_minimal_pom(path: Path, artifact: MavenArtifact) -> None:
    project = ET.Element(tag("project"))
    project.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    project.set(
        "xsi:schemaLocation",
        "http://maven.apache.org/POM/4.0.0 "
        "http://maven.apache.org/xsd/maven-4.0.0.xsd",
    )

    for name, value in (
        ("modelVersion", "4.0.0"),
        ("groupId", "llm.generated.tests"),
        ("artifactId", f"{artifact.artifact_id}-llm-tests"),
        ("version", "1.0.0"),
        ("packaging", "jar"),
    ):
        set_text(project, name, value)

    properties = ET.SubElement(project, tag("properties"))
    set_text(properties, "argLine", "")
    set_text(properties, "maven.compiler.release", DEFAULT_JAVA_VERSION)
    set_text(properties, "project.build.sourceEncoding", "UTF-8")

    dependencies = ET.SubElement(project, tag("dependencies"))

    library_dependency = ET.SubElement(dependencies, tag("dependency"))
    set_text(library_dependency, "groupId", artifact.group_id)
    set_text(library_dependency, "artifactId", artifact.artifact_id)
    set_text(library_dependency, "version", artifact.version)

    for dependency_xml in FIXED_DEPENDENCIES:
        dependencies.append(parse_pom_block(dependency_xml))

    build = ET.SubElement(project, tag("build"))
    set_text(build, "testSourceDirectory", "src/test/java")

    plugins = ET.SubElement(build, tag("plugins"))

    compiler_plugin = ET.SubElement(plugins, tag("plugin"))
    set_text(compiler_plugin, "groupId", "org.apache.maven.plugins")
    set_text(compiler_plugin, "artifactId", "maven-compiler-plugin")
    set_text(compiler_plugin, "version", COMPILER_PLUGIN_VERSION)

    compiler_config = ET.SubElement(compiler_plugin, tag("configuration"))
    set_text(compiler_config, "release", DEFAULT_JAVA_VERSION)

    for plugin_xml in FIXED_PLUGINS:
        plugins.append(parse_pom_block(plugin_xml))

    tree = ET.ElementTree(project)
    ET.indent(tree, space="    ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def compile_library(lib_dir: Path, artifact: MavenArtifact) -> bool:
    result = subprocess.run(
        ["mvn.cmd", "-q", "test-compile"],
        cwd=lib_dir,
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode == 0:
        print(f"Compile success: {artifact.label}")
        return True

    output = result.stdout + "\n" + result.stderr

    print(f"Compile failed: {artifact.label}")
    print(output.strip()[-4000:])

    delete_library(lib_dir, "library failed to compile")
    return False


def prepare_library(config: PipelineConfig) -> bool:
    artifact = MavenArtifact(config.group_id, config.artifact_id, config.version)
    lib_dir = config.library_path

    print(f"\nProcessing: {artifact.label}")

    if lib_dir.exists():
        print(f"Already prepared: {artifact.label}")
        return True

    if not download_library_jars(artifact, lib_dir):
        return False

    if not extract_source_jar(lib_dir, artifact):
        return False

    create_minimal_pom(lib_dir / "pom.xml", artifact)

    return compile_library(lib_dir, artifact)