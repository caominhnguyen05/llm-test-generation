import re
from pathlib import Path


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as file:
        file.write(content.rstrip() + "\n")


def contains_class_declaration(source_code: str, class_name: str) -> bool:
    return bool(re.search(rf"\bclass\s+{re.escape(class_name)}\b", source_code))


def extract_java_code(llm_output: str, expected_class: str | None = None) -> str:
    """Extract the generated Java test class from an LLM response."""
    java_blocks = [
        match.group(1).strip()
        for match in re.finditer(r"```java\s*(.*?)```", llm_output, flags=re.DOTALL | re.IGNORECASE)
    ]
    generic_blocks = [
        match.group(1).strip()
        for match in re.finditer(r"```\s*(.*?)```", llm_output, flags=re.DOTALL)
    ]

    if expected_class:
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

        # Remove JUnit 3 imports
        if import_line.startswith("import junit.framework."):
            continue
        if import_line.startswith("import static junit.framework."):
            continue

        # Remove JUnit 5 imports
        if import_line.startswith("import org.junit.jupiter."):
            continue
        if import_line.startswith("import static org.junit.jupiter."):
            continue
        cleaned_imports.append(import_line)

    return code_without_imports.strip(), cleaned_imports


def strip_package_declarations(test_code: str) -> str:
    return re.sub(r"^\s*package\s+[\w.]+;\s*\n?", "", test_code, flags=re.MULTILINE).strip()


def infer_missing_imports(test_code: str, source_code: str = "") -> set[str]:
    imports = {
        "import org.junit.Test;",
        "import static org.junit.Assert.*;",
    }

    junit_symbols = {
        "@Before": "import org.junit.Before;",
        "@After": "import org.junit.After;",
        "@BeforeClass": "import org.junit.BeforeClass;",
        "@AfterClass": "import org.junit.AfterClass;",
    }
    for symbol, import_line in junit_symbols.items():
        if symbol in test_code:
            imports.add(import_line)

    java_symbols = {
        "Arrays.": "import java.util.Arrays;",
        "Collections.": "import java.util.Collections;",
        "Collection<": "import java.util.Collection;",
        "Date": "import java.util.Date;",
        "Comparator<": "import java.util.Comparator;",
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

    imports.update(extract_imports(source_code))
    return imports


def normalize_test_code(test_code: str, package_name: str, class_name: str, source_code: str = "") -> str:
    """Clean common LLM formatting issues and add imports needed by JUnit 4 tests."""
    expected_class = f"{class_name}Test"
    test_code = extract_java_code(test_code, expected_class)
    test_code = test_code.replace("\r\n", "\n").replace("\r", "\n").strip()
    test_code, existing_imports = remove_existing_imports(test_code)
    test_code = strip_package_declarations(test_code)

    test_code = re.sub(
        r"\bpublic\s+class\s+\w+\b",
        f"public class {expected_class}",
        test_code,
        count=1,
    )

    imports = set(existing_imports) | infer_missing_imports(test_code, source_code)
    imports_block = "\n".join(sorted(imports))

    return f"package {package_name};\n\n{imports_block}\n\n{test_code}"
