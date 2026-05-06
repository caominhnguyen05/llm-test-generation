from ollama import chat
from pathlib import Path
from ollama_models import get_model, list_models

# =========================
# CONFIG
# =========================
OLLAMA_MODEL = get_model("qwen_coder_small")

# Root folder containing selected Maven-style projects
LIBRARIES_ROOT = Path("selected_libraries")

# Pick library folder (manual OR random)
TARGET_LIBRARY = "commons-csv-1.8"
LIBRARY_PATH = LIBRARIES_ROOT / TARGET_LIBRARY

# Source root inside Maven project
SOURCE_ROOT = LIBRARY_PATH / "src/main/java"
TEST_ROOT = LIBRARY_PATH / "src/test/java"

# You manually select the file you want to test
TARGET_JAVA_FILE = SOURCE_ROOT / "org/apache/commons/csv/CSVRecord.java"


def extract_package_and_class(java_file: Path):
    rel_path = java_file.relative_to(SOURCE_ROOT).with_suffix("")
    parts = rel_path.parts

    class_name = parts[-1]
    package_name = ".".join(parts[:-1])

    return package_name, class_name

# =========================
# UTIL FUNCTIONS
# =========================
def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def extract_java_code(llm_output):
    if "```java" in llm_output:
        return llm_output.split("```java")[1].split("```")[0].strip()
    elif "```" in llm_output:
        return llm_output.split("```")[1].strip()
    return llm_output.strip()

# =========================
# MAIN PIPELINE
# =========================
def main():
    if not TARGET_JAVA_FILE.exists():
        print(f"Error: {TARGET_JAVA_FILE} not found.")
        return

    # Read source
    source_code = read_file(TARGET_JAVA_FILE)
    print(f"Loaded {TARGET_JAVA_FILE}.")

    # 🔥 derive package + class from file path
    TARGET_PACKAGE, TARGET_CLASS = extract_package_and_class(TARGET_JAVA_FILE)

    print(f"Package: {TARGET_PACKAGE}")
    print(f"Class: {TARGET_CLASS}")

    # ✅ correct Maven-style output location
    OUTPUT_TEST_FILE = (
        TEST_ROOT /
        TARGET_PACKAGE.replace(".", "/") /
        f"{TARGET_CLASS}Test.java"
    )

    OUTPUT_TEST_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Build prompt
    prompt = f"""
    Write a complete JUnit 4 test class covering the functionality of the Java library class provided below. Make sure the test follows correct syntax and compiles without errors.
    Maximize code coverage by including tests for normal cases, edge cases, and error handling.
    If you use any classes in your test code, include the necessary import statements.

    Follow these requirements:
    1. Package: The test MUST belong to the package `{TARGET_PACKAGE}`.
    2. Class Name: The test MUST be named `{TARGET_CLASS}Test` and be declared `public`.
    3. Imports: Include all necessary imports (e.g., JUnit annotations, assertions).
    4. Test Methods: Each test method MUST be annotated with @Test
    5. Coverage: Write distinct test cases for standard behavior, boundary values, and edge cases (e.g., null inputs).
    6. Output ONLY the raw Java code enclosed in a ```java ... ``` block. No explanations.

    Source Code:
    ```java
    {source_code}
    ```
    """

    print(f"Asking Ollama ({OLLAMA_MODEL}) to generate tests...")

    stream = chat(
        model=OLLAMA_MODEL,
        messages=[{'role': 'user', 'content': prompt}],
        stream=True,
    )

    llm_output = ""
    for chunk in stream:
        token = chunk['message']['content']
        print(token, end='', flush=True)
        llm_output += token

    print("\n\nGeneration complete.\n")

    # Extract Java code
    test_code = extract_java_code(llm_output)

    # Ensure correct package
    if f"package {TARGET_PACKAGE};" not in test_code:
        test_code = f"package {TARGET_PACKAGE};\n\n" + test_code

    # 💾 Save in correct mirrored folder
    write_file(OUTPUT_TEST_FILE, test_code)
    print(f"Done! Test saved to {OUTPUT_TEST_FILE}")

if __name__ == "__main__":
    main()