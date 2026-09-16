"""
Server-side SQL validation and enforcement.

The LLM's job (sql_generation.py) is to interpret the business question and
propose a query. Everything in this file is what actually decides whether
that query is allowed to run — the LLM's output is treated as untrusted
input, exactly like a value typed into a search box.

Checks, in order:
  1. Parses as exactly one statement (sqlglot).
  2. Is a SELECT — no DDL/DML/multi-statement/semicolon-chaining.
  3. Every referenced table is in the caller's role's allow-list.
  4. Every referenced table is qualified to the expected catalog.schema
     (blocks querying anything outside nypade2_dbx.gold).
  5. Row-level filters for the caller's role are injected (AND'd into the
     WHERE clause) for any restricted table referenced — the LLM never
     writes these, so it can't be prompted into omitting them.
  6. A LIMIT is added if missing, capped at settings.MAX_RESULT_ROWS, as a
     blunt cost/runaway-query guard.
"""
from dataclasses import dataclass

import sqlglot
from sqlglot import exp

from auth import Principal
from config import settings
from schema_metadata import CATALOG, SCHEMA, TABLES

DIALECT = "databricks"


class SqlValidationError(Exception):
    pass


@dataclass
class ValidatedQuery:
    sql: str
    tables_used: list[str]


def _extract_tables(tree: exp.Expression) -> list[exp.Table]:
    return list(tree.find_all(exp.Table))


def _table_short_name(table: exp.Table) -> str:
    return table.name


def _table_is_in_scope(table: exp.Table) -> bool:
    """True if the table has no catalog/schema qualifier, or is qualified
    to exactly nypade2_dbx.gold."""
    db = table.db or None
    catalog = table.catalog or None
    if catalog and catalog.lower() != CATALOG.lower():
        return False
    if db and db.lower() != SCHEMA.lower():
        return False
    return True


def validate_and_authorize(raw_sql: str, principal: Principal) -> ValidatedQuery:
    raw_sql = raw_sql.strip().rstrip(";")

    if ";" in raw_sql:
        raise SqlValidationError("Multiple statements are not allowed.")

    try:
        statements = sqlglot.parse(raw_sql, read=DIALECT)
    except Exception as e:
        raise SqlValidationError(f"SQL failed to parse: {e}")

    if len(statements) != 1 or statements[0] is None:
        raise SqlValidationError("Exactly one SQL statement is required.")

    tree = statements[0]

    if not isinstance(tree, exp.Select):
        raise SqlValidationError(
            f"Only SELECT statements are allowed, got: {type(tree).__name__}"
        )

    # Reject anything with a CTE/subquery that itself isn't a plain SELECT
    # (sqlglot's parse already fails on DDL/DML, but be explicit about the
    # single-statement, no-DML intent for defense in depth).
    forbidden_node_types = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter, exp.Merge)
    for node in tree.walk():
        if isinstance(node, forbidden_node_types):
            raise SqlValidationError(f"{type(node).__name__} is not allowed.")

    tables = _extract_tables(tree)
    if not tables:
        raise SqlValidationError("Query references no tables.")

    tables_used = []
    for t in tables:
        if not _table_is_in_scope(t):
            raise SqlValidationError(
                f"Table '{t.sql()}' is outside the allowed {CATALOG}.{SCHEMA} schema."
            )
        name = _table_short_name(t)
        if name not in TABLES:
            raise SqlValidationError(f"Unknown table: {name}")
        if name not in principal.allowed_tables:
            raise SqlValidationError(f"Role '{principal.role}' is not authorized to query '{name}'.")
        tables_used.append(name)

    # Column allow-list: every column identifier that resolves to a known
    # table must be one of that table's documented columns, OR an alias the
    # query itself defines in its SELECT list (e.g. `SUM(x) AS total`
    # referenced later in ORDER BY/HAVING — a normal SQL pattern, not a
    # hallucinated column). Best-effort: catches hallucinated *table*
    # columns before they hit the warehouse as a confusing runtime error.
    known_columns = set()
    for t in tables_used:
        known_columns.update(TABLES[t]["columns"].keys())
    output_aliases = {
        alias_node.alias for alias_node in tree.selects if isinstance(alias_node, exp.Alias)
    }
    known_columns |= output_aliases
    for col in tree.find_all(exp.Column):
        col_name = col.name
        if col_name == "*":
            continue
        if col_name not in known_columns:
            raise SqlValidationError(
                f"Column '{col_name}' is not a recognized column of {', '.join(tables_used)}."
            )

    # Row-level authorization: inject any required filter for tables this
    # role can only see part of. Done on the parsed tree, not string
    # concatenation, so it can't be bypassed by clever LLM-authored SQL.
    for t in tables_used:
        row_filter = principal.row_filter_for(t)
        if row_filter:
            filter_expr = sqlglot.parse_one(row_filter, read=DIALECT)
            existing_where = tree.args.get("where")
            if existing_where:
                tree.set("where", exp.Where(this=exp.And(this=existing_where.this, expression=filter_expr)))
            else:
                tree.set("where", exp.Where(this=filter_expr))

    # Cost guard: cap (or add) LIMIT.
    existing_limit = tree.args.get("limit")
    if existing_limit is None:
        tree.set("limit", exp.Limit(expression=exp.Literal.number(settings.MAX_RESULT_ROWS)))
    else:
        try:
            requested = int(existing_limit.expression.this)
            if requested > settings.MAX_RESULT_ROWS:
                tree.set("limit", exp.Limit(expression=exp.Literal.number(settings.MAX_RESULT_ROWS)))
        except (AttributeError, ValueError):
            tree.set("limit", exp.Limit(expression=exp.Literal.number(settings.MAX_RESULT_ROWS)))

    final_sql = tree.sql(dialect=DIALECT)
    return ValidatedQuery(sql=final_sql, tables_used=tables_used)
