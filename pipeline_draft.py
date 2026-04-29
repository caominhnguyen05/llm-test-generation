import os
import subprocess
import json
from pathlib import Path

# =========================
# CONFIG
# =========================
OLLAMA_MODEL = "deepseek-coder:6.7b"
MAX_REPAIR_ATTEMPTS = 1

PROJECT_PATH = Path("libraries/commons-lang3-3.12.0-sources")  # path to one Maven project
CLASS_FILE = Path("org/apache/commons/lang3/StringUtils.java")  # target class

OUTPUT_DIR = Path("generated_tests")
OUTPUT_DIR.mkdir(exist_ok=True)

RESULTS_FILE = "results.json"


# =========================
# UTIL FUNCTIONS
# =========================

def run_command(cmd, cwd):
    result = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="ignore",
        shell=True  # Allows Windows to find mvn.cmd
    )
    return result.returncode, result.stdout, result.stderr


def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write_file(path, content):
    os.makedirs(path.parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# =========================
# LLM
# =========================

def generate_tests(prompt):
    result = subprocess.run(
        ["ollama", "run", OLLAMA_MODEL],
        input=prompt,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="ignore",
        shell=True  # Added for consistency on Windows
    )
    return result.stdout


def build_prompt(source_code, errors=None):
    prompt = f"""
Generate JUnit 4 unit tests for the following Java class.

Requirements:
- Include necessary imports
- Use @Test annotations
- Ensure tests compile and run

Java class:
{source_code}
"""
    if errors:
        prompt += f"\nFix the following errors:\n{errors}\n"

    return prompt


def clean_llm_output(output):
    # Remove markdown formatting if present
    if "```" in output:
        output = output.split("```")[-2]
    return output.strip()


# =========================
# PIPELINE STEPS
# =========================

def generate_and_save_test(source_code):
    prompt = build_prompt(source_code)
    output = generate_tests(prompt)
    cleaned = clean_llm_output(output)

    test_path = PROJECT_PATH / "src/test/java/generated/MyClassTest.java"
    write_file(test_path, cleaned)

    return test_path, prompt, cleaned


def compile_tests():
    return run_command(["mvn", "test-compile"], cwd=PROJECT_PATH)


def run_tests():
    return run_command(["mvn", "test"], cwd=PROJECT_PATH)


def repair_loop(source_code, test_path, initial_prompt):
    prompt = initial_prompt

    for attempt in range(MAX_REPAIR_ATTEMPTS):
        code, out, err = compile_tests()

        if code == 0:
            return True, attempt, ""

        print(f"[Repair Attempt {attempt+1}] Compilation failed")

        prompt = build_prompt(source_code, errors=err)
        output = generate_tests(prompt)
        cleaned = clean_llm_output(output)

        write_file(test_path, cleaned)

    return False, MAX_REPAIR_ATTEMPTS, err


# =========================
# MAIN PIPELINE
# =========================

def main():
    source_path = PROJECT_PATH / CLASS_FILE
    source_code = read_file(source_path)

    print("Generating initial test...")
    test_path, prompt, test_code = generate_and_save_test(source_code)

    print("Compiling tests...")
    success, attempts, error = repair_loop(source_code, test_path, prompt)

    result = {
        "compiled": success,
        "repair_attempts": attempts,
        "error": error if not success else None
    }

    if success:
        print("Running tests...")
        code, out, err = run_tests()
        result["tests_ran"] = (code == 0)
        result["test_output"] = out
        result["test_error"] = err
    else:
        print("Compilation failed after repairs.")

    # Save results
    with open(RESULTS_FILE, "w") as f:
        json.dump(result, f, indent=4)

    print("Done. Results saved to", RESULTS_FILE)


if __name__ == "__main__":
    main()