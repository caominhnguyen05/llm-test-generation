import csv
import requests
from pathlib import Path
import zipfile
import shutil

# =========================
# CONFIG
# =========================
CSV_FILE = "evosuite_results.csv"
OUTPUT_DIR = Path("selected_libraries")
MAVEN_CENTRAL = "https://repo1.maven.org/maven2"

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

    # Create pom.xml
    pom = f"""<project xmlns="http://maven.apache.org/POM/4.0.0"
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
http://maven.apache.org/xsd/maven-4.0.0.xsd">

<modelVersion>4.0.0</modelVersion>

<groupId>{group_id}</groupId>
<artifactId>{artifact_id}</artifactId>
<version>{version}</version>

<dependencies>
    <dependency>
        <groupId>junit</groupId>
        <artifactId>junit</artifactId>
        <version>4.13.2</version>
        <scope>test</scope>
    </dependency>
</dependencies>

<build>
    <plugins>
        <plugin>
            <groupId>org.apache.maven.plugins</groupId>
            <artifactId>maven-compiler-plugin</artifactId>
            <version>3.8.1</version>
            <configuration>
                <source>1.8</source>
                <target>1.8</target>
            </configuration>
        </plugin>
    </plugins>
</build>

</project>
"""
    (base_dir / "pom.xml").write_text(pom)

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