"""
Evaluation harness: runs eval_questions.json against a running instance of
the chatbot and reports pass/fail. This is what "evaluate the system against
known business questions" means in practice — not unit tests of the code,
but end-to-end checks of the whole pipeline's behavior.

Usage:
    python run_eval.py [--base-url http://localhost:8000]
"""
import argparse
import json
import sys
from pathlib import Path

import requests

DEMO_PASSWORDS = {
    "admin": "admin-demo123",
    "governmental_analyst": "gov_analyst-demo123",
    "business_analyst": "biz_analyst-demo123",
}
DEMO_USERNAMES = {
    "admin": "admin",
    "governmental_analyst": "gov_analyst",
    "business_analyst": "biz_analyst",
}


def login(base_url: str, role: str) -> str:
    username = DEMO_USERNAMES[role]
    password = DEMO_PASSWORDS[role]
    resp = requests.post(f"{base_url}/login", json={"username": username, "password": password})
    resp.raise_for_status()
    return resp.json()["token"]


def run_case(base_url: str, case: dict, tokens: dict) -> tuple[bool, str, dict]:
    token = tokens[case["role"]]
    resp = requests.post(
        f"{base_url}/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": case["question"]},
    )
    if resp.status_code != 200:
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}", {}

    data = resp.json()
    domains = data.get("domains", [])
    row_count = data.get("row_count", 0)

    expected_domain = case.get("expect_domains_include")
    if expected_domain and expected_domain not in domains:
        return False, f"expected domain '{expected_domain}' in {domains}", data

    if expected_domain is None and domains:
        return False, f"expected no domain match, got {domains}", data

    min_rows = case.get("expect_min_rows", 0)
    if row_count < min_rows:
        return False, f"expected >= {min_rows} rows, got {row_count}", data

    return True, "ok", data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--questions", default=str(Path(__file__).parent / "eval_questions.json"))
    args = parser.parse_args()

    cases = json.loads(Path(args.questions).read_text())
    roles_needed = {c["role"] for c in cases}
    tokens = {role: login(args.base_url, role) for role in roles_needed}

    results = []
    authz_results = {}  # for the gov-vs-biz row-filter comparison

    for case in cases:
        passed, reason, data = run_case(args.base_url, case, tokens)
        results.append((case["id"], passed, reason, data))
        if case["id"].startswith("authz_row_filter_"):
            authz_results[case["id"]] = data

    # Extra check: the two authz cases ask the identical question but as
    # different roles — their raw row data should differ, proving the
    # row-level filter is doing something (not just always the same answer).
    if "authz_row_filter_governmental" in authz_results and "authz_row_filter_business" in authz_results:
        gov_rows = authz_results["authz_row_filter_governmental"].get("rows")
        biz_rows = authz_results["authz_row_filter_business"].get("rows")
        differ = gov_rows != biz_rows
        results.append((
            "authz_rows_actually_differ",
            differ,
            "governmental and business roles returned different rows" if differ
            else "FAIL: identical rows returned for both roles — row-level filter may not be applied",
            {},
        ))

    print(f"\n{'PASS' if all(r[1] for r in results) else 'FAIL'} — {sum(r[1] for r in results)}/{len(results)} checks passed\n")
    for case_id, passed, reason, _ in results:
        mark = "✓" if passed else "✗"
        print(f"  {mark} {case_id}: {reason}")

    sys.exit(0 if all(r[1] for r in results) else 1)


if __name__ == "__main__":
    main()
