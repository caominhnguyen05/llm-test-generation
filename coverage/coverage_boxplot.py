from pathlib import Path
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import Patch
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
    # Load CSV files
    llm = load_coverage_csv("csv_data/llm_coverage.csv")
    evosuite = load_coverage_csv("csv_data/evosuite_results.csv")

    # Find libraries that exist in both CSV files.
    common_libraries = llm[KEY_COLUMNS].drop_duplicates().merge(
        evosuite[KEY_COLUMNS].drop_duplicates(), on=KEY_COLUMNS
    )

    if common_libraries.empty:
        raise ValueError("No matching rows found between LLM and EvoSuite CSV files.")

    # Stack both datasets, then keep only libraries that have both LLM and EvoSuite rows.
    df = pd.concat([llm, evosuite], ignore_index=True)
    df = df.merge(common_libraries, on=KEY_COLUMNS, how="inner")

    # Keep only the columns needed for summary and plotting.
    df = df[KEY_COLUMNS + COVERAGE_COLUMNS + ["source"]]

    # Generate summary table
    summary = (
        df.groupby("source")[COVERAGE_COLUMNS]
        .agg(["mean", "median", "std", "min", "max"])
        .round(2)
    )

    output_dir = Path("coverage")
    output_dir.mkdir(exist_ok=True)
    summary.to_csv(output_dir / "coverage_summary_table.csv")

    with open(output_dir / "coverage_summary_table.tex", "w", encoding="utf-8") as f:
        f.write(summary.to_latex())

    # Reshape data for box plot
    df_long = df.melt(
        id_vars=["source"],
        value_vars=COVERAGE_COLUMNS,
        var_name="Coverage Metric",
        value_name="Coverage",
    )
    df_long["Coverage Metric"] = df_long["Coverage Metric"].replace(METRIC_LABELS)

    # Create box plot
    plt.figure(figsize=(11, 6))

    data = []
    positions = []

    metrics = list(METRIC_LABELS.values())

    # Colors for the two approaches
    colors = {
        "LLM": "#4C72B0",
        "EVOSUITE": "#DD8452",
    }

    # Controls spacing
    group_gap = 1.1
    box_offset = 0.18
    box_width = 0.3

    metric_centers = []
    pos = 1

    for metric in metrics:
        center = pos
        metric_centers.append(center)

        for approach, offset in [("LLM", -box_offset), ("EVOSUITE", box_offset)]:
            values = df_long[
                (df_long["Coverage Metric"] == metric)
                & (df_long["source"] == approach)
            ]["Coverage"].dropna()

            data.append(values)
            positions.append(center + offset)

        pos += group_gap

    boxplot = plt.boxplot(
        data,
        positions=positions,
        widths=box_width,
        patch_artist=True,
    )

    # Color boxes alternately: LLM, EvoSuite, LLM, EvoSuite, ...
    for i, box in enumerate(boxplot["boxes"]):
        approach = "LLM" if i % 2 == 0 else "EVOSUITE"
        box.set_facecolor(colors[approach])
        box.set_alpha(0.75)

    for median in boxplot["medians"]:
        median.set_color("black")
        median.set_linewidth(1.5)

    # One label per pair, centered under both boxes
    plt.xticks(metric_centers, metrics, rotation=45, ha="right", fontsize=13)
    
    legend_handles = [
        Patch(facecolor=colors["LLM"], alpha=0.75, label="LLM"),
        Patch(facecolor=colors["EVOSUITE"], alpha=0.75, label="EvoSuite"),
    ]

    plt.legend(handles=legend_handles, title="Approach",fontsize=12, title_fontsize=13)

    plt.ylabel("Coverage (%)", fontsize=14)
    plt.ylim(0, 105)
    plt.title(f"Coverage Distribution: LLM vs EvoSuite ({len(common_libraries)} matched libraries)", fontsize=15)
    plt.tight_layout()

    plt.savefig(output_dir / "coverage_boxplot.pdf")
    plt.savefig(output_dir / "coverage_boxplot.png", dpi=300)
    plt.close()

    print(f"\nMatched {len(common_libraries)} of {len(llm)} LLM row(s).")
    print(f"Saved plot to {output_dir / 'coverage_boxplot.png'}")
    print(f"Saved summary to {output_dir / 'coverage_summary_table.csv'}")


if __name__ == "__main__":
    main()
