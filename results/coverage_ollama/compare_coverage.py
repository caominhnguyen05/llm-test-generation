from pathlib import Path
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


KEY_COLUMNS = ["group_id", "artifact_id", "version"]
COVERAGE_COLUMNS = [
    "instruction_coverage",
    "branch_coverage",
    "line_coverage",
    "complexity_coverage",
    "method_coverage",
    "class_coverage",
]
METRIC_LABELS = {
    "instruction_coverage": "Instruction",
    "branch_coverage": "Branch",
    "line_coverage": "Line",
    "complexity_coverage": "Complexity",
    "method_coverage": "Method",
    "class_coverage": "Class",
}


def load_coverage_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str)

    for column in KEY_COLUMNS:
        df[column] = df[column].fillna("").str.strip()

    df = df[df[KEY_COLUMNS].ne("").all(axis=1)].copy()

    for column in COVERAGE_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    return df


def main() -> None:
    root_dir = Path(__file__).resolve().parents[2]

    # Load CSV files
    llm = load_coverage_csv(root_dir / "results" / "coverage" /"llm_coverage_final.csv")
    evosuite = load_coverage_csv(root_dir / "csv_data" / "evosuite_original.csv")

    # Find libraries that exist in both CSV files.
    common_libraries = llm[KEY_COLUMNS].drop_duplicates().merge(
        evosuite[KEY_COLUMNS].drop_duplicates(), on=KEY_COLUMNS
    )

    if common_libraries.empty:
        raise ValueError("No matching rows found between LLM and EvoSuite CSV files.")

    df = pd.concat([llm, evosuite], ignore_index=True)
    df = df.merge(common_libraries, on=KEY_COLUMNS, how="inner")

    # Keep only the columns needed for summary and plotting.
    df = df[KEY_COLUMNS + COVERAGE_COLUMNS + ["source"]]

    # Generate median summary table.
    summary = df.groupby("source")[COVERAGE_COLUMNS].median().round(2)

    output_dir = root_dir / "results" / "coverage"
    output_dir.mkdir(exist_ok=True)
    summary.to_csv(output_dir / "coverage_summary_table.csv")

    with open(output_dir / "coverage_summary_table.tex", "w", encoding="utf-8") as f:
        f.write(summary.to_latex())

    # Create grouped bar chart from median coverage values.
    plt.figure(figsize=(11, 6))

    metrics = list(METRIC_LABELS.values())
    x_positions = list(range(len(COVERAGE_COLUMNS)))
    bar_width = 0.36

    colors = {
        "LLM": "#4C72B0",
        "EVOSUITE": "#DD8452",
    }

    median_coverage = df.groupby("source")[COVERAGE_COLUMNS].median()
    llm_values = [median_coverage.loc["LLM", column] for column in COVERAGE_COLUMNS]
    evosuite_values = [
        median_coverage.loc["EVOSUITE", column] for column in COVERAGE_COLUMNS
    ]

    llm_positions = [x - bar_width / 2 for x in x_positions]
    evosuite_positions = [x + bar_width / 2 for x in x_positions]

    llm_bars = plt.bar(
        llm_positions,
        llm_values,
        width=bar_width,
        color=colors["LLM"],
        label="LLM",
    )
    evosuite_bars = plt.bar(
        evosuite_positions,
        evosuite_values,
        width=bar_width,
        color=colors["EVOSUITE"],
        label="EvoSuite",
    )

    for bars in [llm_bars, evosuite_bars]:
        for bar in bars:
            height = bar.get_height()
            plt.text(
                bar.get_x() + bar.get_width() / 2,
                height + 1,
                f"{height:.1f}",
                ha="center",
                va="bottom",
                fontsize=10,
            )

    plt.xticks(x_positions, metrics, rotation=45, ha="right", fontsize=13)
    plt.legend(title="Approach", fontsize=12, title_fontsize=13)

    plt.ylabel("Coverage (%)", fontsize=14)
    plt.ylim(0, 110)
    plt.title(
        f"Median Coverage: LLM vs EvoSuite tests ({len(common_libraries)} libraries)",
        fontsize=15,
    )
    plt.tight_layout()

    # plt.savefig(output_dir / "coverage_bar_chart.pdf")
    plt.savefig(output_dir / "coverage_bar_chart.png", dpi=300)
    plt.close()

    print(f"\nMatched {len(common_libraries)} of {len(llm)} LLM row(s).")
    print(f"Saved plot to {output_dir / 'coverage_bar_chart.png'}")
    print(f"Saved summary to {output_dir / 'coverage_summary_table.csv'}")


if __name__ == "__main__":
    main()
