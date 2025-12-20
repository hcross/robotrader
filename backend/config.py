import os
from dotenv import load_dotenv
import litellm

# Load environment variables
load_dotenv()

# Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    # Warning: No API key found. Agents will fail to communicate with LLM.
    pass

# LiteLLM Setup
# We use OpenRouter as the provider and Grok 4.1 Fast as the model.
# Model name in OpenRouter might vary, assuming 'x-ai/grok-2-1212' or similar. 
# Since the user specified "Grok 4.1 Fast", we will map it.
# Note: As of my knowledge cutoff, "Grok 4.1 Fast" might be a future/hypothetical model name.
# I will use a placeholder string that the user can update.

LLM_MODEL = "openrouter/x-ai/grok-beta" # Placeholder for Grok 4.1 Fast
litellm.api_key = OPENROUTER_API_KEY

def get_llm_response(messages, model=LLM_MODEL, **kwargs):
    """
    Wrapper for LiteLLM completion.
    """
    try:
        response = litellm.completion(
            model=model,
            messages=messages,
            **kwargs
        )
        return response
    except Exception as e:
        print(f"LLM Error: {e}")
        return None
