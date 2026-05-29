from openai import OpenAI
from ollama import chat
import time
from dataclasses import dataclass

from llm.config import (
    OLLAMA_MODEL,
    OLLAMA_CONTEXT_SIZE,
    LLM_TIMEOUT_SECONDS,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
    LLM_TEMPERATURE,
    LLM_SEED,
)
from llm.prompts import SYSTEM_PROMPT


@dataclass(frozen=True)
class LLMCallMetrics:
    total_duration_ns: int = 0
    prompt_tokens: int = 0
    output_tokens: int = 0


class LLMTimeoutError(TimeoutError):
    def __init__(
        self,
        message: str,
        partial_output: str = "",
        metrics: LLMCallMetrics | None = None,
    ):
        super().__init__(message)
        self.partial_output = partial_output
        self.metrics = metrics or LLMCallMetrics(
            total_duration_ns=LLM_TIMEOUT_SECONDS * 1_000_000_000,
        )


client = OpenAI(
    base_url=OPENROUTER_BASE_URL,
    api_key=OPENROUTER_API_KEY,
)

def generate_llm_response(prompt: str, llm_backend: str) -> tuple[str, LLMCallMetrics]:
    """Route LLM calls through the backend selected in the library config."""
    if llm_backend == "openrouter":
        return generate_llm_response_openrouter(prompt)
    if llm_backend == "ollama":
        return generate_llm_response_ollama(prompt)
    raise ValueError(f"Unsupported LLM backend: {llm_backend!r}")


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
            raise LLMTimeoutError(
                f"LLM generation exceeded {LLM_TIMEOUT_SECONDS} seconds",
                partial_output=llm_output,
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


def generate_llm_response_ollama(prompt: str) -> tuple[str, LLMCallMetrics]:
    stream = chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        stream=True,
        options={
            "temperature": LLM_TEMPERATURE,
            "seed": LLM_SEED,
            "num_ctx": OLLAMA_CONTEXT_SIZE,
        }
    )

    llm_output = ""
    metrics = LLMCallMetrics()
    started_at = time.monotonic()
    for chunk in stream:
        if time.monotonic() - started_at > LLM_TIMEOUT_SECONDS:
            raise LLMTimeoutError(
                f"LLM generation exceeded {LLM_TIMEOUT_SECONDS} seconds",
                partial_output=llm_output,
            )
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