"""Thin wrapper around the Gemini API so the rest of the app doesn't import
the SDK directly. Gemini (not Anthropic) specifically because it has a real
no-payment-method-required free tier — see https://aistudio.google.com/apikey.

The free tier is rate-limited per-minute per-model (as low as 5 req/min on
some models), and each /chat call makes 2-3 Gemini calls (classify, generate
SQL, summarize) — so retry-with-backoff on 429 is not an edge case here,
it's the normal path once you ask more than ~1-2 questions in a minute.
"""
import re
import time

from google import genai
from google.genai import errors, types

from config import settings

_client = None
_MAX_RETRIES = 3


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def _retry_delay_seconds(e: errors.ClientError, default: float = 15.0) -> float:
    match = re.search(r"retryDelay['\"]?:\s*['\"]?(\d+(?:\.\d+)?)s", str(e))
    return float(match.group(1)) if match else default


def complete(system: str, user: str, max_tokens: int = 1024) -> str:
    last_error = None
    for attempt in range(_MAX_RETRIES):
        try:
            resp = _get_client().models.generate_content(
                model=settings.LLM_MODEL,
                contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    max_output_tokens=max_tokens,
                    # This is a deterministic classification/SQL/summary task, not
                    # one that benefits from extended reasoning — and thinking
                    # tokens otherwise silently eat into max_output_tokens,
                    # truncating the actual answer (seen in testing: a 512-token
                    # budget consumed almost entirely by ~400+ thinking tokens).
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            break
        except errors.ClientError as e:
            last_error = e
            if e.code == 429 and attempt < _MAX_RETRIES - 1:
                time.sleep(_retry_delay_seconds(e))
                continue
            raise
    else:
        raise last_error

    text = (resp.text or "").strip()
    finish_reason = resp.candidates[0].finish_reason if resp.candidates else None
    if str(finish_reason).endswith("MAX_TOKENS") and not text:
        raise RuntimeError(
            f"Gemini hit max_output_tokens={max_tokens} with no usable output. "
            "Increase max_tokens for this call."
        )
    return text
