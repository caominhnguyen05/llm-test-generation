from ollama import chat
from pathlib import Path
import json
import re

# =========================
# CONFIG
# =========================
OLLAMA_MODEL = "qwen2.5-coder:7b"

TARGET_PACKAGE = "org.apache.commons.lang3"
TARGET_CLASS = "CharSetUtils"

PROJECT_PATH = Path("libraries/commons-lang3-3.12.0-sources")
TARGET_JAVA_FILE = PROJECT_PATH / TARGET_PACKAGE.replace(".", "/") / f"{TARGET_CLASS}.java"

MAVEN_PROJECT = Path("test-generator")
OUTPUT_TEST_FILE = MAVEN_PROJECT / "src/test/java" / TARGET_PACKAGE.replace(".", "/") / f"{TARGET_CLASS}Test.java"

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
        
    source_code = read_file(TARGET_JAVA_FILE)
    print(f"Loaded {TARGET_JAVA_FILE}.")

    # Build the STRUCTURED prompt
    prompt = f"""
    Write a complete JUnit 4 test class for the Java source provided below. Maximize line and branch coverage,
    and make sure the test class compiles and runs without errors.

    Requirements:
    1. Package: The test MUST belong to the package `{TARGET_PACKAGE}`.
    2. Class Name: The test MUST be named `{TARGET_CLASS}Test` and be declared `public`.
    3. Imports: Include all necessary imports (e.g., JUnit annotations, assertions).
    4. Test Methods: Each test method MUST be annotated with @Test
    5. Coverage: Write distinct test cases for standard behavior, boundary values, and edge cases (e.g., null inputs) to maximize branch coverage.
    6. Output ONLY the raw Java code enclosed in a ```java ... ``` block. No explanations.

    Source Code:
    ```java
    {source_code}
    ```
    """
    # prompt = "Write Java solution for the Two Sum Leetcode problem. The solution should be a complete Java class named TwoSum with a method twoSum that takes an array of integers and a target integer, and returns the indices of the two numbers that add up to the target. The code should be enclosed in a ```java ... ``` block."

    # Call Ollama via API - Use streaming responses
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

    # Sanity Check: Force package declaration if LLM forgot
    if f"package {TARGET_PACKAGE};" not in test_code:
        test_code = f"package {TARGET_PACKAGE};\n\n" + test_code
        
    write_file(OUTPUT_TEST_FILE, test_code)
    print(f"Done! Test saved to {OUTPUT_TEST_FILE}")

if __name__ == "__main__":
    main()