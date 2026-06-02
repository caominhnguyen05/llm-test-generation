from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


CATEGORY_LABELS = {
    "structure_error": "Structure Error",
    "junit_version_mismatch": "JUnit Version Mismatch",
    "missing_import": "Missing Import",
    "method_signature_mismatch": "Method Signature Mismatch",
    "cannot_find_symbol": "Cannot Find Symbol",
    "constructor_mismatch": "Constructor Mismatch",
    "access_modifier_error": "Access Modifier Error",
    "abstract_class_or_interface_instantiation": "Abstract Class or Interface Instantiation",
    "unchecked_exception_not_handled": "Unchecked Exception Not Handled",
    "generic_type_mismatch": "Generic Type Mismatch",
    "dependency_missing": "Missing Dependency",
    "syntax_error": "Syntax Error",
    "other_compile_error": "Other Compile Error",
}


def main() -> None:
    root_dir = Path(__file__).resolve().parents[1]
    input_path = root_dir / "results" / "final" / "ollama" / "compile_failures_summary.csv"
    output_path = root_dir / "results" / "final" / "ollama" / "compile_failure_categories.pdf"

    df = pd.read_csv(input_path)
    df["compile_failures"] = pd.to_numeric(
        df["compile_failures"], errors="coerce"
    ).fillna(0)

    failures_by_category = (
        df.groupby("category")["compile_failures"]
        .sum()
        .sort_values(ascending=True)
    )

    display_labels = [
        CATEGORY_LABELS.get(category, category.replace("_", " ").title())
        for category in failures_by_category.index
    ]

    plt.figure(figsize=(10, 5))
    bars = plt.barh(
        display_labels,
        failures_by_category.values,
        color="#4C72B0",
    )

    max_value = failures_by_category.max()
    for bar in bars:
        width = bar.get_width()
        plt.text(
            width + max_value * 0.01,
            bar.get_y() + bar.get_height() / 2,
            f"{int(width)}",
            va="center",
            fontsize=13,
        )

    plt.xlabel("Number of Compilation Failures", fontsize=14) 
    plt.ylabel("Failure Category", fontsize=14) 
    plt.tick_params(axis="both", labelsize=13)
    plt.xlim(0, max_value * 1.15)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()

    print(f"Saved chart to {output_path}")


if __name__ == "__main__":
    main()
