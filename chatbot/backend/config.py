"""Environment-driven configuration. No secrets have defaults — the app
refuses to start without them, rather than silently falling back."""
import os


def _require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return val


class Settings:
    # LLM (Anthropic Claude — swap provider by editing llm.py if you prefer another)
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    LLM_MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-4-5")

    # Databricks SQL Warehouse (Unity Catalog gold tables)
    DATABRICKS_SERVER_HOSTNAME = os.environ.get("DATABRICKS_SERVER_HOSTNAME", "")
    DATABRICKS_HTTP_PATH = os.environ.get("DATABRICKS_HTTP_PATH", "")
    # Auth to the warehouse: either a PAT, or OAuth M2M (client id/secret).
    DATABRICKS_TOKEN = os.environ.get("DATABRICKS_TOKEN", "")
    DATABRICKS_CLIENT_ID = os.environ.get("DATABRICKS_CLIENT_ID", "")
    DATABRICKS_CLIENT_SECRET = os.environ.get("DATABRICKS_CLIENT_SECRET", "")

    # Auth (app-level login, not Databricks)
    JWT_SECRET = os.environ.get("JWT_SECRET", "")
    JWT_EXPIRY_MINUTES = int(os.environ.get("JWT_EXPIRY_MINUTES", "120"))

    # Query cost guardrails
    MAX_RESULT_ROWS = int(os.environ.get("MAX_RESULT_ROWS", "500"))
    QUERY_TIMEOUT_SECONDS = int(os.environ.get("QUERY_TIMEOUT_SECONDS", "30"))

    LOG_DB_PATH = os.environ.get("LOG_DB_PATH", "chatbot_audit_log.db")

    def validate(self) -> None:
        _require("ANTHROPIC_API_KEY")
        _require("DATABRICKS_SERVER_HOSTNAME")
        _require("DATABRICKS_HTTP_PATH")
        if not (self.DATABRICKS_TOKEN or (self.DATABRICKS_CLIENT_ID and self.DATABRICKS_CLIENT_SECRET)):
            raise RuntimeError(
                "Set either DATABRICKS_TOKEN, or both DATABRICKS_CLIENT_ID and "
                "DATABRICKS_CLIENT_SECRET, to authenticate to the SQL warehouse."
            )
        _require("JWT_SECRET")


settings = Settings()
