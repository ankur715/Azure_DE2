"""
Local connectivity check for the three NYPA source datasets, before any
Azure infra exists. Downloads small samples into data/raw/ (gitignored).

Usage: python scripts/fetch_nypa_sources.py
"""
import csv
import io
import json
import pathlib
import urllib.request

RAW_DIR = pathlib.Path(__file__).resolve().parent.parent / "data" / "raw"

SOURCES = {
    # CSV file-drop source: generation by facility
    "generation_csv": "https://data.ny.gov/resource/isux-jnrn.csv?$limit=5000",
    # DB-seed source: governmental rate schedule
    "governmental_rates_csv": "https://data.ny.gov/resource/tj6m-a24c.csv?$limit=5000",
    # Live REST API source: business customer rates
    "business_rates_json": "https://data.ny.gov/resource/2x8p-pewm.json?$limit=1000",
}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Azure_DE2-dev"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    body = fetch(SOURCES["generation_csv"])
    (RAW_DIR / "nypa_net_generation.csv").write_bytes(body)
    rows = list(csv.reader(io.StringIO(body.decode())))
    print(f"generation_csv: {len(rows) - 1} rows -> data/raw/nypa_net_generation.csv")

    body = fetch(SOURCES["governmental_rates_csv"])
    (RAW_DIR / "nypa_governmental_rates.csv").write_bytes(body)
    rows = list(csv.reader(io.StringIO(body.decode())))
    print(f"governmental_rates_csv: {len(rows) - 1} rows -> data/raw/nypa_governmental_rates.csv")

    body = fetch(SOURCES["business_rates_json"])
    data = json.loads(body)
    (RAW_DIR / "nypa_business_rates.json").write_bytes(body)
    print(f"business_rates_json: {len(data)} rows -> data/raw/nypa_business_rates.json")


if __name__ == "__main__":
    main()
