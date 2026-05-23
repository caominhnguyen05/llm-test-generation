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
        temperature=0,
        seed=42,
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
            "temperature": 0,
            "seed": 42,
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
    - If an assertion fails, change the test expectation to match actual results shown in the error output.
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