import csv
from dataclasses import dataclass
from pathlib import Path

from coverage.run_coverage import append_row, read_coverage, read_maven_project, run_pruned_jacoco
from llm.main import LLMCallMetrics
from pipeline_config import LLM_COVERAGE_CSV, LLM_RUNTIME_CSV, PipelineConfig


LLM_RUNTIME_FIELDNAMES = [
    "group_id",
    "artifact_id",
    "version",
    "total_classes_under_test",
    "total_llm_calls",
    "initial_generation_calls",
    "repair_calls",
    "total_llm_generation_time_seconds",
    "average_llm_generation_time_per_class_seconds",
    "total_pipeline_runtime_seconds",
    "average_pipeline_runtime_per_class_seconds",
    "total_prompt_tokens",
    "total_output_tokens",
    "number_of_repair_attempts",
]


@dataclass
class LibraryRuntimeMetrics:
    total_llm_calls: int = 0
    initial_generation_calls: int = 0
    repair_calls: int = 0
    total_llm_generation_time_ns: int = 0
    total_prompt_tokens: int = 0
    total_output_tokens: int = 0
    total_pipeline_runtime_seconds: float = 0.0

    def record_initial_call(self, metrics: LLMCallMetrics) -> None:
        self.initial_generation_calls += 1
        self.record_call(metrics)

    def record_repair_call(self, metrics: LLMCallMetrics) -> None:
        self.repair_calls += 1
        self.record_call(metrics)

    def record_call(self, metrics: LLMCallMetrics) -> None:
        self.total_llm_calls += 1
        self.total_llm_generation_time_ns += metrics.total_duration_ns
        self.total_prompt_tokens += metrics.prompt_tokens
        self.total_output_tokens += metrics.output_tokens


def append_library_coverage(config: PipelineConfig, testable_source_files: int, generated_test_classes: int) -> None:
    """Run JaCoCo once for the completed library and append its coverage row."""
    print(f"\nRunning JaCoCo coverage for completed library: {config.library}")
    project = read_maven_project(config.library_path)
    _, prune_result = run_pruned_jacoco(project.path, 300)
    append_row(
        read_coverage(
            project,
            testable_source_files=testable_source_files,
            generated_test_classes=generated_test_classes,
            test_counts=prune_result.test_counts,
        ),
        LLM_COVERAGE_CSV,
    )
    print(f"Coverage row written to {LLM_COVERAGE_CSV}")


def append_zero_library_coverage(config: PipelineConfig, testable_source_files: int) -> None:
    """Append a zero-coverage row when no generated test class survived."""
    project = read_maven_project(config.library_path)
    append_row(
        {
            "group_id": project.group_id,
            "artifact_id": project.artifact_id,
            "version": project.version,
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
        },
        LLM_COVERAGE_CSV,
    )
    print(f"Zero coverage row written to {LLM_COVERAGE_CSV}")


def append_library_runtime_metrics(
    config: PipelineConfig,
    total_classes_under_test: int,
    metrics: LibraryRuntimeMetrics,
) -> None:
    """Append one per-library runtime and LLM usage row."""
    project = read_maven_project(config.library_path)
    total_llm_seconds = metrics.total_llm_generation_time_ns / 1_000_000_000
    total_pipeline_seconds = metrics.total_pipeline_runtime_seconds
    row = {
        "group_id": project.group_id,
        "artifact_id": project.artifact_id,
        "version": project.version,
        "total_classes_under_test": str(total_classes_under_test),
        "total_llm_calls": str(metrics.total_llm_calls),
        "initial_generation_calls": str(metrics.initial_generation_calls),
        "repair_calls": str(metrics.repair_calls),
        "total_llm_generation_time_seconds": f"{total_llm_seconds:.4f}",
        "average_llm_generation_time_per_class_seconds": average_seconds(total_llm_seconds, total_classes_under_test),
        "total_pipeline_runtime_seconds": f"{total_pipeline_seconds:.4f}",
        "average_pipeline_runtime_per_class_seconds": average_seconds(total_pipeline_seconds, total_classes_under_test),
        "total_prompt_tokens": str(metrics.total_prompt_tokens),
        "total_output_tokens": str(metrics.total_output_tokens),
        "number_of_repair_attempts": str(config.attempts),
    }
    append_csv_row(LLM_RUNTIME_CSV, LLM_RUNTIME_FIELDNAMES, row)
    print(f"Runtime metrics row written to {LLM_RUNTIME_CSV}")


def append_csv_row(output_path: Path, fieldnames: list[str], row: dict[str, str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    should_write_header = not output_path.exists() or output_path.stat().st_size == 0
    with open(output_path, "a", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if should_write_header:
            writer.writeheader()
        writer.writerow(row)


def average_seconds(total_seconds: float, count: int) -> str:
    if count == 0:
        return ""
    return f"{total_seconds / count:.4f}"
