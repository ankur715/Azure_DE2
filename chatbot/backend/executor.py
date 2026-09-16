"""
Executes validated SQL against the Databricks SQL Warehouse.

This is the only module that holds a live connection to the warehouse. It
never sees LLM output directly — only sql_validator.ValidatedQuery, which
has already been parsed, authorized, and had row-level filters and a LIMIT
enforced.
"""
import time
from dataclasses import dataclass

from databricks import sql as dbsql

from config import settings


class QueryExecutionError(Exception):
    pass


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[tuple]
    duration_ms: int
    row_count: int


def _connect():
    kwargs = dict(
        server_hostname=settings.DATABRICKS_SERVER_HOSTNAME,
        http_path=settings.DATABRICKS_HTTP_PATH,
        _socket_timeout=settings.QUERY_TIMEOUT_SECONDS,
    )
    if settings.DATABRICKS_TOKEN:
        kwargs["access_token"] = settings.DATABRICKS_TOKEN
    else:
        kwargs["auth_type"] = "databricks-oauth"
        kwargs["oauth_client_id"] = settings.DATABRICKS_CLIENT_ID
        kwargs["oauth_client_secret"] = settings.DATABRICKS_CLIENT_SECRET
    return dbsql.connect(**kwargs)


def execute(sql: str) -> QueryResult:
    start = time.monotonic()
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                columns = [desc[0] for desc in cur.description] if cur.description else []
                rows = cur.fetchall()
    except Exception as e:
        raise QueryExecutionError(str(e))
    duration_ms = int((time.monotonic() - start) * 1000)
    return QueryResult(columns=columns, rows=rows, duration_ms=duration_ms, row_count=len(rows))
