import csv
from dataclasses import dataclass
from pathlib import Path

from coverage.config import FIELDNAMES as COVERAGE_FIELDNAMES
from coverage.main import collect_coverage_after_ignoring_failures
from coverage.jacoco import build_coverage_row
from llm.main import LLMCallMetrics
from pipeline_config import COVERAGE_CSV, COST_CSV, PipelineConfig


COST_FIELDNAMES = [
    "group_id",
    "artifact_id",
    "version",
    "total_classes_under_test",
    "total_llm_calls",
    "repair_calls",
    "total_llm_generation_time_seconds",
    "total_pipeline_runtime_seconds",
    "total_prompt_tokens",
    "total_output_tokens",
    "number_of_repair_attempts",
]


def append_csv_row(output_path: Path, fieldnames: list[str], row: dict[str, str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    should_write_header = not output_path.exists() or output_path.stat().st_size == 0

    with open(output_path, "a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if should_write_header:
            writer.writeheader()
        writer.writerow({fieldname: row.get(fieldname, "") for fieldname in fieldnames})


def library_coordinates(config: PipelineConfig) -> dict[str, str]:
    return {
        "group_id": config.group_id,
        "artifact_id": config.artifact_id,
        "version": config.version,
    }


@dataclass
class LibraryRuntimeMetrics:
    total_llm_calls: int = 0
    repair_calls: int = 0
    total_llm_generation_time_ns: int = 0
    total_prompt_tokens: int = 0
    total_output_tokens: int = 0
    total_pipeline_runtime_seconds: float = 0.0

    def record_call(self, metrics: LLMCallMetrics) -> None:
        self.total_llm_calls += 1
        self.total_llm_generation_time_ns += metrics.total_duration_ns
        self.total_prompt_tokens += metrics.prompt_tokens
        self.total_output_tokens += metrics.output_tokens

    def record_repair_call(self, metrics: LLMCallMetrics) -> None:
        self.repair_calls += 1
        self.record_call(metrics)


def append_library_coverage(config: PipelineConfig, testable_source_files: int, generated_test_classes: int) -> None:
    """Run JaCoCo once for the completed library and append its coverage row."""
    print(f"\nRunning JaCoCo coverage for completed library: {config.library}")

    prep_result = collect_coverage_after_ignoring_failures(config.library_path, 300)

    row = build_coverage_row(
        config,
        testable_source_files=testable_source_files,
        generated_test_classes=generated_test_classes,
        test_counts=prep_result.test_counts,
    )
    append_csv_row(COVERAGE_CSV, COVERAGE_FIELDNAMES, row)
    print(f"Coverage row written to {COVERAGE_CSV}")


def append_zero_coverage_row(config: PipelineConfig, testable_source_files: int) -> None:
    """Append a zero-coverage row when no generated test class compiled."""
    row = library_coordinates(config) | {
        "source": "LLM",
        "instruction_coverage": "0",
        "branch_coverage": "0",
        "line_coverage": "0",
        "complexity_coverage": "0",
        "method_coverage": "0",
        "class_coverage": "0",
        "testable_source_files": str(testable_source_files),
        "generated_test_classes": "0",
        "compilation_success_rate": "0",
        "tests_total": "0",
        "tests_passed": "0",
        "tests_failed_assertions": "0",
        "tests_runtime_errors": "0",
        "runtime_success_rate": "0",
        "failed_assertion_rate": "0",
        "runtime_error_rate": "0",
    }

    append_csv_row(COVERAGE_CSV, COVERAGE_FIELDNAMES, row)
    print(f"Zero coverage row written to {COVERAGE_CSV}")


def append_library_runtime_metrics(
    config: PipelineConfig,
    total_classes_under_test: int,
    metrics: LibraryRuntimeMetrics,
) -> None:
    row = library_coordinates(config) | {
        "total_classes_under_test": str(total_classes_under_test),
        "total_llm_calls": str(metrics.total_llm_calls),
        "repair_calls": str(metrics.repair_calls),
        "total_llm_generation_time_seconds": f"{metrics.total_llm_generation_time_ns / 1_000_000_000:.4f}",
        "total_pipeline_runtime_seconds": f"{metrics.total_pipeline_runtime_seconds:.4f}",
        "total_prompt_tokens": str(metrics.total_prompt_tokens),
        "total_output_tokens": str(metrics.total_output_tokens),
        "number_of_repair_attempts": str(config.attempts),
    }

    append_csv_row(COST_CSV, COST_FIELDNAMES, row)
    print(f"Cost metrics row written to {COST_CSV}")