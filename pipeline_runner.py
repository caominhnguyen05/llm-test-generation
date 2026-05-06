from pathlib import Path

from llm_helpers import call_llm_stream, get_generation_prompt, get_repair_prompt
from maven_helpers import run_maven_test
from pipeline_config import PipelineConfig
from pipeline_utils import extract_package_and_class, normalize_test_code, quick_syntax_check, read_file, write_file


def validate_inputs(config: PipelineConfig) -> bool:
    if not config.library_path.exists():
        print(f"Error: library folder not found: {config.library_path}")
        return False
    if not config.target_java_file.exists():
        print(f"Error: source file not found: {config.target_java_file}")
        return False
    return True


def save_test_code(output_test_file: Path, test_code: str, class_name: str, label: str) -> None:
    syntax_issues = quick_syntax_check(test_code, class_name)
    if syntax_issues:
        print(f"Quick syntax warnings before Maven: {', '.join(syntax_issues)}")
    write_file(output_test_file, test_code)
    print(f"{label} test saved to {output_test_file}")


def generate_initial_test(config: PipelineConfig, source_code: str, package_name: str, class_name: str) -> str:
    print(f"\n[Attempt 0] Asking Ollama ({config.model}) to generate tests...")
    llm_output = call_llm_stream(get_generation_prompt(source_code, package_name, class_name), config.model)
    return normalize_test_code(llm_output, package_name, class_name)


def repair_test(
    config: PipelineConfig,
    test_code: str,
    error_output: str,
    source_code: str,
    package_name: str,
    class_name: str,
) -> str:
    llm_output = call_llm_stream(
        get_repair_prompt(test_code, error_output, source_code, package_name, class_name),
        config.model,
    )
    return normalize_test_code(llm_output, package_name, class_name)


def run_pipeline(config: PipelineConfig) -> None:
    if not validate_inputs(config):
        return

    package_name, class_name = extract_package_and_class(config.target_java_file, config.source_root)
    output_test_file = config.test_root / package_name.replace(".", "/") / f"{class_name}Test.java"

    source_code = read_file(config.target_java_file)
    print(f"Library: {config.library}")
    print(f"Source: {config.target_java_file}")
    print(f"Package: {package_name}")
    print(f"Class: {class_name}")
    print(f"Output: {output_test_file}")

    test_code = generate_initial_test(config, source_code, package_name, class_name)
    save_test_code(output_test_file, test_code, class_name, "Initial")

    for attempt in range(config.attempts + 1):
        success, error_output = run_maven_test(config.library_path, f"{class_name}Test")
        if success:
            print(f"SUCCESS: test compiled and passed on attempt {attempt}.")
            return

        if attempt >= config.attempts:
            print(f"FAILURE: max repair attempts ({config.attempts}) reached.")
            print(error_output)
            return

        print(f"FAILED. Starting repair loop {attempt + 1}/{config.attempts}...")
        test_code = repair_test(config, test_code, error_output, source_code, package_name, class_name)
        save_test_code(output_test_file, test_code, class_name, "Repaired")
