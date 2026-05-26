import csv
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET

import requests

from config import FIXED_DEPENDENCIES, FIXED_PLUGINS


CSV_FILE = Path("csv_data/evosuite_results_one.csv")
OUTPUT_DIR = Path("libraries_test")
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
    def output_dir(self) -> Path:
        return OUTPUT_DIR / self.group_id / self.artifact_id / self.version

    @property
    def jar_name(self) -> str:
        return f"{self.artifact_id}-{self.version}.jar"

    @property
    def sources_jar_name(self) -> str:
        return f"{self.artifact_id}-{self.version}-sources.jar"

    def maven_url(self, suffix: str) -> tuple[str, str]:
        group_path = self.group_id.replace(".", "/")
        filename = f"{self.artifact_id}-{self.version}{suffix}"
        url = f"{MAVEN_CENTRAL_URL}/{group_path}/{self.artifact_id}/{self.version}/{filename}"
        return url, filename


def tag(name: str) -> str:
    return f"{{{POM_NS}}}{name}"


def set_text(parent: ET.Element, name: str, value: str) -> ET.Element:
    elem = ET.SubElement(parent, tag(name))
    elem.text = value
    return elem


def parse_pom_block(xml: str) -> ET.Element:
    return ET.fromstring(f'<snippet xmlns="{POM_NS}">{xml}</snippet>')[0]


def download_file(url: str, output_path: Path) -> bool:
    try:
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            print(f"Failed ({response.status_code}): {url}")
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        return True
    except requests.RequestException as exc:
        print(f"Error: {url} -> {exc}")
        return False


def extract_jar(jar_path: Path, extract_to: Path) -> bool:
    try:
        if extract_to.exists():
            shutil.rmtree(extract_to)
        extract_to.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(jar_path) as jar:
            jar.extractall(extract_to)
        return True
    except (OSError, zipfile.BadZipFile) as exc:
        print(f"Extraction failed: {jar_path} -> {exc}")
        return False


def delete_library(lib_dir: Path, reason: str) -> None:
    if lib_dir.exists():
        shutil.rmtree(lib_dir)
        print(f"Deleted {lib_dir}: {reason}")


def artifact_jar_path(lib_dir: Path, artifact: MavenArtifact) -> Path:
    return lib_dir / "artifacts" / artifact.jar_name


def sources_jar_path(lib_dir: Path, artifact: MavenArtifact) -> Path:
    return lib_dir / "artifacts" / artifact.sources_jar_name


def is_prepared(lib_dir: Path, artifact: MavenArtifact) -> bool:
    return (
        (lib_dir / "pom.xml").exists()
        and artifact_jar_path(lib_dir, artifact).exists()
        and sources_jar_path(lib_dir, artifact).exists()
        and (lib_dir / "prompt_sources").exists()
    )


def download_library_jars(artifact: MavenArtifact, lib_dir: Path) -> bool:
    downloads = [
        (*artifact.maven_url(".jar"), artifact_jar_path(lib_dir, artifact)),
        (*artifact.maven_url("-sources.jar"), sources_jar_path(lib_dir, artifact)),
    ]

    for url, _, output_path in downloads:
        if output_path.exists():
            continue
        if not download_file(url, output_path):
            delete_library(lib_dir, f"required artifact download failed: {url}")
            return False

    print(f"Downloaded artifacts: {artifact.label}")
    return True


def extract_source_jar(lib_dir: Path, artifact: MavenArtifact) -> bool:
    prompt_sources = lib_dir / "prompt_sources"
    if not extract_jar(sources_jar_path(lib_dir, artifact), prompt_sources):
        delete_library(lib_dir, "source jar extraction failed")
        return False

    if not any(prompt_sources.rglob("*.java")):
        delete_library(lib_dir, "source jar contains no Java files")
        return False

    shutil.rmtree(prompt_sources / "META-INF", ignore_errors=True)
    return True


def create_minimal_pom(path: Path, artifact: MavenArtifact) -> None:
    project = ET.Element(tag("project"))
    project.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    project.set(
        "xsi:schemaLocation",
        "http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd",
    )

    for name, value in (
        ("modelVersion", "4.0.0"),
        ("groupId", "llm.generated.tests"),
        ("artifactId", f"{artifact.artifact_id}-test"),
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

    ET.indent(ET.ElementTree(project), space="    ")
    ET.ElementTree(project).write(path, encoding="utf-8", xml_declaration=True)


def compile_library(lib_dir: Path, artifact: MavenArtifact) -> bool:
    result = subprocess.run(
        [
            "mvn.cmd",
            "-q",
            "test-compile",
        ],
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


def prepare_library(artifact: MavenArtifact) -> bool:
    print(f"\nProcessing: {artifact.label}")

    lib_dir = artifact.output_dir
    lib_dir.mkdir(parents=True, exist_ok=True)

    if is_prepared(lib_dir, artifact):
        print(f"Already prepared: {artifact.label}")
        return False

    if not download_library_jars(artifact, lib_dir):
        return False
    if not extract_source_jar(lib_dir, artifact):
        return False

    create_minimal_pom(lib_dir / "pom.xml", artifact)
    return compile_library(lib_dir, artifact)


def read_artifacts(csv_file: Path) -> list[MavenArtifact]:
    with csv_file.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        return [MavenArtifact(row["group_id"], row["artifact_id"], row["version"]) for row in reader]


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    compiled_count = sum(1 for artifact in read_artifacts(CSV_FILE) if prepare_library(artifact))
    print(f"\nAll done! Successfully prepared {compiled_count} libraries.")


if __name__ == "__main__":
    main()
