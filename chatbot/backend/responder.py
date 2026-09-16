"""Turns validated query results back into a plain-English answer."""
from llm import complete
from executor import QueryResult

_SYSTEM = """You answer a business question in plain English using ONLY the query result
rows given to you. Be concise (2-4 sentences). Cite specific numbers from the data.
Do not speculate beyond what the rows show. If the result is empty, say so plainly
and suggest the user rephrase or broaden the question."""


def summarize(question: str, result: QueryResult, max_rows_shown: int = 50) -> str:
    if result.row_count == 0:
        preview = "(no rows returned)"
    else:
        preview_rows = result.rows[:max_rows_shown]
        preview = f"columns: {result.columns}\nrows: {preview_rows}"
        if result.row_count > max_rows_shown:
            preview += f"\n(...and {result.row_count - max_rows_shown} more rows, truncated for this summary)"

    user = f"Question: {question}\n\nQuery result:\n{preview}"
    return complete(system=_SYSTEM, user=user, max_tokens=500)
