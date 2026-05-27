import csv
from dataclasses import dataclass
from pathlib import Path

from coverage.config import FIELDNAMES as COVERAGE_FIELDNAMES
from coverage.coverage_pipeline import run_coverage_after_ignoring_failures
from llm.client import LLMCallMetrics
from pipeline.config import PipelineConfig


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

    with open(output_path, "a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if not output_path.exists() or output_path.stat().st_size == 0:
            writer.writeheader()
        writer.writerow({fieldname: row.get(fieldname, "") for fieldname in fieldnames})


def library_coordinates(config: PipelineConfig) -> dict[str, str]:
    return {
        "group_id": config.group_id,
        "artifact_id": config.artifact_id,
        "version": config.version,
    }


@dataclass
class CostMetrics:
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


def append_library_coverage(
    config: PipelineConfig,
    testable_source_files: int,
    generated_test_classes: int,
) -> None:
    """Append the completed library coverage row."""
    row = run_coverage_after_ignoring_failures(
        config,
        300,
        testable_source_files,
        generated_test_classes,
    )
    append_csv_row(config.coverage_csv, COVERAGE_FIELDNAMES, row)
    print(f"Coverage row written to {config.coverage_csv}")


def append_library_runtime_metrics(
    config: PipelineConfig,
    total_classes_under_test: int,
    metrics: CostMetrics,
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

    append_csv_row(config.cost_csv, COST_FIELDNAMES, row)
    print(f"Cost metrics row written to {config.cost_csv}")