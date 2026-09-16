"""Turns validated query results back into a plain-English answer."""
from executor import QueryResult
from llm import complete
from schema_metadata import render_schema_prompt

_SYSTEM_TEMPLATE = """You answer a business question in plain English using ONLY the query result
rows given to you. Be concise (2-4 sentences). Cite specific numbers from the data.
Do not speculate beyond what the rows show. If the result is empty, say so plainly
and suggest the user rephrase or broaden the question.

Some columns contain coded values (e.g. source_system) that mean something specific —
use the schema notes below to translate them correctly rather than guessing. For
example, do NOT swap which code means "governmental" vs "business".

{schema}"""


def summarize(question: str, result: QueryResult, domains: list[str], max_rows_shown: int = 50) -> str:
    if result.row_count == 0:
        preview = "(no rows returned)"
    else:
        preview_rows = result.rows[:max_rows_shown]
        preview = f"columns: {result.columns}\nrows: {preview_rows}"
        if result.row_count > max_rows_shown:
            preview += f"\n(...and {result.row_count - max_rows_shown} more rows, truncated for this summary)"

    schema_text = render_schema_prompt(domains) or "(no schema notes for this question)"
    system = _SYSTEM_TEMPLATE.format(schema=schema_text)
    user = f"Question: {question}\n\nQuery result:\n{preview}"
    return complete(system=system, user=user, max_tokens=500)
