"""Thin wrapper around the Gemini API so the rest of the app doesn't import
the SDK directly. Gemini (not Anthropic) specifically because it has a real
no-payment-method-required free tier — see https://aistudio.google.com/apikey."""
from google import genai
from google.genai import types

from config import settings

_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def complete(system: str, user: str, max_tokens: int = 1024) -> str:
    resp = _get_client().models.generate_content(
        model=settings.LLM_MODEL,
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
        ),
    )
    return (resp.text or "").strip()
