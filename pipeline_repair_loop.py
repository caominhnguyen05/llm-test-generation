import argparse
import re
import subprocess
from pathlib import Path

from ollama import chat

from ollama_models import get_model

OLLAMA_MODEL = get_model("qwen3")

LIBRARIES_ROOT = Path("selected_libraries")
TARGET_LIBRARY = "commons-csv-1.8"

# Path relative to selected_libraries/<TARGET_LIBRARY>/src/main/java.
TARGET_SOURCE_RELATIVE_PATH = Path("org/apache/commons/csv/Lexer.java")

MAX_REPAIR_ATTEMPTS = 1
MAVEN_TIMEOUT_SECONDS = 120
ERROR_CONTEXT_CHARS = 5000


# =========================
# UTIL FUNCTIONS
# =========================

def remove_license_comment(source_code: str) -> str:
    """Remove leading license comment if present to avoid LLM confusion."""
    if source_code.strip().startswith("/*") and "*/" in source_code:
        return source_code.split("*/", 1)[1].strip()
    return source_code.strip()


def read_file(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return remove_license_comment(f.read())


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content.rstrip() + "\n")


def extract_java_code(llm_output: str) -> str:
    java_block = re.search(r"```java\s*(.*?)```", llm_output, flags=re.DOTALL | re.IGNORECASE)
    if java_block:
        return java_block.group(1).strip()

    generic_block = re.search(r"```\s*(.*?)```", llm_output, flags=re.DOTALL)
    if generic_block:
        return generic_block.group(1).strip()

    return llm_output.strip()


def extract_package_and_class(java_file: Path, source_root: Path) -> tuple[str, str]:
    rel_path = java_file.relative_to(source_root).with_suffix("")
    return ".".join(rel_path.parts[:-1]), rel_path.parts[-1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate and repair JUnit 4 tests for one class in selected_libraries."
    )
    parser.add_argument("--library", default=TARGET_LIBRARY, help="Folder under selected_libraries.")
    parser.add_argument(
        "--source",
        default=str(TARGET_SOURCE_RELATIVE_PATH),
        help="Java file relative to src/main/java in the selected library.",
    )
    parser.add_argument("--model", default=OLLAMA_MODEL, help="Ollama model name.")
    parser.add_argument("--attempts", type=int, default=MAX_REPAIR_ATTEMPTS)
    return parser.parse_args()


def remove_existing_imports(test_code: str) -> tuple[str, list[str]]:
    imports = re.findall(r"^\s*import\s+(?:static\s+)?[\w.*]+;\s*$", test_code, flags=re.MULTILINE)
    code_without_imports = re.sub(
        r"^\s*import\s+(?:static\s+)?[\w.*]+;\s*\n?", "", test_code, flags=re.MULTILINE
    )
    return code_without_imports.strip(), [imp.strip() for imp in imports]


def strip_package_declarations(test_code: str) -> str:
    return re.sub(r"^\s*package\s+[\w.]+;\s*\n?", "", test_code, flags=re.MULTILINE).strip()


def infer_missing_imports(test_code: str) -> set[str]:
    imports = {
        "import org.junit.Test;",
        "import static org.junit.Assert.*;",
    }

    junit_symbols = {
        "@Before": "import org.junit.Before;",
        "@After": "import org.junit.After;",
        "@BeforeClass": "import org.junit.BeforeClass;",
        "@AfterClass": "import org.junit.AfterClass;",
        "@Rule": "import org.junit.Rule;",
        "ExpectedException": "import org.junit.rules.ExpectedException;",
        "TemporaryFolder": "import org.junit.rules.TemporaryFolder;",
    }
    for symbol, import_line in junit_symbols.items():
        if symbol in test_code:
            imports.add(import_line)

    java_symbols = {
        "Arrays.": "import java.util.Arrays;",
        "Collections.": "import java.util.Collections;",
        "List<": "import java.util.List;",
        "Map<": "import java.util.Map;",
        "Set<": "import java.util.Set;",
        "IOException": "import java.io.IOException;",
        "StringReader": "import java.io.StringReader;",
        "StringWriter": "import java.io.StringWriter;",
        "ByteArrayInputStream": "import java.io.ByteArrayInputStream;",
        "ByteArrayOutputStream": "import java.io.ByteArrayOutputStream;",
    }
    for symbol, import_line in java_symbols.items():
        if symbol in test_code:
            imports.add(import_line)

    return imports


def normalize_test_code(test_code: str, package_name: str, class_name: str) -> str:
    """Clean common LLM formatting issues and add imports needed by JUnit 4 tests."""
    test_code = extract_java_code(test_code)
    test_code = test_code.replace("\r\n", "\n").replace("\r", "\n").strip()
    test_code, existing_imports = remove_existing_imports(test_code)
    test_code = strip_package_declarations(test_code)

    expected_class = f"{class_name}Test"
    test_code = re.sub(
        r"\bpublic\s+class\s+\w+\b",
        f"public class {expected_class}",
        test_code,
        count=1,
    )
    if not re.search(rf"\bclass\s+{re.escape(expected_class)}\b", test_code):
        raise ValueError(f"Generated code does not contain class {expected_class}.")

    imports = set(existing_imports) | infer_missing_imports(test_code)
    imports_block = "\n".join(sorted(imports))

    normalized = f"package {package_name};\n\n{imports_block}\n\n{test_code}"
    return normalized


def quick_syntax_check(test_code: str, class_name: str) -> list[str]:
    issues = []
    if f"public class {class_name}Test" not in test_code:
        issues.append(f"missing public class {class_name}Test declaration")
    if "@Test" not in test_code:
        issues.append("missing @Test method annotation")
    if test_code.count("{") != test_code.count("}"):
        issues.append("unbalanced curly braces")
    if test_code.count("(") != test_code.count(")"):
        issues.append("unbalanced parentheses")
    return issues


# =========================
# MAVEN / LLM HELPERS
# =========================
def call_llm_stream(prompt: str, model: str) -> str:
    stream = chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    llm_output = ""
    for chunk in stream:
        token = chunk["message"]["content"]
        print(token, end="", flush=True)
        llm_output += token
    print("\n\nGeneration complete.\n")
    return llm_output


def run_maven_test(library_path: Path, test_class: str) -> tuple[bool, str]:
    print(f"\nRunning Maven tests for {test_class}...")
    command = ["mvn.cmd", "-q", "test", f"-Dtest={test_class}"]

    result = subprocess.run(
        command,
        cwd=library_path,
        capture_output=True,
        text=True,
        timeout=MAVEN_TIMEOUT_SECONDS,
    )

    if result.returncode == 0:
        return True, ""

    error_output = result.stdout + "\n" + result.stderr
    return False, error_output[-ERROR_CONTEXT_CHARS:]


def get_generation_prompt(source_code: str, package_name: str, class_name: str) -> str:
    return f"""
    Write a complete JUnit 4 test class for the Java source below.
    Maximize line and branch coverage, and make sure the test class compiles and runs without errors.

    Requirements:
    1. Package: `{package_name}`.
    2. Class name: The test MUST be named `{class_name}Test` and be declared `public`.
    3. Include all imports needed for JUnit 4 and assertions.
    4. Every test method must use @Test.
    5. Prefer deterministic, fast unit tests with no network, sleeps, randomness, or environment assumptions.
    6. Maximize meaningful line and branch coverage using normal cases, boundaries, exceptional cases, and null handling where the source supports it.
    7. Do not test private implementation details unless they are package-private and directly relevant.
    8. Output ONLY the complete raw Java code inside one ```java block. No comments or explanations.

    Source Code:
    ```java
    {source_code}
    ```
    """


def get_repair_prompt(
    test_code: str,
    error_output: str,
    source_code: str,
    package_name: str,
    class_name: str,
) -> str:
    return f"""
    The JUnit 4 test class for `{class_name}` failed to compile or run in Maven.

    Fix the test code only. Keep the same package and class name.

    Package: `{package_name}`
    Class name: `{class_name}Test`

    Source under test:
    ```java
    {source_code}
    ```

    Failing test code:
    ```java
    {test_code}
    ```

    Maven output:
    ```text
    {error_output}
    ```

    Requirements:
    1. Output ONLY the complete fixed raw Java code inside one ```java block.
    2. Use JUnit 4 imports, including org.junit.Test and static org.junit.Assert.* where needed.
    3. Remove tests that rely on unavailable APIs, nondeterminism, external files, or invalid assumptions.
    4. Keep tests deterministic and focused on behavior visible from the source.
    """


# =========================
# MAIN PIPELINE
# =========================
def main() -> None:
    args = parse_args()
    library_path = LIBRARIES_ROOT / args.library
    source_root = library_path / "src/main/java"
    test_root = library_path / "src/test/java"
    target_java_file = source_root / Path(args.source)

    if not library_path.exists():
        print(f"Error: library folder not found: {library_path}")
        return
    if not target_java_file.exists():
        print(f"Error: source file not found: {target_java_file}")
        return

    package_name, class_name = extract_package_and_class(target_java_file, source_root)
    output_test_file = test_root / package_name.replace(".", "/") / f"{class_name}Test.java"

    source_code = read_file(target_java_file)
    print(f"Library: {args.library}")
    print(f"Source: {target_java_file}")
    print(f"Package: {package_name}")
    print(f"Class: {class_name}")
    print(f"Output: {output_test_file}")

    print(f"\n[Attempt 0] Asking Ollama ({args.model}) to generate tests...")
    llm_output = call_llm_stream(get_generation_prompt(source_code, package_name, class_name), args.model)
    test_code = normalize_test_code(llm_output, package_name, class_name)
    syntax_issues = quick_syntax_check(test_code, class_name)
    if syntax_issues:
        print(f"Quick syntax warnings before Maven: {', '.join(syntax_issues)}")
    write_file(output_test_file, test_code)
    print(f"Initial test saved to {output_test_file}")

    for attempt in range(args.attempts + 1):
        success, error_output = run_maven_test(library_path, f"{class_name}Test")
        if success:
            print(f"SUCCESS: test compiled and passed on attempt {attempt}.")
            return

        if attempt >= args.attempts:
            print(f"FAILURE: max repair attempts ({args.attempts}) reached.")
            print(error_output)
            return

        print(f"FAILED. Starting repair loop {attempt + 1}/{args.attempts}...")
        llm_output = call_llm_stream(
            get_repair_prompt(test_code, error_output, source_code, package_name, class_name),
            args.model,
        )
        test_code = normalize_test_code(llm_output, package_name, class_name)
        syntax_issues = quick_syntax_check(test_code, class_name)
        if syntax_issues:
            print(f"Quick syntax warnings before Maven: {', '.join(syntax_issues)}")
        write_file(output_test_file, test_code)
        print(f"Repaired test saved to {output_test_file}")


if __name__ == "__main__":
    main()
