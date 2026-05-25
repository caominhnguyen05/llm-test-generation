from openai import OpenAI
from ollama import chat
import time
from dataclasses import dataclass

from llm.config import (
    SYSTEM_PROMPT,
    LLM_TIMEOUT_SECONDS,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
    LLM_TEMPERATURE,
    LLM_SEED,
)


class LLMGenerationTimeoutError(TimeoutError):
    pass

@dataclass(frozen=True)
class LLMCallMetrics:
    total_duration_ns: int = 0
    prompt_tokens: int = 0
    output_tokens: int = 0

client = OpenAI(
    base_url=OPENROUTER_BASE_URL,
    api_key=OPENROUTER_API_KEY,
)


def generate_llm_response_openrouter(
    prompt: str,
) -> tuple[str, LLMCallMetrics]:
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY environment variable is not set.")

    started_at = time.monotonic()
    llm_output = ""
    prompt_tokens = 0
    output_tokens = 0

    response = client.chat.completions.create(
        model=OPENROUTER_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=LLM_TEMPERATURE,
        seed=LLM_SEED,
        stream=True,
        stream_options={"include_usage": True},
    )

    for chunk in response:
        if time.monotonic() - started_at > LLM_TIMEOUT_SECONDS:
            raise LLMGenerationTimeoutError(
                f"LLM generation exceeded {LLM_TIMEOUT_SECONDS} seconds"
            )

        if hasattr(chunk, "usage") and chunk.usage is not None:
            prompt_tokens = chunk.usage.prompt_tokens or 0
            output_tokens = chunk.usage.completion_tokens or 0

        if chunk.choices and len(chunk.choices) > 0:
            token = chunk.choices[0].delta.content or ""
            print(token, end="", flush=True)
            llm_output += token

    duration_ns = int((time.monotonic() - started_at) * 1_000_000_000)

    print("\n\nGeneration complete.\n")

    metrics = LLMCallMetrics(
        total_duration_ns=duration_ns,
        prompt_tokens=prompt_tokens,
        output_tokens=output_tokens,
    )
    return llm_output, metrics


def generate_llm_response_ollama(prompt: str, model: str) -> tuple[str, LLMCallMetrics]:
    stream = chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        stream=True,
        options={
            "temperature": LLM_TEMPERATURE,
            "seed": LLM_SEED,
        }
    )

    llm_output = ""
    metrics = LLMCallMetrics()
    started_at = time.monotonic()
    for chunk in stream:
        if time.monotonic() - started_at > LLM_TIMEOUT_SECONDS:
            raise LLMGenerationTimeoutError(f"LLM generation exceeded {LLM_TIMEOUT_SECONDS} seconds")
        if chunk.get("done"):
            metrics = LLMCallMetrics(
                total_duration_ns=int(chunk.get("total_duration") or 0),
                prompt_tokens=int(chunk.get("prompt_eval_count") or 0),
                output_tokens=int(chunk.get("eval_count") or 0),
            )
        token = chunk.get("message", {}).get("content", "")
        print(token, end="", flush=True)
        llm_output += token
    print("\n\nGeneration complete.\n")
    return llm_output, metrics


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