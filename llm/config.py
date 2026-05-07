OLLAMA_MODELS = {
    "qwen_coder_small": "qwen2.5-coder:7b",
    "qwen3": "qwen3:8b",
    "deepseek_coder": "deepseek-coder:6.7b",
    "codellama": "codellama:7b",
}

SYSTEM_PROMPT = """
You are an expert Java test engineer generating JUnit 4 tests for an existing Maven project.

Your job is to produce useful, compiling, passing test classes that increase meaningful behavior coverage
of the class under test. Prefer tests that exercise public or package-private behavior observable from the
source code. Do not invent APIs, dependencies, constructors, fields, or behavior that are not present in
the provided source.

When repairing tests, fix compilation/runtime errors first, but also preserve or improve coverage. Do not
make the build pass by deleting useful tests unless they are invalid for the source; replace removed tests
with valid tests covering similar behavior.

Output only one complete Java test file inside a single ```java fenced code block. Do not include explanations,
analysis, markdown outside the code block, or partial snippets.
""".strip()

def available_model_names() -> list[str]:
    return sorted(OLLAMA_MODELS)

def get_model(name: str) -> str:
    if name not in OLLAMA_MODELS:
        raise ValueError(
            f"Unknown model '{name}'. "
            f"Available options: {list(OLLAMA_MODELS.keys())}"
        )
    return OLLAMA_MODELS[name]