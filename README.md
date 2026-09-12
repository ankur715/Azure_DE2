# Azure_DE2 — NYPA Energy Data Platform

Medallion-architecture pipeline on Azure, built around three real **New York Power
Authority (NYPA)** open datasets pulled through three different ingestion patterns —
file, database, and REST API — landing in a star-schema gold layer.

## Sources

| Source type | Dataset | Ingestion pattern |
|---|---|---|
| CSV (file drop) | [NYPA Net Generation (MWh) by Facility](https://data.ny.gov/d/isux-jnrn) | Dropped into the `raw-csv` container, ADF Copy → bronze parquet |
| Database | [NYPA Electric Supply Rates — Governmental Entities](https://data.ny.gov/d/tj6m-a24c) | Seeded into Azure SQL DB (`dbo.governmental_rates`), incremental ADF copy watermarked on `data_as_of` |
| REST API | [NYPA Electric Supply Rates — Business Customers](https://data.ny.gov/d/2x8p-pewm) | Pulled live from the Socrata SODA API via an ADF REST linked service |

The two rate datasets share a shape (rate by customer segment, effective date) despite
coming from different technical sources — a deliberate design so silver/gold treat
them as parallel feeds into one conformed `fact_supply_rate`, while generation data
feeds a separate `fact_generation`.

## Architecture

```
CSV file  ──(ADF Copy)────────────────┐
Azure SQL ──(ADF incremental copy)────┤──▶ Bronze (ADLS Gen2, date-partitioned parquet/json)
Socrata REST API ──(ADF Copy)─────────┘         │
                                                 ▼
                                    Databricks Silver (cleansed, conformed)
                                                 │
                                                 ▼
                                    Databricks Gold (Delta star schema)
                    dim_facility · dim_date · dim_customer_type
                    fact_generation · fact_supply_rate
```

Secrets (SQL admin password, storage account key) live in Azure Key Vault —
ADF's SQL linked service resolves the password via an `AzureKeyVaultSecret`
reference, and the Databricks cluster reads the storage key through a
Key Vault-backed secret scope (`nypa-kv`). Nothing sensitive is in this repo.

## Deployed resources (resource group `nypa-de2-rg`)

| Resource | Name | Notes |
|---|---|---|
| Storage (ADLS Gen2) | `nypade2dls...` | Containers: `raw-csv`, `bronze`, `silver`, `gold` |
| Data Factory | `nypade2-adf` | 3 linked services, 7 datasets, 3 bronze pipelines |
| Azure SQL DB | `nypade2-sql3-...` | In `centralus` — `eastus`/`eastus2`/`westus2`/`southcentralus` all rejected new SQL server creation on this subscription at deploy time |
| Databricks workspace | `nypade2-dbx` | Notebooks under `/Shared/nypa_pipeline`; job `nypa_silver_gold_pipeline` runs silver → gold on a single-node job cluster |
| Key Vault | `nypade2-kv-...` | `sql-admin-password`, `storage-account-key` secrets |

## ADF pipelines

| Pipeline | Pattern |
|---|---|
| `pl_bronze_generation_csv` | Simple copy, raw-csv → bronze/generation |
| `pl_bronze_governmental_rates` | Lookup watermark → incremental copy (`data_as_of > watermark`) → update watermark (Script activity) |
| `pl_bronze_business_rates_api` | REST source (Socrata SODA API) → bronze/business_rates |

Bronze paths are date-partitioned (`.../ingest_date=yyyy-MM-dd/...`) so re-runs don't
clobber prior loads.

## Databricks notebooks (`workspace/`, mirrored to `/Shared/nypa_pipeline`)

| Notebook | Output |
|---|---|
| `silver_generation.py` | Cleansed generation parquet |
| `silver_rates.py` | Governmental + business rates unioned into one conformed shape |
| `gold_dim_facility.py` | `dim_facility` — surrogate key per NYPA facility |
| `gold_dim_date.py` | `dim_date` — daily calendar, 2012–present |
| `gold_dim_customer_type.py` | `dim_customer_type` — governmental vs. business segments |
| `gold_fact_generation.py` | `fact_generation` — MWh by facility/year |
| `gold_fact_supply_rate.py` | `fact_supply_rate` — rates from both source systems, one fact table |

These run as a single Databricks Job (`nypa_silver_gold_pipeline`) with task
dependencies matching the medallion order.

## Repo layout

| Path | Contents |
|---|---|
| `infra/` | Bicep templates for the resource group, ADLS Gen2, ADF, Azure SQL DB, Databricks, Key Vault |
| `adf/` | Exported ADF linked service / dataset / pipeline JSON |
| `workspace/` | Databricks notebooks (source format) |
| `scripts/` | Local helper scripts — pull NYPA sources, seed the SQL DB, init the watermark table |
| `data/` | Small sample extracts for local testing (full pulls are gitignored) |
| `pics/` | Architecture diagrams / screenshots |

## Stack

Azure Data Factory · ADLS Gen2 · Azure SQL Database · Azure Key Vault · Azure Databricks
· Delta Lake · PySpark · Bicep

## Status

Infra deployed, all three bronze pipelines run successfully, silver/gold notebooks
built and wired into a Databricks Job. See `scripts/` for the local source-connectivity
and seeding scripts.
