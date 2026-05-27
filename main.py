import csv
from dataclasses import replace
from pathlib import Path

from pipeline_config import parse_args
from pipeline_runner import run_library_pipeline

def has_result_row(csv_path: Path, library: str) -> bool:
    if not csv_path.exists():
        return False

    group_id, artifact_id, version = library.split(":")

    with csv_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            if (
                row["group_id"] == group_id
                and row["artifact_id"] == artifact_id
                and row["version"] == version
            ):
                return True

    return False

def is_library_completed(config, library: str) -> bool:
    return (
        has_result_row(config.coverage_csv, library)
        and has_result_row(config.cost_csv, library)
    )

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

    if config.library is not None:
        libraries_list = [config.library]
    else:
        libraries_list = read_libraries_csv(config.libraries_csv)

    for index, library in enumerate(libraries_list, start=1):
        print(f"\n{'=' * 15}")
        print(f"Running library {index}/{len(libraries_list)}: {library}")
        print(f"{'=' * 15}")

        lib_config = replace(config, library=library)

        if is_library_completed(lib_config, library):
            print(f"Skipping {library}: coverage and cost rows already exist.")
            continue

        run_library_pipeline(lib_config)


if __name__ == "__main__":
    main()