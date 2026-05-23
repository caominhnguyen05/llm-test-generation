from dataclasses import dataclass
from maven_helpers import compile_test, execute_test
from pipeline_config import PipelineConfig


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    stage: str
    message: str = ""


def check_test_class_structure(test_code: str, class_name: str) -> list[str]:
    issues = []
    if f"public class {class_name}Test" not in test_code:
        issues.append(f"missing public class {class_name}Test declaration")
    if "@Test" not in test_code:
        issues.append("missing @Test method annotation")
    return issues


def validate_structure(test_code: str, class_name: str) -> ValidationResult:
    issues = check_test_class_structure(test_code, class_name)
    if issues:
        return ValidationResult(False, "structure", ", ".join(issues))
    return ValidationResult(True, "structure")


def validate_compile(config: PipelineConfig, test_class: str) -> ValidationResult:
    success, output = compile_test(config.library_path, test_class)
    if not success:
        return ValidationResult(False, "compile", output)
    return ValidationResult(True, "compile")


def validate_runtime(config: PipelineConfig, test_class: str) -> ValidationResult:
    success, output = execute_test(config.library_path, test_class)
    if not success:
        return ValidationResult(False, "runtime", output)
    return ValidationResult(True, "runtime", output)
