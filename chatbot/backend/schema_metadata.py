"""
Curated schema + business metadata for the gold star schema.

This is the "relevant schema retrieval" layer: instead of dumping the full
warehouse schema at the LLM for every question, `classify_domains()` picks
the 1-2 domains a question is actually about, and only those tables'
metadata gets put in the SQL-generation prompt.
"""

CATALOG = "nypade2_dbx"
SCHEMA = "gold"

# Each domain maps to the tables relevant to it, plus a short description of
# what kinds of questions belong to that domain (used by the classifier).
DOMAINS = {
    "generation": {
        "description": (
            "Questions about electricity generation volume (MWh) by NYPA "
            "facility or year — e.g. 'how much did Niagara generate', "
            "'which facility produced the most power', 'generation trend "
            "over time'."
        ),
        "tables": ["dim_facility", "fact_generation"],
    },
    "rates": {
        "description": (
            "Questions about electricity supply rates/prices — demand price, "
            "energy price — for governmental or business customers, or "
            "comparisons between customer types/segments — e.g. 'average "
            "energy price for governmental customers', 'which customer "
            "segment pays the most', 'business vs governmental demand price'."
        ),
        "tables": ["dim_customer_type", "fact_supply_rate"],
    },
    "calendar": {
        "description": (
            "Questions that need date/time breakdowns (by year, quarter, "
            "month, day of week) layered on top of generation or rates data."
        ),
        "tables": ["dim_date"],
    },
}

# Full column-level metadata per table. Kept separate from DOMAINS so a
# question can pull in extra tables (e.g. dim_date) without duplicating
# descriptions.
TABLES = {
    "dim_facility": {
        "description": "One row per NYPA generating facility.",
        "columns": {
            "facility_key": "Surrogate key, join target for fact_generation.facility_key.",
            "facility_name": "NYPA facility name, e.g. NIAGARA, BLENHEIM-GILBOA, 500 MW.",
        },
    },
    "fact_generation": {
        "description": "Net electricity generation (MWh) by facility and year. One row per facility/year.",
        "columns": {
            "facility_key": "Join to dim_facility.facility_key.",
            "year": "Calendar year of generation, integer (e.g. 2023).",
            "net_generation_mwh": "Net megawatt-hours generated, net of station service.",
        },
        "notes": "Source: NYPA Net Generation open dataset. Annual grain, not daily.",
    },
    "dim_customer_type": {
        "description": (
            "One row per distinct rate program / customer segment, tagged "
            "with whether it's a governmental or business rate."
        ),
        "columns": {
            "customer_type_key": "Surrogate key, join target for fact_supply_rate.customer_type_key.",
            "customer_type": (
                "The rate program / customer category name (e.g. 'Preservation Power', "
                "'Aluminum Company of America', 'Direct Sale Western New York'). "
                "NOT a simple business/governmental flag by itself."
            ),
            "customer_segment": "Same value as customer_type in this dataset (kept for schema symmetry).",
        },
        "notes": (
            "Use fact_supply_rate.source_system ('azure_sql' = governmental, "
            "'socrata_rest_api' = business) to distinguish governmental vs "
            "business rows, since customer_type itself is a program name, "
            "not a governmental/business flag."
        ),
    },
    "fact_supply_rate": {
        "description": (
            "Electricity supply rates by customer segment and date, unioned "
            "from two source systems: an Azure SQL DB (governmental rates) "
            "and a Socrata REST API (business rates)."
        ),
        "columns": {
            "date_key": "Join to dim_date.date_key (YYYYMMDD integer).",
            "customer_type_key": "Join to dim_customer_type.customer_type_key.",
            "demand_price_kw": "Demand charge in $/kW.",
            "energy_price_mills_kwh": "Energy charge in mills/kWh (1 mill = $0.001).",
            "source_system": (
                "'azure_sql' = governmental rate (from the Azure SQL DB source), "
                "'socrata_rest_api' = business rate (from the public API source). "
                "This is the column to filter/group on for governmental-vs-business questions."
            ),
        },
    },
    "dim_date": {
        "description": "Standard calendar dimension, one row per day from 2012-01-01 to present.",
        "columns": {
            "date_key": "YYYYMMDD integer, join target for fact tables.",
            "full_date": "Calendar date.",
            "year": "Integer year.",
            "month": "Integer month (1-12).",
            "day": "Integer day of month.",
            "day_name": "Day of week name, e.g. 'Monday'.",
            "quarter": "Integer quarter (1-4).",
        },
    },
}


def qualified(table: str) -> str:
    return f"{CATALOG}.{SCHEMA}.{table}"


def metadata_for_domains(domains: list[str]) -> dict:
    """Return {table_name: {description, columns, notes}} for the given domains."""
    tables = set()
    for d in domains:
        tables.update(DOMAINS.get(d, {}).get("tables", []))
    return {t: TABLES[t] for t in tables if t in TABLES}


def render_schema_prompt(domains: list[str]) -> str:
    """Render curated schema + business notes as text for the SQL-generation prompt."""
    meta = metadata_for_domains(domains)
    lines = []
    for table, info in meta.items():
        lines.append(f"TABLE {qualified(table)} — {info['description']}")
        for col, desc in info["columns"].items():
            lines.append(f"  - {col}: {desc}")
        if info.get("notes"):
            lines.append(f"  NOTE: {info['notes']}")
        lines.append("")
    return "\n".join(lines)
