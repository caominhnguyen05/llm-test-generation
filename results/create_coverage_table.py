from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_FILE = BASE_DIR / "coverage_repair_attempts_table.tex"
PLOT_FILE = BASE_DIR / "median_coverage_by_repair_attempts.png"

COVERAGE_FILES = {
    "No repair": BASE_DIR / "coverage_no_repair.csv",
    "1 repair": BASE_DIR / "coverage_repair_1.csv",
    "2 repairs": BASE_DIR / "llm_coverage_final.csv",
}

COVERAGE_COLUMNS = {
    "Line": "line_coverage",
    "Branch": "branch_coverage",
    "Instruction": "instruction_coverage",
    "Method": "method_coverage",
    "Class": "class_coverage",
    "Complexity": "complexity_coverage",
}


def format_number(value):
    return f"{value:.2f}"


def coverage_stats(csv_path):
    df = pd.read_csv(csv_path)
    stats = {}

    for metric, column in COVERAGE_COLUMNS.items():
        values = pd.to_numeric(df[column], errors="coerce")
        stats[metric] = {
            "median": values.median(),
            "mean": values.mean(),
        }

    return stats


def main():
    all_stats = {
        label: coverage_stats(csv_path)
        for label, csv_path in COVERAGE_FILES.items()
    }

    lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Mean and median coverage across different maximum repair attempts}",
        r"\label{tab:coverage-repair-attempts}",
        r"\begin{tabular}{lrrrrrr}",
        r"\hline",
        r"Metric & \multicolumn{2}{c}{No repair} & \multicolumn{2}{c}{1 repair} & \multicolumn{2}{c}{2 repairs} \\",
        r"\cline{2-7}",
        r" & Median & Mean & Median & Mean & Median & Mean \\",
        r"\hline",
    ]

    for metric in COVERAGE_COLUMNS:
        row = [metric]
        for label in COVERAGE_FILES:
            row.append(format_number(all_stats[label][metric]["median"]))
            row.append(format_number(all_stats[label][metric]["mean"]))
        lines.append(" & ".join(row) + r" \\")

    lines.extend([
        r"\hline",
        r"\end{tabular}",
        r"\end{table}",
    ])

    OUTPUT_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved table to {OUTPUT_FILE}")

    repair_attempts = [0, 1, 2]
    plt.figure(figsize=(8, 5))

    for metric in COVERAGE_COLUMNS:
        medians = [
            all_stats[label][metric]["median"]
            for label in COVERAGE_FILES
        ]
        plt.plot(repair_attempts, medians, marker="o", label=metric)

    plt.xlabel("Maximum repair attempts")
    plt.ylabel("Median coverage (%)")
    plt.xticks(repair_attempts)
    plt.grid(True, linestyle="--", alpha=0.4)
    plt.legend()
    plt.tight_layout()
    # plt.savefig(PLOT_FILE, dpi=300)
    plt.savefig(BASE_DIR / "median_coverage_by_repair_attempts.pdf")
    plt.close()


if __name__ == "__main__":
    main()
