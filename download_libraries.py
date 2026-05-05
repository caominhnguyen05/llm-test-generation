import csv
import requests
from pathlib import Path
import zipfile
import shutil
import xml.etree.ElementTree as ET

# =========================
# CONFIG
# =========================
CSV_FILE = "evosuite_results_small.csv"
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

def prepare_pom_from_sources(base_dir, extracted_src):
    source_pom = find_extracted_pom(extracted_src)
    if source_pom is None:
        print(f"No pom.xml found in extracted sources: {extracted_src}")
        return

    target_pom = base_dir / "pom.xml"
    shutil.copy(source_pom, target_pom)

    tree = ET.parse(target_pom)
    root = tree.getroot()

    dependencies = get_or_create_child(root, "dependencies")
    add_dependency(dependencies, "junit", "junit", "4.13.2")
    add_dependency(dependencies, "org.mockito", "mockito-core", "4.11.0")

    build = get_or_create_child(root, "build")
    plugins = get_or_create_child(build, "plugins")
    add_jacoco_plugin(plugins)

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

    prepare_pom_from_sources(base_dir, extracted_src)

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
                    continue

            # Create Maven project
            create_maven_project(lib_dir, group_id, artifact_id, version)

    print("\nAll done!")

if __name__ == "__main__":
    main()
