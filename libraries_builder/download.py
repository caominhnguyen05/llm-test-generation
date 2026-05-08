import csv
import requests
import subprocess
from pathlib import Path
import zipfile
import shutil
import xml.etree.ElementTree as ET


CSV_FILE = "csv_data/evosuite_results_small.csv"
OUTPUT_DIR = Path("libraries_initial")
MAVEN_CENTRAL = "https://repo1.maven.org/maven2"
POM_NS = "http://maven.apache.org/POM/4.0.0"
JAVA_VERSION = "8"
ET.register_namespace("", POM_NS)

# =========================
# HELPERS
# =========================
def build_source_url(group_id, artifact_id, version):
    group_path = group_id.replace(".", "/")
    filename = f"{artifact_id}-{version}-sources.jar"
    url = f"{MAVEN_CENTRAL}/{group_path}/{artifact_id}/{version}/{filename}"
    return url, filename

def build_pom_url(group_id: str, artifact_id: str, version: str) -> tuple[str, str]:
    group_path = group_id.replace(".", "/")
    filename = f"{artifact_id}-{version}.pom"
    url = f"{MAVEN_CENTRAL}/{group_path}/{artifact_id}/{version}/{filename}"
    return url, filename

def download_pom_from_maven_central(target_pom: Path, group_id: str, artifact_id: str, version: str) -> bool:
    url, _ = build_pom_url(group_id, artifact_id, version)
    return download_file(url, target_pom)

def download_file(url, output_path):
    try:
        r = requests.get(url, timeout=20)
        if r.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(r.content)
            return True
        else:
            print(f"Failed ({r.status_code}): {url}")
            return False
    except Exception as e:
        print(f"Error: {url} -> {e}")
        return False

def extract_jar(jar_path, extract_to):
    try:
        with zipfile.ZipFile(jar_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        return True
    except Exception as e:
        print(f"Extraction failed: {jar_path} -> {e}")
        return False

def pom_tag(name):
    return f"{{{POM_NS}}}{name}"

def child(parent, name):
    return parent.find(pom_tag(name))

def children(parent, name):
    return parent.findall(pom_tag(name))

def get_or_create_child(parent, name):
    existing = child(parent, name)
    if existing is not None:
        return existing

    created = ET.SubElement(parent, pom_tag(name))
    return created

def inserted_comment():
    return ET.Comment(" This element was inserted by download.py ")

def dependency_matches(dependency, group_id, artifact_id):
    group = child(dependency, "groupId")
    artifact = child(dependency, "artifactId")
    return group is not None and artifact is not None and group.text == group_id and artifact.text == artifact_id

def find_dependency(dependencies, group_id, artifact_id):
    for dependency in dependencies.findall(pom_tag("dependency")):
        if dependency_matches(dependency, group_id, artifact_id):
            return dependency
    return None

def has_dependency(dependencies, group_id, artifact_id):
    return find_dependency(dependencies, group_id, artifact_id) is not None

def add_or_update_dependency(dependencies, group_id, artifact_id, version, scope="test"):
    dependency = find_dependency(dependencies, group_id, artifact_id)
    if dependency is None:
        dependencies.append(inserted_comment())
        dependency = ET.SubElement(dependencies, pom_tag("dependency"))
        ET.SubElement(dependency, pom_tag("groupId")).text = group_id
        ET.SubElement(dependency, pom_tag("artifactId")).text = artifact_id

    set_text_child(dependency, "version", version)
    set_text_child(dependency, "scope", scope)

def add_dependency(dependencies, group_id, artifact_id, version, scope="test"):
    add_or_update_dependency(dependencies, group_id, artifact_id, version, scope)

def plugin_matches(plugin, group_id, artifact_id):
    group = child(plugin, "groupId")
    artifact = child(plugin, "artifactId")
    if artifact is None or artifact.text != artifact_id:
        return False
    if group is None or not group.text:
        return group_id == "org.apache.maven.plugins"
    return group.text == group_id

def find_plugin(plugins, group_id, artifact_id):
    for plugin in plugins.findall(pom_tag("plugin")):
        if plugin_matches(plugin, group_id, artifact_id):
            return plugin
    return None

def has_plugin(plugins, group_id, artifact_id):
    return find_plugin(plugins, group_id, artifact_id) is not None

def get_or_create_plugin(plugins, group_id, artifact_id):
    plugin = find_plugin(plugins, group_id, artifact_id)
    if plugin is None:
        plugins.append(inserted_comment())
        plugin = ET.SubElement(plugins, pom_tag("plugin"))
    set_text_child(plugin, "groupId", group_id)
    set_text_child(plugin, "artifactId", artifact_id)
    return plugin

def remove_children(parent, name):
    for elem in children(parent, name):
        parent.remove(elem)

def set_plugin_version(plugin, version):
    set_text_child(plugin, "version", version)

def configure_compiler_plugin(plugins):
    plugin = get_or_create_plugin(plugins, "org.apache.maven.plugins", "maven-compiler-plugin")
    set_plugin_version(plugin, "3.11.0")
    configuration = get_or_create_child(plugin, "configuration")
    set_text_child(configuration, "source", JAVA_VERSION)
    set_text_child(configuration, "target", JAVA_VERSION)
    # set_text_child(configuration, "encoding", "UTF-8")

def configure_existing_compiler_plugins(root):
    for plugin in root.iter(pom_tag("plugin")):
        if plugin_matches(plugin, "org.apache.maven.plugins", "maven-compiler-plugin"):
            set_plugin_version(plugin, "3.11.0")
            configuration = get_or_create_child(plugin, "configuration")
            set_text_child(configuration, "source", JAVA_VERSION)
            set_text_child(configuration, "target", JAVA_VERSION)
            # set_text_child(configuration, "encoding", "UTF-8")

def configure_surefire_plugin(plugins):
    plugin = get_or_create_plugin(plugins, "org.apache.maven.plugins", "maven-surefire-plugin")
    set_plugin_version(plugin, "3.2.5")
    remove_children(plugin, "configuration")
    remove_children(plugin, "dependencies")

    configuration = ET.SubElement(plugin, pom_tag("configuration"))
    ET.SubElement(configuration, pom_tag("argLine")).text = "@{jacoco.argLine}"
    includes = ET.SubElement(configuration, pom_tag("includes"))
    ET.SubElement(includes, pom_tag("include")).text = "**/*Test.java"

    dependencies = ET.SubElement(plugin, pom_tag("dependencies"))
    dependency = ET.SubElement(dependencies, pom_tag("dependency"))
    ET.SubElement(dependency, pom_tag("groupId")).text = "org.apache.maven.surefire"
    ET.SubElement(dependency, pom_tag("artifactId")).text = "surefire-junit4"
    ET.SubElement(dependency, pom_tag("version")).text = "3.2.5"

def configure_jacoco_plugin(plugins):
    plugin = get_or_create_plugin(plugins, "org.jacoco", "jacoco-maven-plugin")
    set_plugin_version(plugin, "0.8.12")
    remove_children(plugin, "configuration")
    remove_children(plugin, "executions")

    configuration = ET.SubElement(plugin, pom_tag("configuration"))
    ET.SubElement(configuration, pom_tag("propertyName")).text = "jacoco.argLine"
    excludes = ET.SubElement(configuration, pom_tag("excludes"))
    ET.SubElement(excludes, pom_tag("exclude")).text = "META-INF/versions/**"

    executions = ET.SubElement(plugin, pom_tag("executions"))
    prepare_agent = ET.SubElement(executions, pom_tag("execution"))
    ET.SubElement(prepare_agent, pom_tag("id")).text = "prepare-agent"
    goals = ET.SubElement(prepare_agent, pom_tag("goals"))
    ET.SubElement(goals, pom_tag("goal")).text = "prepare-agent"

    report = ET.SubElement(executions, pom_tag("execution"))
    ET.SubElement(report, pom_tag("id")).text = "report"
    ET.SubElement(report, pom_tag("phase")).text = "verify"
    report_goals = ET.SubElement(report, pom_tag("goals"))
    ET.SubElement(report_goals, pom_tag("goal")).text = "report"


def normalize_generated_test_pom(root):
    properties = get_or_create_child(root, "properties")
    # set_text_child(properties, "project.build.sourceEncoding", "UTF-8")
    set_text_child(properties, "jacoco.argLine", "")

    # Prevent old libraries from using source/target values unsupported by modern JDKs.
    set_text_child(properties, "maven.compiler.source", JAVA_VERSION)
    set_text_child(properties, "maven.compiler.target", JAVA_VERSION)
    set_text_child(properties, "maven.compile.source", JAVA_VERSION)
    set_text_child(properties, "maven.compile.target", JAVA_VERSION)

    dependencies = get_or_create_child(root, "dependencies")
    add_or_update_dependency(dependencies, "junit", "junit", "4.13.2")
    add_or_update_dependency(dependencies, "org.mockito", "mockito-core", "4.11.0")

    build = get_or_create_child(root, "build")
    plugins = get_or_create_child(build, "plugins")
    configure_compiler_plugin(plugins)
    configure_surefire_plugin(plugins)
    configure_jacoco_plugin(plugins)
    configure_existing_compiler_plugins(root)

def add_jacoco_plugin(plugins):
    configure_jacoco_plugin(plugins)

def set_text_child(parent, name, text):
    elem = get_or_create_child(parent, name)
    elem.text = text
    return elem


def create_minimal_pom(target_pom, group_id, artifact_id, version):
    project = ET.Element(pom_tag("project"))

    project.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    project.set(
        "xsi:schemaLocation",
        "http://maven.apache.org/POM/4.0.0 "
        "http://maven.apache.org/xsd/maven-4.0.0.xsd"
    )

    ET.SubElement(project, pom_tag("modelVersion")).text = "4.0.0"
    ET.SubElement(project, pom_tag("groupId")).text = group_id
    ET.SubElement(project, pom_tag("artifactId")).text = artifact_id
    ET.SubElement(project, pom_tag("version")).text = version
    ET.SubElement(project, pom_tag("packaging")).text = "jar"

    normalize_generated_test_pom(project)

    tree = ET.ElementTree(project)
    ET.indent(tree, space="    ")
    tree.write(target_pom, encoding="utf-8", xml_declaration=True)


def prepare_pom(base_dir, group_id, artifact_id, version):
    target_pom = base_dir / "pom.xml"

    if not download_pom_from_maven_central(target_pom, group_id, artifact_id, version):
        print(f"Could not download pom.xml from Maven Central. Creating minimal pom.xml: {target_pom}")
        create_minimal_pom(target_pom, group_id, artifact_id, version)
        return

    tree = ET.parse(target_pom)
    root = tree.getroot()

    # Ensure basic Maven coordinates exist
    set_text_child(root, "modelVersion", "4.0.0")

    if child(root, "groupId") is None and child(root, "parent") is None:
        set_text_child(root, "groupId", group_id)

    if child(root, "artifactId") is None:
        set_text_child(root, "artifactId", artifact_id)

    if child(root, "version") is None and child(root, "parent") is None:
        set_text_child(root, "version", version)

    packaging = child(root, "packaging")
    if packaging is None:
        set_text_child(root, "packaging", "jar")

    normalize_generated_test_pom(root)

    ET.indent(tree, space="    ")
    tree.write(target_pom, encoding="utf-8", xml_declaration=True)

def create_maven_project(base_dir, group_id, artifact_id, version):
    src_main = base_dir / "src/main/java"
    src_main.mkdir(parents=True, exist_ok=True)

    # Move extracted sources into Maven structure
    extracted_src = base_dir / "extracted"
    if extracted_src.exists():
        for file in extracted_src.rglob("*.java"):
            target = src_main / file.relative_to(extracted_src)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(file, target)

    prepare_pom(base_dir, group_id, artifact_id, version)

    if extracted_src.exists():
        shutil.rmtree(extracted_src)

def compile_library(base_dir: Path) -> tuple[bool, str]:
    command = [
        "mvn.cmd",
        "-q",
        "test-compile",
        "-Drat.skip=true",
        "-Danimal.sniffer.skip=true",
    ]
    result = subprocess.run(
        command,
        cwd=base_dir,
        capture_output=True,
        text=True,
        timeout=300,
    )
    output = result.stdout + "\n" + result.stderr
    return result.returncode == 0, output

def delete_library(lib_dir: Path, reason: str) -> None:
    if lib_dir.exists():
        shutil.rmtree(lib_dir)
        print(f"Deleted {lib_dir}: {reason}")

def delete_downloaded_jar(jar_path: Path) -> None:
    if jar_path.exists():
        jar_path.unlink()

def library_already_prepared(lib_dir: Path) -> bool:
    return (
        (lib_dir / "pom.xml").exists()
        and (lib_dir / "src/main/java").exists()
    )

# =========================
# MAIN
# =========================
def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    with open(CSV_FILE, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        print(reader.fieldnames)

        for row in reader:
            group_id = row["group_id"]
            artifact_id = row["artifact_id"]
            version = row["version"]

            print(f"\nProcessing: {group_id}:{artifact_id}:{version}")

            url, filename = build_source_url(group_id, artifact_id, version)

            lib_dir = OUTPUT_DIR / group_id / artifact_id / version
            lib_dir.mkdir(parents=True, exist_ok=True)

            if library_already_prepared(lib_dir):
                print(f"Already prepared: {group_id}:{artifact_id}:{version}")
                continue

            jar_path = lib_dir / filename

            success = download_file(url, jar_path)
            if not success:
                delete_library(lib_dir, "source jar download failed")
                continue

            print(f"Downloaded: {group_id}:{artifact_id}:{version}")

            extract_dir = lib_dir / "extracted"
            extract_dir.mkdir(exist_ok=True)

            ok = extract_jar(jar_path, extract_dir)
            if not ok:
                delete_library(lib_dir, "source jar extraction failed")
                continue

            delete_downloaded_jar(jar_path)

            create_maven_project(lib_dir, group_id, artifact_id, version)

            success, output = compile_library(lib_dir)
            if success:
                print(f"Compile success: {group_id}:{artifact_id}:{version}")
            else:
                print(f"Compile failed: {group_id}:{artifact_id}:{version}")
                print(output.strip()[-4000:])
                delete_library(lib_dir, "library does not compile")

    print("\nAll done!")

if __name__ == "__main__":
    main()
