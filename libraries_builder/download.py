import csv
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import xml.etree.ElementTree as ET
import requests

from config import (FIXED_DEPENDENCIES, 
                    FIXED_PLUGINS)


CSV_FILE = Path("csv_data/evosuite_results_one.csv")
OUTPUT_DIR = Path("libraries_test")
MAVEN_CENTRAL = "https://repo1.maven.org/maven2"

POM_NS = "http://maven.apache.org/POM/4.0.0"
DEFAULT_JAVA_VERSION = "8"
MIN_JAVA_VERSION = 8
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

    def maven_url(self, suffix: str) -> tuple[str, str]:
        group_path = self.group_id.replace(".", "/")
        filename = f"{self.artifact_id}-{self.version}{suffix}"
        url = f"{MAVEN_CENTRAL}/{group_path}/{self.artifact_id}/{self.version}/{filename}"
        return url, filename


# ---------- basic file steps ----------

def download_file(url: str, output_path: Path) -> bool:
    try:
        response = requests.get(url, timeout=20)
        if response.status_code != 200:
            print(f"Failed ({response.status_code}): {url}")
            return False
        output_path.write_bytes(response.content)
        return True
    except requests.RequestException as exc:
        print(f"Error: {url} -> {exc}")
        return False


def extract_jar(jar_path: Path, extract_to: Path) -> bool:
    try:
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


def is_prepared(lib_dir: Path) -> bool:
    return (lib_dir / "pom.xml").exists() and (lib_dir / "src/main/java").exists()


# ---------- POM helpers ----------

def tag(name: str) -> str:
    return f"{{{POM_NS}}}{name}"


def child(parent: ET.Element, name: str) -> Optional[ET.Element]:
    return parent.find(tag(name))


def child_text(parent: ET.Element, name: str) -> Optional[str]:
    elem = child(parent, name)
    return elem.text.strip() if elem is not None and elem.text else None


def ensure_child(parent: ET.Element, name: str) -> ET.Element:
    elem = child(parent, name)
    if elem is None:
        elem = ET.SubElement(parent, tag(name))
    return elem


def set_text(parent: ET.Element, name: str, value: str) -> ET.Element:
    elem = ensure_child(parent, name)
    elem.text = value
    return elem


def remove_children(parent: ET.Element, *names: str) -> None:
    for name in names:
        for elem in parent.findall(tag(name)):
            parent.remove(elem)


def parse_pom_block(xml: str) -> ET.Element:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    return ET.fromstring(f'<snippet xmlns="{POM_NS}">{xml}</snippet>', parser=parser)[0]


def coordinates(elem: ET.Element, default_group: Optional[str] = None) -> tuple[str, str]:
    group_id = child_text(elem, "groupId") or default_group
    artifact_id = child_text(elem, "artifactId")
    if not group_id or not artifact_id:
        raise ValueError("Maven block must have groupId and artifactId")
    return group_id, artifact_id


def same_coordinates(elem: ET.Element, group_id: str, artifact_id: str, default_group: Optional[str] = None) -> bool:
    try:
        elem_group, elem_artifact = coordinates(elem, default_group)
    except ValueError:
        return False
    return elem_group == group_id and elem_artifact == artifact_id


def replace_maven_block(parent: ET.Element, tag_name: str, xml: str, default_group: Optional[str] = None) -> None:
    new_block = parse_pom_block(xml)
    group_id, artifact_id = coordinates(new_block, default_group)

    for existing in parent.findall(tag(tag_name)):
        if same_coordinates(existing, group_id, artifact_id, default_group):
            parent.remove(existing)
            break

    parent.append(new_block)


# ---------- POM normalization ----------

def normalize_java_version(value: str) -> str:
    value = value.strip()
    if value.startswith("${") and value.endswith("}"):
        return DEFAULT_JAVA_VERSION
    if value.startswith("1."):
        value = value.split(".", 1)[1]

    try:
        version = int(value)
    except ValueError:
        return DEFAULT_JAVA_VERSION

    return str(version) if version >= MIN_JAVA_VERSION else DEFAULT_JAVA_VERSION


def plugin_matches(plugin: ET.Element, artifact_id: str, group_id: str = "org.apache.maven.plugins") -> bool:
    return same_coordinates(plugin, group_id, artifact_id, default_group="org.apache.maven.plugins")


def detect_java_version(root: ET.Element) -> Optional[str]:
    properties = child(root, "properties")
    if properties is not None:
        for name in (
            "maven.compiler.release",
            "maven.compiler.source",
            "maven.compiler.target",
            "maven.compile.source",
            "maven.compile.target",
        ):
            if value := child_text(properties, name):
                return value

    for plugin in root.iter(tag("plugin")):
        if not plugin_matches(plugin, "maven-compiler-plugin"):
            continue
        configuration = child(plugin, "configuration")
        if configuration is None:
            continue
        for name in ("release", "source", "target"):
            if value := child_text(configuration, name):
                return value

    return None


def configure_compiler_plugin(plugins: ET.Element, java_version: str) -> None:
    plugin = None
    for candidate in plugins.findall(tag("plugin")):
        if plugin_matches(candidate, "maven-compiler-plugin"):
            plugin = candidate
            break

    if plugin is None:
        plugin = ET.SubElement(plugins, tag("plugin"))
        set_text(plugin, "groupId", "org.apache.maven.plugins")
        set_text(plugin, "artifactId", "maven-compiler-plugin")

    set_text(plugin, "version", COMPILER_PLUGIN_VERSION)
    configuration = ensure_child(plugin, "configuration")
    remove_children(configuration, "source", "target")
    set_text(configuration, "release", java_version)


def normalize_test_pom(root: ET.Element) -> None:
    detected_java = detect_java_version(root)
    java_version = normalize_java_version(detected_java) if detected_java else DEFAULT_JAVA_VERSION

    properties = ensure_child(root, "properties")
    set_text(properties, "jacoco.argLine", "")
    set_text(properties, "maven.compiler.release", java_version)
    remove_children(
        properties,
        "maven.compiler.source",
        "maven.compiler.target",
        "maven.compile.source",
        "maven.compile.target",
    )

    dependencies = ensure_child(root, "dependencies")
    for dependency_xml in FIXED_DEPENDENCIES:
        replace_maven_block(dependencies, "dependency", dependency_xml)

    build = ensure_child(root, "build")
    set_text(build, "sourceDirectory", "src/main/java")
    set_text(build, "testSourceDirectory", "src/test/java")

    plugins = ensure_child(build, "plugins")
    configure_compiler_plugin(plugins, java_version)
    for plugin_xml in FIXED_PLUGINS:
        replace_maven_block(plugins, "plugin", plugin_xml, default_group="org.apache.maven.plugins")

    for plugin in root.iter(tag("plugin")):
        if plugin_matches(plugin, "maven-compiler-plugin"):
            configuration = ensure_child(plugin, "configuration")
            remove_children(configuration, "source", "target")
            set_text(plugin, "version", COMPILER_PLUGIN_VERSION)
            set_text(configuration, "release", java_version)


def write_pom(tree: ET.ElementTree, path: Path) -> None:
    ET.indent(tree, space="    ")
    tree.write(path, encoding="utf-8", xml_declaration=True)


def create_minimal_pom(path: Path, artifact: MavenArtifact) -> None:
    project = ET.Element(tag("project"))
    project.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    project.set(
        "xsi:schemaLocation",
        "http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd",
    )

    for name, value in (
        ("modelVersion", "4.0.0"),
        ("groupId", artifact.group_id),
        ("artifactId", artifact.artifact_id),
        ("version", artifact.version),
        ("packaging", "jar"),
    ):
        set_text(project, name, value)

    normalize_test_pom(project)
    write_pom(ET.ElementTree(project), path)


def prepare_pom(base_dir: Path, artifact: MavenArtifact) -> None:
    target_pom = base_dir / "pom.xml"
    pom_url, _ = artifact.maven_url(".pom")

    if not download_file(pom_url, target_pom):
        print(f"Could not download pom.xml from Maven Central. Creating minimal pom.xml: {target_pom}")
        create_minimal_pom(target_pom, artifact)
        return

    tree = ET.parse(target_pom)
    root = tree.getroot()
    has_parent = child(root, "parent") is not None

    set_text(root, "modelVersion", "4.0.0")
    if child(root, "groupId") is None and not has_parent:
        set_text(root, "groupId", artifact.group_id)
    if child(root, "artifactId") is None:
        set_text(root, "artifactId", artifact.artifact_id)
    if child(root, "version") is None and not has_parent:
        set_text(root, "version", artifact.version)
    if child(root, "packaging") is None:
        set_text(root, "packaging", "jar")

    normalize_test_pom(root)
    write_pom(tree, target_pom)


# ---------- named pipeline steps ----------

def step_download_sources(artifact: MavenArtifact, lib_dir: Path) -> Optional[Path]:
    url, filename = artifact.maven_url("-sources.jar")
    jar_path = lib_dir / filename
    if not download_file(url, jar_path):
        delete_library(lib_dir, "source jar download failed")
        return None
    print(f"Downloaded: {artifact.label}")
    return jar_path


def step_extract_sources(jar_path: Path, lib_dir: Path) -> Optional[Path]:
    extract_dir = lib_dir / "extracted"
    extract_dir.mkdir(exist_ok=True)

    if not extract_jar(jar_path, extract_dir):
        delete_library(lib_dir, "source jar extraction failed")
        return None
    if not any(extract_dir.rglob("*.java")):
        delete_library(lib_dir, "source jar contains no Java files")
        return None

    jar_path.unlink(missing_ok=True)
    return extract_dir


def step_create_maven_project(extract_dir: Path, lib_dir: Path, artifact: MavenArtifact) -> None:
    source_dir = lib_dir / "src/main/java"
    source_dir.mkdir(parents=True, exist_ok=True)

    for source_file in extract_dir.rglob("*.java"):
        target = source_dir / source_file.relative_to(extract_dir)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source_file, target)

    prepare_pom(lib_dir, artifact)
    shutil.rmtree(extract_dir)


def compile_library(base_dir: Path) -> tuple[bool, str]:
    result = subprocess.run(
        [
            "mvn.cmd",
            "-q",
            "test-compile",
            "-Drat.skip=true",
            "-Danimal.sniffer.skip=true",
        ],
        cwd=base_dir,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return result.returncode == 0, result.stdout + "\n" + result.stderr


def step_compile_with_fallback(lib_dir: Path, artifact: MavenArtifact) -> bool:
    success, output = compile_library(lib_dir)
    if success:
        print(f"Compile success: {artifact.label}")
        return True

    print(f"Compile failed: {artifact.label}")
    print(output.strip()[-4000:])

    print(f"Retrying with minimal pom.xml: {artifact.label}")
    create_minimal_pom(lib_dir / "pom.xml", artifact)

    success, output = compile_library(lib_dir)
    if success:
        print(f"Compile success with minimal pom.xml: {artifact.label}")
        return True

    print(f"Compile failed with minimal pom.xml: {artifact.label}")
    print(output.strip()[-4000:])
    delete_library(lib_dir, "library does not compile")
    return False


def prepare_library(artifact: MavenArtifact) -> bool:
    print(f"\nProcessing: {artifact.label}")

    lib_dir = artifact.output_dir
    lib_dir.mkdir(parents=True, exist_ok=True)

    if is_prepared(lib_dir):
        print(f"Already prepared: {artifact.label}")
        return False

    jar_path = step_download_sources(artifact, lib_dir)
    if jar_path is None:
        return False

    extract_dir = step_extract_sources(jar_path, lib_dir)
    if extract_dir is None:
        return False

    step_create_maven_project(extract_dir, lib_dir, artifact)
    return step_compile_with_fallback(lib_dir, artifact)


def read_artifacts(csv_file: Path) -> list[MavenArtifact]:
    with csv_file.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        print(reader.fieldnames)
        return [MavenArtifact(row["group_id"], row["artifact_id"], row["version"]) for row in reader]


def main() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    compiled_count = sum(1 for artifact in read_artifacts(CSV_FILE) if prepare_library(artifact))
    print(f"\nAll done! Successfully compiled {compiled_count} libraries.")


if __name__ == "__main__":
    main()
