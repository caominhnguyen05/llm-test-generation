import csv
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from library_prep.prep_library import download_artifacts, extract_source_jar
from pipeline.config import parse_coordinate
from pipeline.preprocess import find_testable_sources

INPUT_CSV = REPO_ROOT / "csv_data" / "evosuite_original.csv"
OUTPUT_CSV = REPO_ROOT / "csv_data" / "small_libraries.csv"
DEFAULT_LIBRARIES_ROOT = REPO_ROOT / "libraries_evosuite_original"
MAX_TESTABLE_SOURCES = 35

FIELDNAMES = [
    "group_id",
    "artifact_id",
    "version",
    "original_java_files",
    "testable_java_sources",
]


@dataclass(frozen=True)
class SourceScanConfig:
    library: str
    libraries_root: Path

    @property
    def group_id(self) -> str:
        return parse_coordinate(self.library)[0]

    @property
    def artifact_id(self) -> str:
        return parse_coordinate(self.library)[1]

    @property
    def version(self) -> str:
        return parse_coordinate(self.library)[2]

    @property
    def library_path(self) -> Path:
        return self.libraries_root / self.group_id / self.artifact_id / self.version

    @property
    def source_folder(self) -> Path:
        return self.library_path / "prompt_sources"


def read_coordinates(csv_path: Path) -> list[str]:
    coordinates: list[str] = []
    seen: set[str] = set()

    with csv_path.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            coordinate = f"{row['group_id'].strip()}:{row['artifact_id'].strip()}:{row['version'].strip()}"
            if coordinate not in seen:
                seen.add(coordinate)
                coordinates.append(coordinate)

    return coordinates


def count_java_sources(config: SourceScanConfig) -> int:
    return sum(1 for _ in config.source_folder.rglob("*.java"))


def write_rows(output_csv: Path, rows: list[dict[str, str]]) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def find_small_libraries(
    input_csv: Path,
    output_csv: Path,
    libraries_root: Path,
) -> None:
    rows: list[dict[str, str]] = []

    for coordinate in read_coordinates(input_csv):
        config = SourceScanConfig(coordinate, libraries_root)
        print(f"\nScanning {coordinate}...")

        try:
            if not download_artifacts(config):
                print(f"Skipping {coordinate}: artifact download failed.")
                continue

            if not extract_source_jar(config):
                print(f"Skipping {coordinate}: source extraction failed.")
                continue

            original_java_files = count_java_sources(config)
            testable_sources = find_testable_sources(config)
            testable_count = len(testable_sources)

            if testable_count < MAX_TESTABLE_SOURCES:
                rows.append(
                    {
                        "group_id": config.group_id,
                        "artifact_id": config.artifact_id,
                        "version": config.version,
                        "original_java_files": str(original_java_files),
                        "testable_java_sources": str(testable_count),
                    }
                )
                print(f"Added {coordinate}: {testable_count}/{original_java_files} testable sources.")
            else:
                print(f"Skipped {coordinate}: {testable_count} testable sources.")
        finally:
            shutil.rmtree(config.library_path, ignore_errors=True)

    write_rows(output_csv, rows)
    print(f"\nWrote {len(rows)} row(s) to {output_csv}")


def main() -> None:
    find_small_libraries(
        input_csv=INPUT_CSV,
        output_csv=OUTPUT_CSV,
        libraries_root=DEFAULT_LIBRARIES_ROOT,
    )


if __name__ == "__main__":
    main()
