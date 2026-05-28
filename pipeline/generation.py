from llm.client import generate_llm_response
from llm.prompts import (
    get_generation_prompt,
    get_repair_prompt,
)
from pipeline.config import LibConfig
from pipeline.metrics import CostMetrics
from pipeline.postprocess import postprocess_test_code
from pipeline.experiment_logs import save_prompt, save_response, save_error


def create_initial_test(
    config: LibConfig,
    source_code: str,
    package_name: str,
    class_name: str,
    api_summary: str,
    metrics: CostMetrics,
) -> str:
    """Generate and postprocess the first version of the LLM-generated test class."""
    print(f"\n[Attempt 0] Asking LLM to generate test class for {class_name} in {package_name}...")
    prompt = get_generation_prompt(source_code, package_name, class_name, api_summary)
    save_prompt(config, class_name, package_name, "initial", prompt)

    llm_output, call_metrics = generate_llm_response(
        prompt,
        config.llm_backend,
    )
    save_response(config, class_name, package_name, "initial", llm_output)
    
    metrics.record_call(call_metrics)
    return postprocess_test_code(llm_output, package_name, class_name, source_code)


def create_repair_test(
    config: LibConfig,
    failed_test_code: str,
    error_message: str,
    source_code: str,
    package_name: str,
    class_name: str,
    api_summary: str,
    metrics: CostMetrics,
    repair_attempt: int,
) -> str:
    """Ask the LLM to repair a generated test after validation fails."""
    print(f"Asking LLM to repair the test for {class_name} in {package_name}...")
    phase = f"repair_{repair_attempt}"
    prompt = get_repair_prompt(failed_test_code, error_message, source_code, package_name, class_name, api_summary)
    save_prompt(config, class_name, package_name, phase, prompt)

    llm_output, call_metrics = generate_llm_response(
        prompt,
        config.llm_backend,
    )
    save_response(config, class_name, package_name, phase, llm_output)

    metrics.record_repair_call(call_metrics)

    return postprocess_test_code(llm_output, package_name, class_name, source_code)