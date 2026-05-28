import re

JUNIT4_IMPORTS = {
    "import org.junit.Ignore;",
    "import org.junit.Test;",
    "import static org.junit.Assert.*;",
}

SYMBOL_IMPORTS = {
    "@Before": "import org.junit.Before;",
    "@After": "import org.junit.After;",
    "Arrays.": "import java.util.Arrays;",
    "Collections.": "import java.util.Collections;",
    "Collection<": "import java.util.Collection;",
    "Comparator<": "import java.util.Comparator;",
    "List<": "import java.util.List;",
    "Map<": "import java.util.Map;",
    "Set<": "import java.util.Set;",
    "IOException": "import java.io.IOException;",
}


def contains_class_declaration(source_code: str, class_name: str) -> bool:
    return bool(re.search(rf"\bclass\s+{re.escape(class_name)}\b", source_code))


def extract_java_code(llm_output: str, expected_class: str) -> str:
    """Extract the generated Java test class from an LLM response."""
    java_blocks = [
        match.group(1).strip()
        for match in re.finditer(r"```java\s*(.*?)```", llm_output, flags=re.DOTALL | re.IGNORECASE)
    ]
    generic_blocks = [
        match.group(1).strip()
        for match in re.finditer(r"```\s*(.*?)```", llm_output, flags=re.DOTALL)
    ]

    for block in java_blocks:
        if contains_class_declaration(block, expected_class):
            return block
    for block in generic_blocks:
        if contains_class_declaration(block, expected_class):
            return block
    if contains_class_declaration(llm_output, expected_class):
        return llm_output.strip()

    if java_blocks:
        return java_blocks[0]
    if generic_blocks:
        return generic_blocks[0]
    return llm_output.strip()


def extract_imports(source_code: str) -> list[str]:
    """Extracts import statements from Java source code."""
    return [
        line.strip()
        for line in re.findall(
            r"^\s*import\s+(?:static\s+)?[\w.*]+;\s*$",
            source_code,
            flags=re.MULTILINE,
        )
    ]


def remove_existing_imports(test_code: str) -> tuple[str, list[str]]:
    """Removes existing import statements from the test code and returns them separately."""
    imports = re.findall(
        r"^\s*import\s+(?:static\s+)?[\w.*]+;\s*$",
        test_code,
        flags=re.MULTILINE,
    )

    code_without_imports = re.sub(
        r"^\s*import\s+(?:static\s+)?[\w.*]+;\s*\n?",
        "",
        test_code,
        flags=re.MULTILINE,
    )

    cleaned_imports = []
    for import_line in imports:
        import_line = import_line.strip()

        wrong_junit_imports = (
            "import junit.framework.",
            "import static junit.framework.",
            "import org.junit.jupiter.",
            "import static org.junit.jupiter."
        )

        if import_line.startswith(wrong_junit_imports):
            continue
        cleaned_imports.append(import_line)

    return code_without_imports.strip(), cleaned_imports


def remove_package_declaration(test_code: str) -> str:
    return re.sub(r"^\s*package\s+[\w.]+;\s*\n?", "", test_code, flags=re.MULTILINE).strip()


def infer_missing_imports(test_code: str, source_code: str = "") -> set[str]:
    """Infer imports commonly needed by generated JUnit 4 tests."""
    imports = set(JUNIT4_IMPORTS)

    for symbol, import_line in SYMBOL_IMPORTS.items():
        if symbol in test_code:
            imports.add(import_line)

    imports.update(extract_imports(source_code))
    return imports


def postprocess_test_code(test_code: str, package_name: str, class_name: str, source_code: str = "") -> str:
    """Clean common LLM formatting issues and add imports needed by JUnit 4 tests."""
    expected_class = f"{class_name}Test"
    test_code = extract_java_code(test_code, expected_class)
    test_code = test_code.replace("\r\n", "\n").replace("\r", "\n").strip()
    test_code, existing_imports = remove_existing_imports(test_code)
    test_code = remove_package_declaration(test_code)

    test_code = re.sub(
        r"\bpublic\s+class\s+\w+\b",
        f"public class {expected_class}",
        test_code,
        count=1,
    )

    imports = set(existing_imports) | infer_missing_imports(test_code, source_code)
    imports_block = "\n".join(sorted(imports))
    test_code = add_test_timeouts(test_code)

    return f"package {package_name};\n\n{imports_block}\n\n{test_code}"


def add_test_timeouts(test_code: str) -> str:
    """Add timeout = 2000 to each @Test annotation in the test code."""

    def add_timeout(match: re.Match[str]) -> str:
        arguments = match.group(1)
        timeout_argument = "timeout = 2000"

        if arguments is None:
            return f"@Test({timeout_argument})"

        arguments = arguments.strip()
        if re.search(r"\btimeout\s*=", arguments):
            arguments = re.sub(
                r"\btimeout\s*=\s*\d+[lL]?",
                timeout_argument,
                arguments,
                count=1,
            )
            return f"@Test({arguments})"

        return f"@Test({timeout_argument}, {arguments})"

    return re.sub(r"@\s*Test(?:\s*\(([^)]*)\))?", add_timeout, test_code)