# Azure_DE2 — NYPA Energy Data Platform

Medallion-architecture pipeline on Azure, built around three real **New York Power
Authority (NYPA)** open datasets pulled through three different ingestion patterns —
file, database, and REST API — landing in a star-schema gold layer.

## Sources

| Source type | Dataset | Ingestion pattern |
|---|---|---|
| CSV (file drop) | [NYPA Net Generation (MWh) by Facility](https://data.ny.gov/d/isux-jnrn) | Bulk file dropped into `raw/csv` container, picked up by ADF on schedule |
| Database | [NYPA Electric Supply Rates — Governmental Entities](https://data.ny.gov/d/tj6m-a24c) | Seeded into Azure SQL DB, incremental ADF copy watermarked on `data_as_of` |
| REST API | [NYPA Electric Supply Rates — Business Customers](https://data.ny.gov/d/2x8p-pewm) | Pulled live from the Socrata SODA API (`data.ny.gov/resource/2x8p-pewm.json`) |

The two rate datasets share a shape (rate by customer segment, effective date) despite
coming from different technical sources — a deliberate design so bronze/silver treat
them as parallel feeds into one conformed `fact_supply_rate`, while generation data
feeds a separate `fact_generation`.

## Architecture

```
CSV file  ──(ADF Copy)───────────────▶┐
Azure SQL ──(ADF incremental copy)────┤──▶ Bronze (ADLS Gen2, parquet)
Socrata API ──(ADF REST / notebook)───┘         │
                                                 ▼
                                    Databricks Silver (cleansed, conformed)
                                                 │
                                                 ▼
                                 Databricks Gold (Delta star schema, Unity Catalog)
                    dim_facility · dim_date · dim_customer_type
                    fact_generation · fact_supply_rate
```

## Repo layout

| Path | Contents |
|---|---|
| `infra/` | Bicep templates for the resource group, ADLS Gen2, ADF, Azure SQL DB, Databricks workspace |
| `adf/` | Exported ADF pipeline / dataset / linked service JSON |
| `workspace/` | Databricks notebooks — bronze ingestion, silver cleansing, gold dimensional model |
| `scripts/` | Local helper scripts (pull CSV, seed SQL DB, sanity-check the API) — used for local dev before wiring ADF |
| `data/` | Small sample extracts for local testing (full pulls are gitignored) |
| `pics/` | Architecture diagrams / screenshots |

## Stack

Azure Data Factory · ADLS Gen2 · Azure SQL Database · Azure Databricks · Unity Catalog
· Delta Lake · PySpark · Bicep

## Status

Scaffolding in progress — infra not yet provisioned. See `scripts/` for local
source-connectivity checks against the live NYPA datasets.
