from ollama import chat

from pipeline_config import SYSTEM_PROMPT


def call_llm_stream(prompt: str, model: str) -> str:
    stream = chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        stream=True,
    )
    llm_output = ""
    for chunk in stream:
        token = chunk["message"]["content"]
        print(token, end="", flush=True)
        llm_output += token
    print("\n\nGeneration complete.\n")
    return llm_output


def get_generation_prompt(source_code: str, package_name: str, class_name: str) -> str:
    return f"""
    Generate a complete JUnit 4 test class for the Java source below.

    Primary goal:
    Create a compiling, passing test class that covers meaningful behavior in `{class_name}`, including
    normal cases, boundary cases, exceptional cases, and null handling where the source supports them.

    Requirements:
    1. Package: `{package_name}`.
    2. Class name: The test MUST be named `{class_name}Test` and be declared `public`.
    3. Include all imports needed for JUnit 4 and assertions.
    4. Every test method must use @Test.
    5. Prefer deterministic, fast unit tests with no network, sleeps, randomness, or environment assumptions.
    6. Do not use APIs, constructors, methods, fields, or constants unless they exist in the source or standard/JUnit libraries.
    7. Do not test private implementation details unless they are package-private and directly relevant.
    8. If existing behavior implies multiple paths or states, create separate focused test methods for them.
    9. Output ONLY the complete raw Java code inside one ```java block. No comments or explanations.

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
    Repair the JUnit 4 test class for `{class_name}`.

    The current test failed during `mvn -q test -Dtest={class_name}Test`. Use the Maven output to identify
    the exact compilation or runtime failures, then return a corrected complete test file.

    Priorities, in order:
    1. The returned test class must compile.
    2. The returned tests must pass.
    3. The returned tests should preserve valid existing coverage.
    4. If the current test class misses important behavior in the source, add new focused test methods.

    Requirements:
    1. Keep package `{package_name}`.
    2. Keep public class name `{class_name}Test`.
    3. Use JUnit 4 only.
    4. Do not invent unavailable APIs, dependencies, constructors, methods, fields, or constants.
    5. Do not simply delete failing tests to make the build pass. If a test is invalid, replace it with a valid
       test for similar behavior.
    6. Add new test methods when the class under test has visible behavior, branches, edge cases, or exception
       paths not covered by the current test.
    7. Keep tests deterministic, fast, isolated, and focused on behavior visible from the source.
    8. Output ONLY the complete fixed raw Java code inside one ```java block.

    Package: `{package_name}`
    Class name: `{class_name}Test`

    Source under test:
    ```java
    {source_code}
    ```

    Failing test code:
    ```java
    {test_code}
    ```

    Maven output:
    ```text
    {error_output}
    ```
    """
