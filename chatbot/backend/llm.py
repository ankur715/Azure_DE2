"""Thin wrapper around the Anthropic API so the rest of the app doesn't
import the SDK directly."""
import anthropic

from config import settings

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def complete(system: str, user: str, max_tokens: int = 1024) -> str:
    resp = _get_client().messages.create(
        model=settings.LLM_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in resp.content if block.type == "text").strip()
