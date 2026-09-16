"""
App-level authentication and data-access authorization.

This is deliberately separate from Databricks/Unity Catalog auth: the
Databricks warehouse credential is a single shared, read-only identity
(see executor.py); *this* module is what maps a logged-in human to what
subset of that data they're allowed to see, before any question is even
sent to the LLM.

Roles:
  - admin               : all rows, all tables
  - governmental_analyst: fact_supply_rate restricted to source_system='azure_sql'
  - business_analyst    : fact_supply_rate restricted to source_system='socrata_rest_api'

Demo users only — replace USERS with a real identity provider (Azure AD,
Okta, etc.) before using this for anything real.
"""
import time
from dataclasses import dataclass

import jwt
from passlib.hash import bcrypt

from config import settings

# username -> (bcrypt hash, role). Passwords are the username + "-demo123"
# for every seed account (see README) — rotate/remove before real use.
USERS = {
    "admin": {"password_hash": bcrypt.hash("admin-demo123"), "role": "admin"},
    "gov_analyst": {"password_hash": bcrypt.hash("gov_analyst-demo123"), "role": "governmental_analyst"},
    "biz_analyst": {"password_hash": bcrypt.hash("biz_analyst-demo123"), "role": "business_analyst"},
}

# Row-level filters injected server-side (never LLM-authored) per role.
# None means "no filter for this table" (full access to whatever the role
# can otherwise see); a role not listing a table at all means "no access".
ROW_FILTERS = {
    "admin": {
        "fact_supply_rate": None,
    },
    "governmental_analyst": {
        "fact_supply_rate": "source_system = 'azure_sql'",
    },
    "business_analyst": {
        "fact_supply_rate": "source_system = 'socrata_rest_api'",
    },
}

# Tables every role may query at all (row filters above further restrict rows).
ALLOWED_TABLES = {
    "admin": {"dim_facility", "fact_generation", "dim_customer_type", "fact_supply_rate", "dim_date"},
    "governmental_analyst": {"dim_facility", "fact_generation", "dim_customer_type", "fact_supply_rate", "dim_date"},
    "business_analyst": {"dim_facility", "fact_generation", "dim_customer_type", "fact_supply_rate", "dim_date"},
}


@dataclass
class Principal:
    username: str
    role: str

    @property
    def allowed_tables(self) -> set[str]:
        return ALLOWED_TABLES.get(self.role, set())

    def row_filter_for(self, table: str) -> str | None:
        return ROW_FILTERS.get(self.role, {}).get(table)


class AuthError(Exception):
    pass


def authenticate(username: str, password: str) -> Principal:
    user = USERS.get(username)
    if not user or not bcrypt.verify(password, user["password_hash"]):
        raise AuthError("Invalid username or password")
    return Principal(username=username, role=user["role"])


def issue_token(principal: Principal) -> str:
    payload = {
        "sub": principal.username,
        "role": principal.role,
        "exp": int(time.time()) + settings.JWT_EXPIRY_MINUTES * 60,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def verify_token(token: str) -> Principal:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise AuthError(f"Invalid or expired token: {e}")
    return Principal(username=payload["sub"], role=payload["role"])
