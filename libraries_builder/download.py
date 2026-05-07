import csv
import requests
import subprocess
from pathlib import Path
import zipfile
import shutil
import xml.etree.ElementTree as ET


CSV_FILE = "csv_data/evosuite_results_small.csv"
OUTPUT_DIR = Path("libraries_small")
MAVEN_CENTRAL = "https://repo1.maven.org/maven2"
POM_NS = "http://maven.apache.org/POM/4.0.0"
ET.register_namespace("", POM_NS)

# =========================
# HELPERS
# =========================
def build_url(group_id, artifact_id, version):
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

def find_extracted_pom(extracted_src):
    maven_poms = list(extracted_src.glob("META-INF/maven/**/pom.xml"))
    if maven_poms:
        return maven_poms[0]

    poms = list(extracted_src.rglob("pom.xml"))
    return poms[0] if poms else None

def child(parent, name):
    return parent.find(pom_tag(name))

def get_or_create_child(parent, name):
    existing = child(parent, name)
    if existing is not None:
        return existing

    created = ET.SubElement(parent, pom_tag(name))
    return created

def has_dependency(dependencies, group_id, artifact_id):
    for dependency in dependencies.findall(pom_tag("dependency")):
        group = child(dependency, "groupId")
        artifact = child(dependency, "artifactId")
        if group is not None and artifact is not None:
            if group.text == group_id and artifact.text == artifact_id:
                return True
    return False

def add_dependency(dependencies, group_id, artifact_id, version, scope="test"):
    if has_dependency(dependencies, group_id, artifact_id):
        return

    dependency = ET.SubElement(dependencies, pom_tag("dependency"))
    ET.SubElement(dependency, pom_tag("groupId")).text = group_id
    ET.SubElement(dependency, pom_tag("artifactId")).text = artifact_id
    ET.SubElement(dependency, pom_tag("version")).text = version
    ET.SubElement(dependency, pom_tag("scope")).text = scope

def has_plugin(plugins, group_id, artifact_id):
    for plugin in plugins.findall(pom_tag("plugin")):
        group = child(plugin, "groupId")
        artifact = child(plugin, "artifactId")
        if group is not None and artifact is not None:
            if group.text == group_id and artifact.text == artifact_id:
                return True
    return False

def add_jacoco_plugin(plugins):
    group_id = "org.jacoco"
    artifact_id = "jacoco-maven-plugin"
    if has_plugin(plugins, group_id, artifact_id):
        return

    plugin = ET.SubElement(plugins, pom_tag("plugin"))
    ET.SubElement(plugin, pom_tag("groupId")).text = group_id
    ET.SubElement(plugin, pom_tag("artifactId")).text = artifact_id
    ET.SubElement(plugin, pom_tag("version")).text = "0.8.12"

    executions = ET.SubElement(plugin, pom_tag("executions"))
    prepare_agent = ET.SubElement(executions, pom_tag("execution"))
    goals = ET.SubElement(prepare_agent, pom_tag("goals"))
    ET.SubElement(goals, pom_tag("goal")).text = "prepare-agent"

    report = ET.SubElement(executions, pom_tag("execution"))
    ET.SubElement(report, pom_tag("id")).text = "report"
    ET.SubElement(report, pom_tag("phase")).text = "test"
    report_goals = ET.SubElement(report, pom_tag("goals"))
    ET.SubElement(report_goals, pom_tag("goal")).text = "report"

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

    properties = ET.SubElement(project, pom_tag("properties"))
    ET.SubElement(properties, pom_tag("maven.compiler.source")).text = "8"
    ET.SubElement(properties, pom_tag("maven.compiler.target")).text = "8"
    ET.SubElement(properties, pom_tag("project.build.sourceEncoding")).text = "UTF-8"

    dependencies = ET.SubElement(project, pom_tag("dependencies"))
    add_dependency(dependencies, "junit", "junit", "4.13.2")
    add_dependency(dependencies, "org.mockito", "mockito-core", "4.11.0")

    build = ET.SubElement(project, pom_tag("build"))
    plugins = ET.SubElement(build, pom_tag("plugins"))

    compiler = ET.SubElement(plugins, pom_tag("plugin"))
    ET.SubElement(compiler, pom_tag("groupId")).text = "org.apache.maven.plugins"
    ET.SubElement(compiler, pom_tag("artifactId")).text = "maven-compiler-plugin"
    ET.SubElement(compiler, pom_tag("version")).text = "3.11.0"

    configuration = ET.SubElement(compiler, pom_tag("configuration"))
    ET.SubElement(configuration, pom_tag("source")).text = "8"
    ET.SubElement(configuration, pom_tag("target")).text = "8"

    surefire = ET.SubElement(plugins, pom_tag("plugin"))
    ET.SubElement(surefire, pom_tag("groupId")).text = "org.apache.maven.plugins"
    ET.SubElement(surefire, pom_tag("artifactId")).text = "maven-surefire-plugin"
    ET.SubElement(surefire, pom_tag("version")).text = "3.2.5"

    add_jacoco_plugin(plugins)

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

    properties = get_or_create_child(root, "properties")
    set_text_child(properties, "maven.compiler.source", "8")
    set_text_child(properties, "maven.compiler.target", "8")
    set_text_child(properties, "project.build.sourceEncoding", "UTF-8")

    dependencies = get_or_create_child(root, "dependencies")
    add_dependency(dependencies, "junit", "junit", "4.13.2")
    add_dependency(dependencies, "org.mockito", "mockito-core", "4.11.0")

    build = get_or_create_child(root, "build")
    plugins = get_or_create_child(build, "plugins")

    add_jacoco_plugin(plugins)

    if not has_plugin(plugins, "org.apache.maven.plugins", "maven-compiler-plugin"):
        compiler = ET.SubElement(plugins, pom_tag("plugin"))
        ET.SubElement(compiler, pom_tag("groupId")).text = "org.apache.maven.plugins"
        ET.SubElement(compiler, pom_tag("artifactId")).text = "maven-compiler-plugin"
        ET.SubElement(compiler, pom_tag("version")).text = "3.11.0"

        configuration = ET.SubElement(compiler, pom_tag("configuration"))
        ET.SubElement(configuration, pom_tag("source")).text = "8"
        ET.SubElement(configuration, pom_tag("target")).text = "8"

    if not has_plugin(plugins, "org.apache.maven.plugins", "maven-surefire-plugin"):
        surefire = ET.SubElement(plugins, pom_tag("plugin"))
        ET.SubElement(surefire, pom_tag("groupId")).text = "org.apache.maven.plugins"
        ET.SubElement(surefire, pom_tag("artifactId")).text = "maven-surefire-plugin"
        ET.SubElement(surefire, pom_tag("version")).text = "3.2.5"

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

def compile_library(base_dir: Path) -> tuple[bool, str]:
    command = [
        "mvn.cmd",
        "-q",
        "compile",
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

            url, filename = build_url(group_id, artifact_id, version)

            lib_dir = OUTPUT_DIR / f"{artifact_id}-{version}"
            lib_dir.mkdir(exist_ok=True)

            jar_path = lib_dir / filename

            # Download
            if not jar_path.exists():
                success = download_file(url, jar_path)
                if not success:
                    delete_library(lib_dir, "source jar download failed")
                    continue
                print(f"Downloaded: {group_id}:{artifact_id}:{version}")
            else:
                print(f"Already downloaded: {group_id}:{artifact_id}:{version}")

            # Extract
            extract_dir = lib_dir / "extracted"
            if not extract_dir.exists():
                extract_dir.mkdir()
                ok = extract_jar(jar_path, extract_dir)
                if not ok:
                    delete_library(lib_dir, "source jar extraction failed")
                    continue

            # Create Maven project
            create_maven_project(lib_dir, group_id, artifact_id, version)

            # Compile before keeping the library
            success, output = compile_library(lib_dir)
            if success:
                print(f"Compile success: {group_id}:{artifact_id}:{version}")
            else:
                print(f"Compile failed: {group_id}:{artifact_id}:{version}")
                print(output.strip()[-3000:])
                delete_library(lib_dir, "library does not compile")

    print("\nAll done!")

if __name__ == "__main__":
    main()
