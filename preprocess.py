import re
from dataclasses import dataclass
from pathlib import Path


def remove_license_comment(source_code: str) -> str:
    if source_code.strip().startswith("/*") and "*/" in source_code:
        return source_code.split("*/", 1)[1].strip()
    return source_code.strip()


def read_source_file(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as file:
        return remove_license_comment(file.read())


def extract_package_and_class(java_file: Path, source_root: Path) -> tuple[str, str]:
    rel_path = java_file.relative_to(source_root).with_suffix("")
    return ".".join(rel_path.parts[:-1]), rel_path.parts[-1]


@dataclass(frozen=True)
class TestabilityDecision:
    testable: bool
    reason: str = ""


def strip_comments_and_strings(source_code: str) -> str:
    """Remove Java comments and string bodies so simple source scans are safer."""
    source_code = re.sub(r"/\*.*?\*/", "", source_code, flags=re.DOTALL)
    source_code = re.sub(r"//.*", "", source_code)
    source_code = re.sub(r'"(?:\\.|[^"\\])*"', '""', source_code)
    source_code = re.sub(r"'(?:\\.|[^'\\])+'", "''", source_code)
    return source_code


def _find_top_level_declaration(source_code: str, class_name: str) -> re.Match[str] | None:
    return re.search(
        rf"\b(?:public|protected|private|abstract|final|static|\s)*"
        rf"(class|interface|enum|@interface)\s+{re.escape(class_name)}\b",
        source_code,
    )


def _body_after_declaration(source_code: str, declaration: re.Match[str]) -> str:
    body_start = source_code.find("{", declaration.end())
    body_end = source_code.rfind("}")
    if body_start == -1 or body_end == -1 or body_end <= body_start:
        return ""
    return source_code[body_start + 1 : body_end]


def _has_method_body(source_code: str) -> bool:
    return bool(
        re.search(
            r"\b(?:public|protected|private|static|final|synchronized|native|\s)+"
            r"[\w<>\[\], ? extends super.]+\s+\w+\s*\([^;{}]*\)\s*(?:throws\s+[^{;]+)?\{",
            source_code,
        )
    )


def _has_constructor_body(source_code: str, class_name: str) -> bool:
    return bool(
        re.search(
            rf"\b(?:public|protected|private|\s)*{re.escape(class_name)}\s*"
            r"\([^;{}]*\)\s*(?:throws\s+[^{;]+)?\{",
            source_code,
        )
    )


def _is_constant_only_class(source_code: str, class_name: str) -> bool:
    if _has_method_body(source_code) or _has_constructor_body(source_code, class_name):
        return False

    fields = re.findall(
        r"\b(?:public|protected|private|static|final|transient|volatile|\s)+"
        r"[\w<>\[\], ? extends super.]+\s+\w+\s*(?:=|;)",
        source_code,
    )
    return bool(fields)


def _is_simple_enum(body: str) -> bool:
    body_without_constants = body.split(";", 1)[1] if ";" in body else ""
    return not _has_method_body(body_without_constants)


def assess_source_testability(java_file: Path, source_root: Path) -> TestabilityDecision:
    """Heuristically skip source files that are unlikely to produce useful tests."""
    if java_file.name in {"package-info.java", "module-info.java"}:
        return TestabilityDecision(False, "metadata source file")

    source_code = strip_comments_and_strings(read_source_file(java_file))
    _, class_name = extract_package_and_class(java_file, source_root)
    declaration = _find_top_level_declaration(source_code, class_name)
    if declaration is None:
        return TestabilityDecision(False, "no matching top-level Java type declaration")

    kind = declaration.group(1)
    body = _body_after_declaration(source_code, declaration)

    if kind == "@interface":
        return TestabilityDecision(False, "annotation type")

    if kind == "interface":
        has_default_or_static_method = bool(re.search(r"\b(default|static)\b[^;{}]*\([^;{}]*\)\s*\{", body))
        if not has_default_or_static_method:
            return TestabilityDecision(False, "interface without executable default/static methods")

    if kind == "enum" and _is_simple_enum(body):
        return TestabilityDecision(False, "enum with constants only")

    if kind == "class" and _is_constant_only_class(body, class_name):
        return TestabilityDecision(False, "constant-only class")

    return TestabilityDecision(True)
