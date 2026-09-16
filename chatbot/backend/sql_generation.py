"""
NL question -> SQL. This is the ONLY module where the LLM writes SQL, and
its output is never trusted — sql_validator.py is what actually decides
whether it runs. The LLM is told the row-level policy exists (so it doesn't
generate something contradictory) but never told to enforce it itself.
"""
import re

from llm import complete
from schema_metadata import render_schema_prompt

_SYSTEM_TEMPLATE = """You write a single Databricks SQL SELECT statement to answer an
analytics question about NYPA (New York Power Authority) energy data.

Schema (only the tables relevant to this question):

{schema}

Rules:
- Output ONLY the SQL statement. No markdown fences, no explanation, no comments.
- Exactly one SELECT statement. Never INSERT/UPDATE/DELETE/DDL.
- Always use fully-qualified table names (nypade2_dbx.gold.<table>).
- Only use columns listed above — never invent a column.
- Do not add your own row-level access filters (e.g. based on customer type or
  source system) unless the question explicitly asks for a filtered subset —
  access control is enforced separately, outside of what you generate.
- If the question can't be answered with the given schema, output exactly:
  NO_QUERY: <one sentence reason>
"""


def generate_sql(question: str, domains: list[str], conversation_context: str = "") -> str:
    schema_text = render_schema_prompt(domains) or "(no matching schema for this question)"
    system = _SYSTEM_TEMPLATE.format(schema=schema_text)
    user = question
    if conversation_context:
        user = f"Recent conversation:\n{conversation_context}\n\nNew question: {question}"

    raw = complete(system=system, user=user, max_tokens=512)
    # Strip markdown fences defensively in case the model adds them anyway.
    raw = re.sub(r"^```(sql)?", "", raw.strip(), flags=re.IGNORECASE).strip()
    raw = re.sub(r"```$", "", raw).strip()
    return raw
