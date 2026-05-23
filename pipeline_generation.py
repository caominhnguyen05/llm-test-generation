from pipeline_config import PipelineConfig
from llm.config import OLLAMA_MODEL, LLM_BACKEND
from llm.main import (
    LLMCallMetrics,
    generate_llm_response_ollama,
    generate_llm_response_openrouter,
    get_generation_prompt,
    get_repair_prompt,
)
from pipeline_metrics import LibraryRuntimeMetrics
from postprocess import normalize_test_code
from validation import ValidationResult, validate_compile, validate_runtime, validate_structure


def generate_llm_response(prompt: str) -> tuple[str, LLMCallMetrics]:
    """Route LLM calls through the backend selected in the pipeline config."""
    if LLM_BACKEND == "openrouter":
        return generate_llm_response_openrouter(prompt)
    if LLM_BACKEND == "ollama":
        return generate_llm_response_ollama(prompt, model=OLLAMA_MODEL)
    raise ValueError(f"Unsupported LLM backend: {LLM_BACKEND!r}")


def generate_initial_test(
    source_code: str,
    package_name: str,
    class_name: str,
    metrics: LibraryRuntimeMetrics | None = None,
) -> str:
    """Ask the LLM to generate the first version of the JUnit test class."""
    print(f"\n[Attempt 0] Asking LLM to generate test class for {class_name} in {package_name}...")
    llm_output, call_metrics = generate_llm_response(
        get_generation_prompt(source_code, package_name, class_name),
    )
    if metrics is not None:
        metrics.record_initial_call(call_metrics)
    return normalize_test_code(llm_output, package_name, class_name, source_code)


def generate_repair_test(
    test_code: str,
    validation_result: ValidationResult,
    source_code: str,
    package_name: str,
    class_name: str,
    metrics: LibraryRuntimeMetrics | None = None,
) -> str:
    """Ask the LLM to repair a generated test after validation fails."""
    print(f"Asking LLM to repair the test for {class_name} in {package_name}...")
    llm_output, call_metrics = generate_llm_response(
        get_repair_prompt(test_code, validation_result.message, source_code, package_name, class_name),
    )
    
    if metrics is not None:
        metrics.record_repair_call(call_metrics)
    return normalize_test_code(llm_output, package_name, class_name, source_code)


def validate_test(config: PipelineConfig, test_code: str, test_class: str) -> ValidationResult:
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