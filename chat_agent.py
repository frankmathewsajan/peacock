import os
from google import genai
from PIL import Image

client = genai.Client()


def analyze_screen(
    prompt: str, images: list[Image.Image], model_tier: str = "fast"
) -> tuple[str, int]:
    """
    Passes multiple image contexts along with the user text query
    to the selected Gemini multi-modal processing pipeline.
    """
    if not images and not prompt:
        return "System Error: No content provided.", 0

    # Map the frontend toggle to the correct frontier model
    model_map = {"fast": "gemini-3.5-flash", "deep": "gemini-3.1-pro-preview"}
    target_model = model_map.get(model_tier, "gemini-3.5-flash")

    try:
        payload = images + [prompt]

        response = client.models.generate_content(model=target_model, contents=payload)

        tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            tokens = response.usage_metadata.total_token_count

        return response.text, tokens
    except Exception as e:
        return f"API Execution Fault ({target_model}): {str(e)}", 0
