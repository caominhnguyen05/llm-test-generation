from ollama import chat
from llm.config import SYSTEM_PROMPT


def generate_llm_response(prompt: str, model: str) -> str:
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
        print(token, end="", flush=True) # Uncomment to see real-time test code generation
        llm_output += token
    print("\n\nGeneration complete.\n")
    return llm_output


def get_generation_prompt(source_code: str, package_name: str, class_name: str) -> str:
    return f"""
    Generate a complete JUnit 4 test class for the Java class below.

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
    You are repairing a generated JUnit 4 test file of a Java library class.

    Return ONLY one complete Java source file inside a single ```java block.
    Do not explain anything.
    Do not use markdown except the ```java block.
    The file MUST declare: public class {class_name}Test
    The package MUST be: {package_name}

    Repair goal:
    - Fix the test so it compiles and passes.
    - The source under test is assumed correct.
    - If an assertion fails, change the test expectation to match actual behavior shown in the error output.
    - If a test expects an exception that is not thrown, remove or replace that invalid expectation.
    - Do not invent APIs or dependencies.
    - Do not shrink the test class just to make it pass.
    - Preserve existing valid test methods whenever possible.
    - If you remove or simplify an invalid test, replace it with another meaningful passing test.
    - Add additional focused tests when the current test class misses important source behavior, branches, boundary cases, or exceptions.
    - Aim for a compiling, passing test class with broad behavior coverage, not the smallest passing test.

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
