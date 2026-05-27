import csv
import re
from collections import Counter
from pathlib import Path

from pipeline.config import PipelineConfig
from pipeline.metrics import append_csv_row
from pipeline.validation import ValidationResult


COMPILE_FAILURE_FIELDNAMES = [
    "library",
    "source_file",
    "stage",
    "category",
    "message",
]
COMPILE_FAILURE_SUMMARY_FIELDNAMES = [
    "library",
    "category",
    "compile_failures",
    "percentage",
]


def categorize_compile_error(message: str, stage: str = "compile") -> str:
    """Return a regex-based category for a Maven compile error."""
    if stage == "structure":
        return "structure_error"

    patterns = [
        ("junit_version_mismatch", r"org\.junit\.jupiter|jupiter.*does not exist|package org\.junit\.jupiter does not exist"),
        ("missing_import", r"package .+ does not exist|import .+ cannot be resolved"),
        ("method_signature_mismatch", r"method .+ cannot be applied|no suitable method|actual and formal argument lists differ"),
        ("cannot_find_symbol", r"cannot find symbol|symbol:\s*(class|method|variable)"),
        ("constructor_mismatch", r"constructor .+ cannot be applied|no suitable constructor"),
        ("access_modifier_error", r"has private access|has protected access|is not public in|cannot be accessed from outside package"),
        (
            "abstract_class_or_interface_instantiation",
            r"is abstract; cannot be instantiated|is abstract and cannot be instantiated|is an interface; cannot be instantiated",
        ),
        ("unchecked_exception_not_handled", r"unreported exception|must be caught or declared to be thrown"),
        ("generic_type_mismatch", r"incompatible types|inference variable|type argument|cannot infer type"),
        ("dependency_missing", r"could not resolve dependencies|dependency .+ not found|package .+ does not exist"),
        ("syntax_error", r"';' expected|illegal start of|reached end of file while parsing|not a statement|class, interface, enum, or record expected"),
    ]
    for category, pattern in patterns:
        if re.search(pattern, message.lower(), re.DOTALL):
            return category
    return "other_compile_error"


def record_compile_failure(
    config: PipelineConfig,
    source: Path,
    result: ValidationResult,
) -> None:
    category = categorize_compile_error(result.message, result.stage)

    append_csv_row(
        config.compile_failures_csv,
        COMPILE_FAILURE_FIELDNAMES,
        {
            "library": config.library,
            "source_file": str(source),
            "stage": result.stage,
            "category": category,
            "message": compact_csv_message(result.message),
        },
    )


def write_compile_failure_summary(config: PipelineConfig) -> None:
    """Write category counts and percentages from the compile failure detail CSV."""
    if not config.compile_failures_csv.exists():
        return

    library_counts: dict[str, Counter[str]] = {}
    with open(config.compile_failures_csv, "r", encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            library = row.get("library", "")
            if not library:
                continue
            category = row.get("category", "other_compile_error")
            library_counts.setdefault(library, Counter())[category] += 1

    if not library_counts:
        return

    config.compile_failure_summary_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(config.compile_failure_summary_csv, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=COMPILE_FAILURE_SUMMARY_FIELDNAMES)
        writer.writeheader()
        for library, category_counts in sorted(library_counts.items()):
            total_failures = sum(category_counts.values())
            for category, count in sorted(category_counts.items()):
                writer.writerow(
                    {
                        "library": library,
                        "category": category,
                        "compile_failures": str(count),
                        "percentage": f"{(count / total_failures) * 100:.2f}",
                    }
                )
    print(f"Compile failure summary written to {config.compile_failure_summary_csv}")


def compact_csv_message(message: str) -> str:
    return re.sub(r"\s+", " ", message).strip()[-1000:]