"""
Seeds the Azure SQL DB (nypa_rates) with the NYPA governmental rates dataset,
simulating an existing OLTP source system that ADF will later pull from
incrementally (watermarked on data_as_of).

Requires env vars: SQL_SERVER_FQDN, SQL_ADMIN_LOGIN, SQL_ADMIN_PASSWORD, SQL_DB_NAME
(load from .env before running).

Usage:
    set -a && source .env && set +a
    export SQL_SERVER_FQDN=<from `az sql server show`>
    export SQL_DB_NAME=nypa_rates
    python3 scripts/seed_sql_governmental_rates.py
"""
import csv
import os
import pathlib

import pymssql

RAW_CSV = pathlib.Path(__file__).resolve().parent.parent / "data" / "raw" / "nypa_governmental_rates.csv"

CREATE_TABLE_SQL = """
IF OBJECT_ID('dbo.governmental_rates', 'U') IS NULL
CREATE TABLE dbo.governmental_rates (
    id INT IDENTITY(1,1) PRIMARY KEY,
    governmental_entity NVARCHAR(200),
    service_classification NVARCHAR(200),
    ratetype NVARCHAR(100),
    period NVARCHAR(50),
    production_demand_price_kw FLOAT,
    production_energy_price_mills_kwh FLOAT,
    production_on_peak_energy_price_mills_kwh FLOAT,
    production_offpeak_energy_price_mills_kwh FLOAT,
    data_as_of DATE
)
"""

INSERT_SQL = """
INSERT INTO dbo.governmental_rates (
    governmental_entity, service_classification, ratetype, period,
    production_demand_price_kw, production_energy_price_mills_kwh,
    production_on_peak_energy_price_mills_kwh, production_offpeak_energy_price_mills_kwh,
    data_as_of
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def to_float(v):
    return float(v) if v not in (None, "") else None


def main() -> None:
    conn = pymssql.connect(
        server=os.environ["SQL_SERVER_FQDN"],
        user=os.environ["SQL_ADMIN_LOGIN"],
        password=os.environ["SQL_ADMIN_PASSWORD"],
        database=os.environ["SQL_DB_NAME"],
    )
    cur = conn.cursor()
    cur.execute(CREATE_TABLE_SQL)
    cur.execute("SELECT COUNT(*) FROM dbo.governmental_rates")
    existing = cur.fetchone()[0]
    if existing:
        print(f"dbo.governmental_rates already has {existing} rows, skipping load.")
        conn.close()
        return

    with open(RAW_CSV, newline="") as f:
        reader = csv.DictReader(f)
        rows = [
            (
                r["governmental_entity"],
                r["service_classification"],
                r["ratetype"],
                r["period"],
                to_float(r["production_demand_price_kw"]),
                to_float(r["production_energy_price_mills_kwh"]),
                to_float(r["production_on_peak_energy_price_mills_kwh"]),
                to_float(r["production_offpeak_energy_price_mills_kwh"]),
                r["data_as_of"][:10] if r["data_as_of"] else None,
            )
            for r in reader
        ]

    cur.executemany(INSERT_SQL, rows)
    conn.commit()
    print(f"Loaded {len(rows)} rows into dbo.governmental_rates")
    conn.close()


if __name__ == "__main__":
    main()
