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
    local_llm = load_coverage_csv(root_dir / "results" / "final" / "local_llm" / "coverage.csv")
    cloud_llm = load_coverage_csv(
        root_dir / "results" / "final" / "cloud_llm" / "coverage.csv"
    )
    evosuite = load_coverage_csv(root_dir / "datasets" / "evosuite_baseline.csv")

    local_llm["source"] = "Qwen 2.5-Coder-7B"
    cloud_llm["source"] = "Deepseek V4 Flash"
    evosuite["source"] = "EvoSuite"

    # Find libraries that exist in all CSV files.
    common_libraries = local_llm[KEY_COLUMNS].drop_duplicates().merge(
        cloud_llm[KEY_COLUMNS].drop_duplicates(), on=KEY_COLUMNS
    )
    common_libraries = common_libraries.merge(
        evosuite[KEY_COLUMNS].drop_duplicates(), on=KEY_COLUMNS
    )

    if common_libraries.empty:
        raise ValueError(
            "No matching rows found across qwen, Deepseek, and EvoSuite CSV files."
        )

    df = pd.concat([local_llm, cloud_llm, evosuite], ignore_index=True)
    df = df.merge(common_libraries, on=KEY_COLUMNS, how="inner")

    # Keep only the columns needed for summary and plotting.
    df = df[KEY_COLUMNS + COVERAGE_COLUMNS + ["source"]]

    output_dir = root_dir / "results" / "figures"
    output_dir.mkdir(exist_ok=True)

    # Create grouped bar chart from median coverage values.
    plt.figure(figsize=(11, 5.4))

    metrics = list(METRIC_LABELS.values())
    x_positions = list(range(len(COVERAGE_COLUMNS)))
    bar_width = 0.26
    series_order = ["Qwen 2.5-Coder-7B", "Deepseek V4 Flash", "EvoSuite"]

    colors = {
        "Qwen 2.5-Coder-7B": "#4C72B0",
        "Deepseek V4 Flash": "#55A868",
        "EvoSuite": "#DD8452",
    }

    median_coverage = df.groupby("source")[COVERAGE_COLUMNS].median()
    offsets = [-bar_width, 0, bar_width]
    all_bars = []

    for source, offset in zip(series_order, offsets):
        values = [median_coverage.loc[source, column] for column in COVERAGE_COLUMNS]
        positions = [x + offset for x in x_positions]
        bars = plt.bar(
            positions,
            values,
            width=bar_width,
            color=colors[source],
            label=source,
        )
        all_bars.append(bars)

    for bars in all_bars:
        for bar in bars:
            height = bar.get_height()
            plt.text(
                bar.get_x() + bar.get_width() / 2,
                height + 1,
                f"{height:.1f}",
                ha="center",
                va="bottom",
                fontsize=12,
            )

    plt.xticks(x_positions, metrics, rotation=45, ha="right", fontsize=15)
    plt.legend(fontsize=12, title_fontsize=13)
    plt.ylabel("Coverage (%)", fontsize=15)
    plt.ylim(0, 110)
    plt.tight_layout()

    plt.savefig(output_dir / "rq4_barchart.pdf")
    plt.close()

    print(f"\nMatched {len(common_libraries)} libraries across all CSV files.")
    print(f"Saved plot to {output_dir / 'rq4_barchart.pdf'}")


if __name__ == "__main__":
    main()
