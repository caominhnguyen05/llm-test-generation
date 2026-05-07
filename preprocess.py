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
