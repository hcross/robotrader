import os
from dotenv import load_dotenv
import litellm

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "openrouter/google/gemini-2.5-flash")
litellm.api_key = OPENROUTER_API_KEY


def get_llm_response(messages, model=LLM_MODEL, **kwargs):
    """
    Wrapper for LiteLLM completion via OpenRouter.
    """
    try:
        return litellm.completion(
            model=model,
            messages=messages,
            **kwargs,
        )
    except Exception as exc:
        print(f"LLM Error: {exc}")
        return None
