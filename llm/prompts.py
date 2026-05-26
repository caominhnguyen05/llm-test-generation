def get_generation_prompt(source_code: str, package_name: str, class_name: str) -> str:
    return f"""
    Generate a complete, compilable JUnit 4 test class for the following Java source code.

    Target Details:
    - Package: {package_name}
    - Class to test: {class_name}
    - Test Class Name: {class_name}Test

    Strict Requirements:
    1. Output only valid Java code inside a single ```java ``` block. Do not include any explanations, introduction, or post-text.
    2. Ensure the test class is `public` and includes all necessary imports (JUnit 4, Mockito if needed, and standard libraries).
    3. Every test method must use the `@Test` annotation and include explicit, clear assertions.
    4. Use only constructors, methods, fields, constants, nested classes, and enum values that exist in the provided source or standard Java/JUnit libraries.
    5. Test only publicly accessible behavior, focusing on boundary cases, branch coverage, and explicitly thrown exceptions. Do not test private methods.
    6. Do not use external files, network/database connections, or assume environment-specific variables. Keep tests deterministic and fast.

    Handling Abstract Classes and Interfaces:
    - If the target class is an `interface` or an `abstract class`, do not try to instantiate it directly.
    - Instead, create a minimal, concrete package-private static inner subclass (or anonymous class) within the test class, or use Mockito to mock it, to thoroughly test its implemented methods and default behavior.

    Source Code:
    ```java
    {source_code}
    ```
    """


def get_repair_prompt(
    test_code: str,
    error_output: str,
    source_code: str,
    package_name: str,
    class_name: str,
) -> str:
    return f"""
    Repair the generated JUnit 4 test file for the Java class below.

    Target:
    - Package: {package_name}
    - Test class name: {class_name}Test
    - The test class must be public.

    Repair goals, in priority order:
    1. Make the test class compile.
    2. Make all tests pass.
    3. Preserve existing valid tests.
    4. Replace invalid tests with valid tests that cover similar behavior where possible.
    5. Add focused tests for important source behavior, branches, boundary cases, or exceptions when this can be done safely.

    Repair rules:
    1. Use only APIs, constructors, methods, fields, constants, nested classes, and enum values that exist in the provided source or standard Java/JUnit libraries.
    2. If the error is cannot find symbol, remove or replace the unavailable API usage with valid source-supported behavior.
    3. If an assertion fails, adjust the expected value only when the source code or validation output shows that the generated expectation was wrong.
    4. If an expected exception is not thrown, remove or replace that invalid exception expectation.
    5. Do not delete tests merely to make the build pass.
    6. Do not shrink the test class to a minimal smoke test unless the source provides no other meaningful behavior.
    7. Do not add comments or explanations.

    Source under test:
    ```java
    {source_code}
    ```

    Failing test code:
    ```java
    {test_code}
    ```

    Validation output:
    ```text
    {error_output}
    ```
    """