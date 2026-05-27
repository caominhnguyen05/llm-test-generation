import re
from dataclasses import dataclass
from pathlib import Path
from pipeline.config import PipelineConfig

def find_testable_sources(config: PipelineConfig) -> list[Path]:
    keep = []
    skipped = []

    for path in sorted(config.source_folder.rglob("*.java")):
        decision = check_testability(path, config.source_folder)
        relative_path = path.relative_to(config.source_folder)

        if decision.testable:
            keep.append(relative_path)
        else:
            skipped.append((relative_path, decision.reason))

    if len(skipped) > 0:
        print(f"Preprocessing skipped {len(skipped)} likely non-testable source files:")
        for source, reason in skipped:
            print(f"- {source}: {reason}")

    return keep


def remove_leading_block_comment(source_code: str) -> str:
    if source_code.strip().startswith("/*") and "*/" in source_code:
        return source_code.split("*/", 1)[1].strip()
    return source_code.strip()


def read_java_source(path: Path) -> str:
    source_code = path.read_text(encoding="utf-8", errors="replace")
    return remove_leading_block_comment(source_code)


def extract_package_and_class(java_file: Path, source_root: Path) -> tuple[str, str]:
    rel_path = java_file.relative_to(source_root).with_suffix("")
    return ".".join(rel_path.parts[:-1]), rel_path.parts[-1]


@dataclass(frozen=True)
class Decision:
    testable: bool
    reason: str = ""


def strip_comments_and_strings(source_code: str) -> str:
    """Remove Java comments and string bodies so simple source scans are safer."""
    source_code = re.sub(r"/\*.*?\*/", "", source_code, flags=re.DOTALL)
    source_code = re.sub(r"//.*", "", source_code)
    source_code = re.sub(r'"(?:\\.|[^"\\])*"', '""', source_code)
    source_code = re.sub(r"'(?:\\.|[^'\\])+'", "''", source_code)
    return source_code


def find_top_level_declaration(source_code: str, class_name: str) -> re.Match[str] | None:
    """Find the main class/interface/enum declaration matching the file name."""
    return re.search(
        rf"\b(?:public|protected|private|abstract|final|static|\s)*"
        rf"(class|interface|enum|@interface)\s+{re.escape(class_name)}\b",
        source_code,
    )


def body_after_declaration(source_code: str, declaration: re.Match[str]) -> str:
    """Return the text inside the outer class/interface/enum body."""
    body_start = source_code.find("{", declaration.end())
    body_end = source_code.rfind("}")
    if body_start == -1 or body_end == -1 or body_end <= body_start:
        return ""
    return source_code[body_start + 1 : body_end]


def has_method_body(source_code: str) -> bool:
    """Check whether the source contains at least one method with a body."""
    return bool(
        re.search(
            r"\b(?:public|protected|private|static|final|synchronized|native|\s)+"
            r"[\w<>\[\], ? extends super.]+\s+\w+\s*\([^;{}]*\)\s*(?:throws\s+[^{;]+)?\{",
            source_code,
        )
    )


def has_constructor_body(source_code: str, class_name: str) -> bool:
    """Check whether the class contains a constructor with a body."""
    return bool(
        re.search(
            rf"\b(?:public|protected|private|\s)*{re.escape(class_name)}\s*"
            r"\([^;{}]*\)\s*(?:throws\s+[^{;]+)?\{",
            source_code,
        )
    )


def is_constant_only_class(source_code: str, class_name: str) -> bool:
    if has_method_body(source_code) or has_constructor_body(source_code, class_name):
        return False

    fields = re.findall(
        r"\b(?:public|protected|private|static|final|transient|volatile|\s)+"
        r"[\w<>\[\], ? extends super.]+\s+\w+\s*(?:=|;)",
        source_code,
    )
    return bool(fields)


def is_simple_enum(body: str) -> bool:
    body_without_constants = body.split(";", 1)[1] if ";" in body else ""
    return not has_method_body(body_without_constants)


def check_testability(java_file: Path, source_root: Path) -> Decision:
    """Decide whether a Java source file is worth testing."""
    if java_file.name in {"package-info.java", "module-info.java"}:
        return Decision(False, "metadata source file")

    source_code = strip_comments_and_strings(read_java_source(java_file))
    _, class_name = extract_package_and_class(java_file, source_root)
    declaration = find_top_level_declaration(source_code, class_name)
    if declaration is None:
        return Decision(False, "no matching top-level Java type declaration")

    kind = declaration.group(1)
    body = body_after_declaration(source_code, declaration)

    if kind == "@interface":
        return Decision(False, "annotation type")

    if kind == "interface":
        has_default_or_static_method = bool(re.search(r"\b(default|static)\b[^;{}]*\([^;{}]*\)\s*\{", body))
        if not has_default_or_static_method:
            return Decision(False, "interface without executable default/static methods")

    if kind == "enum" and is_simple_enum(body):
        return Decision(False, "enum with constants only")

    if kind == "class" and is_constant_only_class(body, class_name):
        return Decision(False, "constant-only class")

    return Decision(True)