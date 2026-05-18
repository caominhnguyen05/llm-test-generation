import csv
from dataclasses import replace
from pathlib import Path

from pipeline_config import parse_args
from pipeline_runner import run_library_pipeline


def read_libraries_csv(csv_path: Path) -> list[str]:
    """Read Maven coordinates from a CSV file."""
    libraries: list[str] = []

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

    libraries = read_libraries_csv(config.libraries_csv)

    for index, library in enumerate(libraries, start=1):
        print(f"\n==============================")
        print(f"Running library {index}/{len(libraries)}: {library}")
        print(f"==============================")

        library_config = replace(config, library=library)
        run_library_pipeline(library_config)


if __name__ == "__main__":
    main()