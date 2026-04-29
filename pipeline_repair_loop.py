from ollama import chat
from pathlib import Path
import json
import re
import subprocess

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

MAX_REPAIR_ATTEMPTS = 3

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

def enforce_package(test_code, package_name):
    if f"package {package_name};" not in test_code:
        return f"package {package_name};\n\n" + test_code
    return test_code

# =========================
# MAVEN / LLM HELPERS
# =========================
def call_llm_stream(prompt):
    """Handles the streaming API call to Ollama and returns the full output."""
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
    return llm_output

def run_maven_test():
    """Runs Maven for the specific test class and captures the output."""
    print(f"\n⚙️ Running Maven tests for {TARGET_CLASS}Test...")
    command = ["mvn", "test", f"-Dtest={TARGET_CLASS}Test"]
    
    result = subprocess.run(
        command, 
        cwd=MAVEN_PROJECT, 
        capture_output=True, 
        text=True
    )
    
    if result.returncode == 0:
        return True, ""
    else:
        # Extract last 3000 chars to avoid blowing up the LLM's context window
        error_output = result.stdout + "\n" + result.stderr
        return False, error_output[-3000:]

def get_repair_prompt(test_code, error_output):
    """Builds the prompt used for repairing failing tests."""
    return f"""
    The JUnit 4 test class you generated for `{TARGET_CLASS}` failed to compile or run.

    Here is the failing test code:
    ```java
    {test_code}
    Here is the Maven error output:
    code
    Text
    {error_output}
    Please fix the test code to resolve these errors.
    Requirements:
    Output ONLY the complete, fixed raw Java code enclosed in a java ... block. No explanations.
    Maintain the package {TARGET_PACKAGE} and class name {TARGET_CLASS}Test.
    """
# =========================
# MAIN PIPELINE
# =========================
def main():
    if not TARGET_JAVA_FILE.exists():
        print(f"Error: {TARGET_JAVA_FILE} not found.")
        return
    
    source_code = read_file(TARGET_JAVA_FILE)
    print(f"Loaded {TARGET_JAVA_FILE}.")

    # 1. Build the Initial Prompt
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

    # 2. Initial Generation
    print(f"\n[Attempt 0] Asking Ollama ({OLLAMA_MODEL}) to generate tests...")
    llm_output = call_llm_stream(prompt)

    test_code = extract_java_code(llm_output)
    test_code = enforce_package(test_code, TARGET_PACKAGE)
    write_file(OUTPUT_TEST_FILE, test_code)
    print(f"Initial test saved to {OUTPUT_TEST_FILE}")

    # 3. Compilation & Repair Loop
    for attempt in range(MAX_REPAIR_ATTEMPTS + 1):
        # Run Maven
        success, error_output = run_maven_test()
        
        if success:
            print(f"✅ SUCCESS! Test compiled and passed on Attempt {attempt}!")
            return  # Exit the script, we are done!
            
        # If it fails, check if we have repair attempts left
        if attempt < MAX_REPAIR_ATTEMPTS:
            print(f"❌ FAILED. Initiating repair loop {attempt + 1}/{MAX_REPAIR_ATTEMPTS}...")
            
            repair_prompt = get_repair_prompt(test_code, error_output)
            print(f"\nAsking Ollama to repair the code...")
            
            llm_output = call_llm_stream(repair_prompt)
            test_code = extract_java_code(llm_output)
            test_code = enforce_package(test_code, TARGET_PACKAGE)
            
            write_file(OUTPUT_TEST_FILE, test_code)
            print(f"Repaired test saved to {OUTPUT_TEST_FILE}")
        else:
            print(f"🚨 FAILURE. Max repair attempts ({MAX_REPAIR_ATTEMPTS}) reached. Test still fails.")
if __name__ == "__main__":
    main()