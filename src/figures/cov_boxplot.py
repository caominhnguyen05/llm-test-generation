from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


KEY_COLUMNS = ["group_id", "artifact_id", "version"]
COVERAGE_COLUMNS = [
    "line_coverage",
    "branch_coverage",
    "method_coverage",
    "class_coverage",
    "instruction_coverage",
    "complexity_coverage",
]
METRIC_LABELS = {
    "line_coverage": "Line",
    "branch_coverage": "Branch",
    "method_coverage": "Method",
    "class_coverage": "Class",
    "instruction_coverage": "Instruction",
    "complexity_coverage": "Complexity",
}


def format_percent(value: float) -> str:
    return f"{value:.2f}"


def load_coverage_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype=str)

    for column in KEY_COLUMNS:
        df[column] = df[column].fillna("").str.strip()

    df = df[df[KEY_COLUMNS].ne("").all(axis=1)].copy()

    for column in COVERAGE_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    return df


def library_label(row: pd.Series) -> str:
    return f"{row['group_id']}:{row['artifact_id']}:{row['version']}"


def main() -> None:
    root_dir = Path(__file__).resolve().parents[2]

    llm_csv = root_dir / "results" / "final" / "local_llm" / "coverage.csv"
    evosuite_csv = root_dir / "datasets" / "evosuite_baseline.csv"

    output_dir = root_dir / "results" / "figures"
    output_dir.mkdir(exist_ok=True)

    llm = load_coverage_csv(llm_csv)
    evosuite = load_coverage_csv(evosuite_csv)

    common_libraries = llm[KEY_COLUMNS].drop_duplicates().merge(
        evosuite[KEY_COLUMNS].drop_duplicates(), on=KEY_COLUMNS
    )

    if common_libraries.empty:
        raise ValueError("No matching rows found between LLM and EvoSuite CSV files.")

    df = pd.concat([llm, evosuite], ignore_index=True)
    df = df.merge(common_libraries, on=KEY_COLUMNS, how="inner")
    df = df[KEY_COLUMNS + COVERAGE_COLUMNS + ["source"]]

    summary_stats = df.groupby("source")[COVERAGE_COLUMNS].agg(["mean", "median"])
    table_rows = []
    for column in COVERAGE_COLUMNS:
        table_rows.append(
            (
                METRIC_LABELS[column],
                format_percent(summary_stats.loc["LLM", (column, "mean")]),
                format_percent(summary_stats.loc["LLM", (column, "median")]),
                format_percent(summary_stats.loc["EVOSUITE", (column, "mean")]),
                format_percent(summary_stats.loc["EVOSUITE", (column, "median")]),
            )
        )

    latex_lines = [
        r"\begin{table}[htbp]",
        r"\centering",
        r"\small",
        rf"\caption{{Mean and median coverage percentages achieved by LLM-generated tests and EvoSuite-generated tests across the {len(common_libraries)} sample libraries.}}",
        r"\label{tab:coverage-summary}",
        r"\begin{tabularx}{\columnwidth}{@{} X r r c r r @{}}",
        r"\toprule",
        r" & \multicolumn{2}{c}{\textbf{LLM}} & & \multicolumn{2}{c}{\textbf{EvoSuite}} \\",
        r"\cmidrule{2-3} \cmidrule{5-6}",
        r"\textbf{Coverage Metric} & \textbf{Mean} & \textbf{Median} & & \textbf{Mean} & \textbf{Median} \\",
        r"\midrule",
    ]
    latex_lines.extend(
        f"{metric:<11} & {llm_mean} & {llm_median} & & {evosuite_mean} & {evosuite_median} \\\\"
        for metric, llm_mean, llm_median, evosuite_mean, evosuite_median in table_rows
    )
    latex_lines.extend(
        [
            r"\bottomrule",
            r"\end{tabularx}",
            r"\end{table}",
        ]
    )

    table_path = output_dir / "rq1_coverage_table.tex"
    plot_path = output_dir / "rq1_boxplot.pdf"


    with open(table_path, "w", encoding="utf-8") as f:
        f.write("\n".join(latex_lines))
        f.write("\n")

    colors = {
        "LLM": "#4C72B0",
        "EVOSUITE": "#DD8452",
    }

    plt.figure(figsize=(12, 6))

    grouped_data = []
    positions = []
    metric_centers = []
    box_colors = []

    for index, column in enumerate(COVERAGE_COLUMNS):
        group_center = index * 2.4
        llm_position = group_center - 0.38
        evosuite_position = group_center + 0.38

        grouped_data.append(df.loc[df["source"] == "LLM", column].dropna())
        positions.append(llm_position)
        box_colors.append(colors["LLM"])

        grouped_data.append(df.loc[df["source"] == "EVOSUITE", column].dropna())
        positions.append(evosuite_position)
        box_colors.append(colors["EVOSUITE"])

        metric_centers.append(group_center)

    boxplot = plt.boxplot(
        grouped_data,
        positions=positions,
        widths=0.65,
        patch_artist=True,
        showmeans=True,
        meanprops={
            "marker": "D",
            "markerfacecolor": "white",
            "markeredgecolor": "#222222",
            "markersize": 5,
        },
        medianprops={"color": "#222222", "linewidth": 1.4},
        whiskerprops={"color": "#555555"},
        capprops={"color": "#555555"},
        flierprops={
            "marker": "o",
            "markerfacecolor": "#666666",
            "markeredgecolor": "#666666",
            "markersize": 3,
            "alpha": 0.45,
        },
    )

    for patch, color in zip(boxplot["boxes"], box_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.82)
        patch.set_edgecolor("#333333")

    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, facecolor=colors["LLM"], edgecolor="#333333", alpha=0.82),
        plt.Rectangle(
            (0, 0), 1, 1, facecolor=colors["EVOSUITE"], edgecolor="#333333", alpha=0.82
        ),
    ]

    plt.xticks(
        metric_centers,
        [METRIC_LABELS[column] for column in COVERAGE_COLUMNS],
        rotation=45,
        ha="right",
        fontsize=13,
    )
    plt.legend(
        legend_handles,
        ["LLM", "EvoSuite"],
        title="Approach",
        fontsize=12,
        title_fontsize=13,
        loc="upper left",
        bbox_to_anchor=(1.02, 1),
        frameon=False,
    )

    plt.ylabel("Coverage (%)", fontsize=14)
    plt.ylim(0, 110)

    plt.tight_layout(rect=(0, 0, 0.84, 1))

    plt.savefig(
        plot_path,
        bbox_inches="tight",
        pad_inches=0.03,
    )
    plt.close()

    print(f"\nMatched {len(common_libraries)} of {len(llm)} LLM row(s).")
    print(f"Saved plot to {plot_path}")
    print(f"Saved summary to {table_path}")


if __name__ == "__main__":
    main()