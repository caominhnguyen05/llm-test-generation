import ollama
from pathlib import Path
import json

# =========================
# CONFIG
# =========================
OLLAMA_MODEL = "deepseek-coder:6.7b"

PROJECT_PATH = Path("libraries/commons-lang3-3.12.0-sources")
TARGET_JAVA_FILE = PROJECT_PATH / "org/apache/commons/lang3/BitField.java"

MAVEN_PROJECT = Path("test-generator")

OUTPUT_TEST_FILE = MAVEN_PROJECT / "src/test/java/org/apache/commons/lang3/BitFieldTest.java"

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
    """Extracts code from markdown blocks (```java ... ```)"""
    if "```java" in llm_output:
        return llm_output.split("```java")[1].split("```")[0].strip()
    elif "```" in llm_output:
        return llm_output.split("```")[1].strip()
    return llm_output.strip()

# =========================
# MAIN PIPELINE
# =========================
def main():
    # 1. Read the source code
    if not TARGET_JAVA_FILE.exists():
        print(f"Error: {TARGET_JAVA_FILE} not found. Please create it first.")
        return
        
    source_code = read_file(TARGET_JAVA_FILE)
    print(f"Loaded {TARGET_JAVA_FILE}.")

    # 2. Build the prompt
    prompt = f"""
    You are an expert Java software testing engineer. Your task is to write a comprehensive JUnit 4 test class for the provided Java class.

    Requirements for the test class:
    - Include necessary imports
    - Use @Test annotations
    - Only output Java code

    Java class:
    ```java
    {source_code}
    ```

    """

    # 3. Call Ollama via API
    print(f"Asking Ollama ({OLLAMA_MODEL}) to generate tests... (this may take a moment)")
    
    response = ollama.chat(model=OLLAMA_MODEL, messages=[
        {'role': 'user', 'content': prompt}
    ])

    print(json.dumps(response.model_dump(), indent=2))
    
    llm_output = response['message']['content']

    # 4. Clean and Save
    test_code = extract_java_code(llm_output)
    write_file(OUTPUT_TEST_FILE, test_code)
    
    print(f"Done! Test saved to {OUTPUT_TEST_FILE}")

if __name__ == "__main__":
    main()