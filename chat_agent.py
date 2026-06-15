import os
from google import genai
from PIL import Image

# Initialize as None at the module level
_client = None


def get_client() -> genai.Client:
    """Lazy initialization ensures the env is loaded before the client builds."""
    global _client
    if _client is None:
        # Explicitly fetch the key to force a hard crash here if it's truly missing,
        # rather than a mysterious internal SDK error.
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "CRITICAL: GEMINI_API_KEY is not loaded into the environment."
            )
        _client = genai.Client(api_key=api_key)
    return _client


def analyze_screen(
    prompt: str, images: list[Image.Image], model_tier: str = "fast"
) -> tuple[str, int]:

    if not images and not prompt:
        return "System Error: No content provided.", 0

    model_map = {"fast": "gemini-3.5-flash", "deep": "gemini-3.1-pro-preview"}
    target_model = model_map.get(model_tier, "gemini-3.5-flash")

    try:
        # Instantiate/Retrieve the client safely inside the execution scope
        client = get_client()

        payload = images + [prompt]
        response = client.models.generate_content(model=target_model, contents=payload)

        tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            tokens = response.usage_metadata.total_token_count

        return response.text, tokens

    except Exception as e:
        return f"API Execution Fault ({target_model}): {str(e)}", 0
