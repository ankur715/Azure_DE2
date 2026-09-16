"""
Question classification — picks which schema domains are relevant to a
question, so sql_generation.py only puts those tables' metadata in the
prompt instead of the whole warehouse schema.
"""
import json

from llm import complete
from schema_metadata import DOMAINS

_DOMAIN_LIST = "\n".join(f"- {name}: {info['description']}" for name, info in DOMAINS.items())

_SYSTEM = f"""You classify analytics questions about NYPA (New York Power Authority) data
into one or more of these domains:

{_DOMAIN_LIST}

Respond with ONLY a JSON array of domain names relevant to the question, e.g. ["rates"] or
["generation", "calendar"]. If the question isn't about any of these domains at all
(e.g. small talk, unrelated topic), respond with []."""


def classify_domains(question: str) -> list[str]:
    raw = complete(system=_SYSTEM, user=question, max_tokens=64)
    try:
        domains = json.loads(raw)
    except json.JSONDecodeError:
        # Fall back to including everything rather than failing the request
        # outright — an over-inclusive prompt is a much smaller problem than
        # a broken chatbot.
        return list(DOMAINS.keys())
    return [d for d in domains if d in DOMAINS]
