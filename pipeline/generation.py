from llm.client import generate_llm_response
from llm.prompts import get_generation_prompt, get_repair_prompt
from pipeline.metrics import CostMetrics
from pipeline.postprocess import postprocess_test_code


def generate_initial_test(
    source_code: str,
    package_name: str,
    class_name: str,
    llm_backend: str,
    metrics: CostMetrics,
) -> str:
    """Ask the LLM to generate the first version of the JUnit test class."""
    print(f"\n[Attempt 0] Asking LLM to generate test class for {class_name} in {package_name}...")
    llm_output, call_metrics = generate_llm_response(
        get_generation_prompt(source_code, package_name, class_name),
        llm_backend,
    )
    
    metrics.record_call(call_metrics)
    return postprocess_test_code(llm_output, package_name, class_name, source_code)


def generate_repair_test(
    test_code: str,
    error_message: str,
    source_code: str,
    package_name: str,
    class_name: str,
    llm_backend: str,
    metrics: CostMetrics,
) -> str:
    """Ask the LLM to repair a generated test after validation fails."""
    print(f"Asking LLM to repair the test for {class_name} in {package_name}...")

    llm_output, call_metrics = generate_llm_response(
        get_repair_prompt(test_code, error_message, source_code, package_name, class_name),
        llm_backend,
    )

    metrics.record_repair_call(call_metrics)

    return postprocess_test_code(llm_output, package_name, class_name, source_code)