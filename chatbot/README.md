# NYPA Analytics Chatbot

A natural-language-to-SQL chatbot over the [Azure_DE2](../README.md) NYPA gold data model
(`nypade2_dbx.gold` in Databricks Unity Catalog): `dim_facility`, `fact_generation`,
`dim_customer_type`, `fact_supply_rate`, `dim_date`.

This is the companion analytics layer to the data pipeline — same idea as
[Web_App](https://github.com/ankur715/Web_App)'s Retail Sales Analytics Chatbot, but built as a
governed enterprise NL→SQL pipeline rather than a single LLM call: the LLM interprets the
question and drafts SQL; everything about whether that SQL is safe, authorized, and affordable
to run is decided by code, not by asking the model nicely.

## Architecture

```
User (browser) ──login──▶ FastAPI /login ──▶ JWT (username + role)
      │
      └─question──▶ FastAPI /chat (Bearer JWT)
                        │
                        ▼
                 1. Authenticate — verify JWT, resolve Principal(username, role)
                        │
                        ▼
                 2. Classify — LLM picks relevant schema domain(s)
                        │        (generation / rates / calendar)
                        ▼
                 3. Retrieve metadata — only the curated tables/columns/
                    business notes for those domains, not the full schema
                        │
                        ▼
                 4. Generate SQL — LLM drafts ONE SELECT statement
                        │        (untrusted output past this point)
                        ▼
                 5. Validate + authorize — sqlglot parse, SELECT-only,
                    table/column allow-list, row-level filter injected per
                    role, LIMIT capped           ◀── LLM has no say here
                        │
                        ▼
                 6. Execute — read-only warehouse connection (Databricks SQL)
                        │
                        ▼
                 7. Respond — LLM summarizes the actual returned rows
                        │
                        ▼
                 8. Log + remember — question/SQL/metrics/outcome to SQLite;
                    conversation turn kept in memory for follow-ups
```

**The LLM's job stops at steps 2, 4, and 7** — classifying the question, drafting SQL, and
describing results in English. It never decides what's allowed to run; `sql_validator.py` and
`auth.py` do that, deterministically, every time, regardless of what the model outputs.

| File | Responsibility |
|---|---|
| `backend/app.py` | FastAPI routes, orchestrates the pipeline above |
| `backend/auth.py` | Login, JWT issuance/verification, role → allowed tables + row-level filters |
| `backend/schema_metadata.py` | Curated table/column descriptions + business notes, grouped by domain |
| `backend/classifier.py` | LLM call: question → relevant domain(s) |
| `backend/sql_generation.py` | LLM call: question + curated schema → one SQL statement |
| `backend/sql_validator.py` | Parses and authorizes the SQL — the actual security boundary |
| `backend/executor.py` | Runs validated SQL against the Databricks SQL Warehouse |
| `backend/responder.py` | LLM call: query results → plain-English answer |
| `backend/conversation.py` | In-memory per-session conversation context |
| `backend/logging_store.py` | SQLite audit log: question, SQL, metrics, outcome |
| `frontend/index.html` | Single-page chat UI (login + chat, no build step) |
| `eval/` | Known-question regression harness, including an authorization test |

## Why Databricks SQL, not the ADF/Synapse side

The gold Delta tables already live in ADLS, registered as real Unity Catalog tables
(`nypade2_dbx.gold.*`) for exactly this reason: Unity Catalog gives per-principal `SELECT`
grants for free, and the existing serverless SQL Warehouse (`Serverless Starter Warehouse`)
answers ad-hoc analytical SQL in seconds without needing a dedicated always-on cluster.

## Authorization model (demo)

| Role | Username | Sees |
|---|---|---|
| `admin` | `admin` | All rows |
| `governmental_analyst` | `gov_analyst` | `fact_supply_rate` rows where `source_system = 'azure_sql'` only |
| `business_analyst` | `biz_analyst` | `fact_supply_rate` rows where `source_system = 'socrata_rest_api'` only |

Password for every demo account is `<username>-demo123` (e.g. `admin-demo123`). The row filter is
injected into the parsed SQL tree server-side — the LLM is told the policy exists so it doesn't
generate something contradictory, but it never writes the filter itself, and there's no way for a
crafted question to bypass it (see `eval/eval_questions.json`'s `authz_row_filter_*` cases, which
prove the same question returns different data for different roles).

This is a demo identity/permission model, not a real IdP. Swap `auth.py`'s `USERS`/`ROW_FILTERS`
for real Azure AD groups + a proper policy table before using this for anything beyond a
portfolio project.

## Setup — local

### 1. Prerequisites already in place (from the main project)

- Databricks workspace with `nypade2_dbx.gold.*` tables and a running/resumable SQL Warehouse
- An Anthropic API key — get one at https://console.anthropic.com/settings/keys

### 2. Install

```bash
cd chatbot/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
```

Fill in `.env`:

- `ANTHROPIC_API_KEY` — your key
- `DATABRICKS_SERVER_HOSTNAME` / `DATABRICKS_HTTP_PATH` — from the SQL Warehouse's
  "Connection details" tab in the Databricks UI
- `DATABRICKS_TOKEN` — a personal access token (User Settings → Developer → Access tokens),
  **or** `DATABRICKS_CLIENT_ID`/`DATABRICKS_CLIENT_SECRET` for a service-principal OAuth
  credential if your workspace tier supports generating one (see note below)
- `JWT_SECRET` — any random string, e.g. `openssl rand -hex 32`

> **On "read-only warehouse credentials":** the right way to do this is a Unity
> Catalog service principal granted `SELECT` only (no write grants anywhere) — this repo's
> setup created one (`nypa-chatbot-readonly`) with exactly that grant. Generating its OAuth
> secret requires either the workspace's on-behalf-of-token feature or the Databricks *account*
> console (Settings → Identity and access → Service principals), which needs account-admin
> access — not available from a workspace-scoped API session. If your workspace supports it,
> use that service principal's credential; otherwise a personal PAT works for local testing,
> with read-only behavior enforced by `sql_validator.py` (SELECT-only, ever) rather than by the
> credential's own permission scope.

### 4. Run

```bash
cd chatbot/backend
uvicorn app:app --reload --port 8000
```

Open **http://localhost:8000** — the backend serves the frontend directly, no separate server.

### 5. Evaluate

```bash
cd chatbot/eval
pip install requests
python run_eval.py --base-url http://localhost:8000
```

## Setup — Azure

Containerize the backend (`Dockerfile` in this folder already does this — it packages the
backend and frontend into one image, since the backend serves the frontend directly) and run it
on **Azure Container Apps** (simplest: scales to zero, no VM management) or **Azure App Service**
(if you want a persistent instance).

```bash
# From chatbot/, build and push to Azure Container Registry
az acr build --registry <your-acr-name> --image nypa-chatbot:latest .

# Deploy to Container Apps, injecting secrets as env vars (never bake them into the image)
az containerapp create \
  --name nypa-chatbot \
  --resource-group nypa-de2-rg \
  --image <your-acr-name>.azurecr.io/nypa-chatbot:latest \
  --target-port 8000 --ingress external \
  --secrets anthropic-key=<value> jwt-secret=<value> dbx-token=<value> \
  --env-vars \
    ANTHROPIC_API_KEY=secretref:anthropic-key \
    JWT_SECRET=secretref:jwt-secret \
    DATABRICKS_TOKEN=secretref:dbx-token \
    DATABRICKS_SERVER_HOSTNAME=<hostname> \
    DATABRICKS_HTTP_PATH=<http-path>
```

For anything beyond a demo, move the secrets into the Key Vault already deployed for this
project (`nypade2-kv-...`) and reference them via Container Apps' Key Vault integration instead
of plain env vars.

## What this does *not* do

- No production-grade query cost estimation — the LIMIT-capping in `sql_validator.py` is a
  blunt guard, not a real cost model (Databricks' own warehouse-level cost/timeout limits are
  the actual backstop).
- No persistent conversation history — `conversation.py` is in-memory, lost on restart.
- No real identity provider — see the authorization section above.
