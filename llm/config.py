import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "deepseek/deepseek-v4-flash"

OLLAMA_MODEL = "qwen2.5-coder:7b"
OLLAMA_CONTEXT_SIZE = 6000

LLM_TIMEOUT_SECONDS = 300
LLM_TEMPERATURE = 0
LLM_SEED = 42