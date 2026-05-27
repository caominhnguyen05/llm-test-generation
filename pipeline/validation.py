from dataclasses import dataclass
from pipeline.maven import compile_test, execute_test
from pipeline.config import PipelineConfig


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    stage: str
    message: str = ""


def validate_structure(test_code: str, class_name: str) -> ValidationResult:
    issues = []
    if f"public class {class_name}Test" not in test_code:
        issues.append(f"missing public class {class_name}Test declaration")
    if "@Test" not in test_code:
        issues.append("missing @Test method annotation")

    if issues:
        return ValidationResult(False, "structure", ", ".join(issues))
    return ValidationResult(True, "structure")


def validate_compile(config: PipelineConfig, test_class: str) -> ValidationResult:
    success, output = compile_test(config.library_path, test_class)
    return ValidationResult(success, "compile", output)


def validate_runtime(config: PipelineConfig, test_class: str) -> ValidationResult:
    success, output = execute_test(config.library_path, test_class)
    return ValidationResult(success, "runtime", output)

def validate_test(config: PipelineConfig, test_class: str) -> ValidationResult:
    """Validate a generated test through compile and runtime checks."""
    compile_result = validate_compile(config, test_class)
    if not compile_result.passed:
        return compile_result

    runtime_result = validate_runtime(config, test_class)
    if not runtime_result.passed:
        return runtime_result

    return ValidationResult(True, "complete", runtime_result.message)