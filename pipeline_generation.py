from pipeline_config import PipelineConfig
from llm.main import generate_llm_response, get_generation_prompt, get_repair_prompt
from pipeline_metrics import LibraryRuntimeMetrics
from postprocess import normalize_test_code
from validation import ValidationResult, validate_compile, validate_runtime, validate_structure


def generate_initial_test(
    config: PipelineConfig,
    source_code: str,
    package_name: str,
    class_name: str,
    metrics: LibraryRuntimeMetrics | None = None,
) -> str:
    """Ask the LLM to generate the first version of the JUnit test class."""
    print(f"\n[Attempt 0] Asking Ollama ({config.model}) to generate tests...")
    llm_output, call_metrics = generate_llm_response(
        get_generation_prompt(source_code, package_name, class_name),
        config.model,
        return_metrics=True,
    )
    if metrics is not None:
        metrics.record_initial_call(call_metrics)
    return normalize_test_code(llm_output, package_name, class_name, source_code)


def generate_repair_test(
    config: PipelineConfig,
    test_code: str,
    validation_result: ValidationResult,
    source_code: str,
    package_name: str,
    class_name: str,
    metrics: LibraryRuntimeMetrics | None = None,
) -> str:
    """Ask the LLM to repair a generated test after validation fails."""
    print(f"Asking Ollama ({config.model}) to repair the test...")
    llm_output, call_metrics = generate_llm_response(
        get_repair_prompt(test_code, validation_result.message, source_code, package_name, class_name),
        config.model,
        return_metrics=True,
    )
    if metrics is not None:
        metrics.record_repair_call(call_metrics)
    return normalize_test_code(llm_output, package_name, class_name, source_code)


def validate_generated_test(config: PipelineConfig, test_code: str, test_class: str) -> ValidationResult:
    """Validate a generated test through structure, compile, and runtime checks."""
    structure_result = validate_structure(test_code, test_class.removesuffix("Test"))
    if not structure_result.passed:
        return structure_result

    compile_result = validate_compile(config, test_class)
    if not compile_result.passed:
        return compile_result

    runtime_result = validate_runtime(config, test_class)
    if not runtime_result.passed:
        return runtime_result

    return ValidationResult(True, "complete", runtime_result.message)
