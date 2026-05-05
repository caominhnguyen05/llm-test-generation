OLLAMA_MODELS = {
    "qwen_coder_small": "qwen2.5-coder:7b",
    "qwen_coder_large": "qwen2.5-coder:14b",
    "qwen3": "qwen3:8b",
    "deepseek_coder": "deepseek-coder:6.7b",
    "codellama": "codellama:7b",

    "llama3_small": "llama3:8b",
    "mistral": "mistral:7b",
}

def get_model(name: str) -> str:
    if name not in OLLAMA_MODELS:
        raise ValueError(
            f"Unknown model '{name}'. "
            f"Available options: {list(OLLAMA_MODELS.keys())}"
        )
    return OLLAMA_MODELS[name]


def list_models():
    """
    Print all available models in a readable format.
    """
    for k, v in OLLAMA_MODELS.items():
        print(f"{k:20} → {v}")