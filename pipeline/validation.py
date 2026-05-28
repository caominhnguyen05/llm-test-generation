from dataclasses import dataclass
from pipeline.maven import compile_test, execute_test
from pipeline.config import LibConfig


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    stage: str
    message: str = ""


def validate_structure(test_code: str, test_class: str) -> ValidationResult:
    issues = []
    if f"public class {test_class}" not in test_code:
        issues.append(f"missing public class {test_class} declaration")
    if "@Test" not in test_code:
        issues.append("missing @Test method annotation")

    if issues:
        return ValidationResult(False, "structure", ", ".join(issues))
    return ValidationResult(True, "structure")


def validate_compile(config: LibConfig, test_class: str) -> ValidationResult:
    success, output = compile_test(config.library_path, test_class)
    return ValidationResult(success, "compile", output)


def validate_test(config: LibConfig, test_class: str) -> ValidationResult:
    """Validate a generated test through compile and runtime checks."""
    compile_result = validate_compile(config, test_class)
    if not compile_result.passed:
        return compile_result

    success, output = execute_test(config.library_path, test_class)
    if not success:
        return ValidationResult(False, "runtime", output)

    return ValidationResult(True, "complete", output)