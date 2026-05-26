import csv
from dataclasses import replace
from pathlib import Path

from pipeline_config import parse_args
from pipeline_runner import run_library_pipeline


def read_libraries_csv(csv_path: Path) -> list[str]:
    """Read Maven coordinates from a CSV file."""
    libraries = []

    with open(csv_path, "r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            group_id = row["group_id"].strip()
            artifact_id = row["artifact_id"].strip()
            version = row["version"].strip()

            libraries.append(f"{group_id}:{artifact_id}:{version}")

    return libraries


def main() -> None:
    config = parse_args()

    if config.libraries_csv is None:
        run_library_pipeline(config)
        return

    libraries_list = read_libraries_csv(config.libraries_csv)

    for index, library in enumerate(libraries_list, start=1):
        print(f"\n{'=' * 15}")
        print(f"Running library {index}/{len(libraries_list)}: {library}")
        print(f"{'=' * 15}")

        run_library_pipeline(replace(config, library=library))


if __name__ == "__main__":
    main()