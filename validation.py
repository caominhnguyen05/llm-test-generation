from dataclasses import dataclass

from maven_helpers import run_maven_test_compile, run_maven_test_runtime
from pipeline_config import PipelineConfig
from postprocess import test_class_syntax_check


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    stage: str
    message: str = ""


def validate_syntax(test_code: str, class_name: str) -> ValidationResult:
    issues = test_class_syntax_check(test_code, class_name)
    if issues:
        return ValidationResult(False, "syntax", ", ".join(issues))
    return ValidationResult(True, "syntax")


def validate_compile(config: PipelineConfig, test_class: str) -> ValidationResult:
    success, output = run_maven_test_compile(config.library_path, test_class)
    if not success:
        return ValidationResult(False, "compile", output)
    return ValidationResult(True, "compile")


def validate_runtime(config: PipelineConfig, test_class: str) -> ValidationResult:
    success, output = run_maven_test_runtime(config.library_path, test_class)
    if not success:
        return ValidationResult(False, "runtime", output)
    return ValidationResult(True, "runtime", output)
