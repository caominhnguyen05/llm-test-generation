from dataclasses import replace
from pathlib import Path

from llm.main import generate_llm_response, get_generation_prompt, get_repair_prompt
from pipeline_config import PipelineConfig
from postprocess import normalize_test_code, write_file
from preprocess import extract_package_and_class, read_source_file
from validation import ValidationResult, validate_compile, validate_runtime, validate_syntax


def iter_library_sources(config: PipelineConfig) -> list[Path]:
    """Return all Java source files in a library."""
    if not config.source_root.exists():
        print(f"Error: source root not found: {config.source_root}")
        return []
    ignored_files = {"package-info.java", "module-info.java"}
    return sorted(
        path.relative_to(config.source_root)
        for path in config.source_root.rglob("*.java")
        if path.name not in ignored_files
    )


def validate_inputs(config: PipelineConfig) -> bool:
    """Check that the selected library and source file exist before running."""
    if not config.library_path.exists():
        print(f"Error: library folder not found: {config.library_path}")
        return False
    if not config.target_java_file.exists():
        print(f"Error: source file not found: {config.target_java_file}")
        return False
    return True


def save_test_code(output_test_file: Path, test_code: str, class_name: str, label: str) -> None:
    """Save the generated test code to the library src/test/java folder, creating directories as needed."""
    syntax_result = validate_syntax(test_code, class_name)
    if not syntax_result.passed:
        print(f"Quick syntax warnings before Maven: {syntax_result.message}")
    write_file(output_test_file, test_code)
    print(f"{label} test saved to {output_test_file}")


def generate_initial_test(config: PipelineConfig, source_code: str, package_name: str, class_name: str) -> str:
    """Ask the LLM to generate the first version of the JUnit test class.

    The raw LLM response is normalized so the result is a complete Java test
    file with the expected package and class name.
    """
    print(f"\n[Attempt 0] Asking Ollama ({config.model}) to generate tests...")
    llm_output = generate_llm_response(
        get_generation_prompt(source_code, package_name, class_name),
        config.model,
    )
    return normalize_test_code(llm_output, package_name, class_name, source_code)


def generate_repair_test(
    config: PipelineConfig,
    test_code: str,
    validation_result: ValidationResult,
    source_code: str,
    package_name: str,
    class_name: str,
) -> str:
    """Ask the LLM to repair a generated test after validation fails.

    The repair prompt includes the current test, the source under test, and the
    validation error output so the model can fix syntax, compile, or runtime
    execution problems.
    """
    llm_output = generate_llm_response(
        get_repair_prompt(test_code, validation_result.message, source_code, package_name, class_name),
        config.model,
    )
    return normalize_test_code(llm_output, package_name, class_name, source_code)


def validate_generated_test(config: PipelineConfig, test_code: str, test_class: str) -> ValidationResult:
    """Validate a generated test through syntax, compile, and runtime checks.

    Validation stops at the first failing stage so the repair loop receives the
    most relevant error message. Runtime validation checks whether Maven can run
    the test class; depending on Maven settings, assertion failures may be kept.
    """
    syntax_result = validate_syntax(test_code, test_class.removesuffix("Test"))
    if not syntax_result.passed:
        return syntax_result

    compile_result = validate_compile(config, test_class)
    if not compile_result.passed:
        return compile_result

    runtime_result = validate_runtime(config, test_class)
    if not runtime_result.passed:
        return runtime_result

    return ValidationResult(True, "complete", runtime_result.message)


def run_pipeline(config: PipelineConfig) -> None:
    """Generate, save, validate, and repair a test for one Java source file.

    The pipeline reads the target source file, asks the LLM for an initial test,
    writes it to src/test/java, validates it, and then runs repair attempts until
    the test is valid or the configured repair limit is reached.
    """
    if not validate_inputs(config):
        return

    source_code = read_source_file(config.target_java_file)
    package_name, class_name = extract_package_and_class(config.target_java_file, config.source_root)
    test_class = f"{class_name}Test"
    output_test_file = config.test_root / package_name.replace(".", "/") / f"{test_class}.java"

    print(f"Library: {config.library}")
    print(f"Source: {config.target_java_file}")
    print(f"Package: {package_name}")
    print(f"Class: {class_name}")
    print(f"Output: {output_test_file}")

    test_code = generate_initial_test(config, source_code, package_name, class_name)
    save_test_code(output_test_file, test_code, class_name, "Initial")

    for attempt in range(config.attempts + 1):
        validation_result = validate_generated_test(config, test_code, test_class)
        if validation_result.passed:
            print(f"SUCCESS: test is syntactically valid, compiles, and is executable on attempt {attempt}.")
            return

        if attempt >= config.attempts:
            print(f"FAILURE: max repair attempts ({config.attempts}) reached.")
            print(validation_result.message)
            return

        print(f"{validation_result.stage.title()} validation failed.")
        print(validation_result.message)
        print(f"Starting repair loop {attempt + 1}/{config.attempts}...")
        
        test_code = generate_repair_test(
            config,
            test_code,
            validation_result,
            source_code,
            package_name,
            class_name,
        )
        save_test_code(output_test_file, test_code, class_name, "Repaired")


def run_library_pipeline(config: PipelineConfig) -> None:
    """Run the test-generation pipeline for every Java source file in a library.

    If one test class fails to compile or run, the error is logged and the pipeline
    continues with the next source file.
    """
    sources = iter_library_sources(config)
    if not sources:
        print(f"No Java source files found under {config.source_root}")
        return

    failures: list[tuple[Path, str]] = []
    print(f"Found {len(sources)} Java source files in {config.library}.")
    for index, source in enumerate(sources, start=1):
        print(f"\n=== [{index}/{len(sources)}] {source} ===")
        try:
            run_pipeline(replace(config, source=source))
        except Exception as exc:
            failures.append((source, str(exc)))
            print(f"ERROR: failed while processing {source}.")
            print(exc)
            print("Keeping any generated test file as-is and continuing with the next class.")

    if failures:
        print(f"\nCompleted with {len(failures)} failed source file(s):")
        for source, message in failures:
            print(f"- {source}: {message}")
