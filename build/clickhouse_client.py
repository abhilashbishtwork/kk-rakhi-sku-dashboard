"""Thin ClickHouse HTTP client — same pattern as kk-90d-stores-dashboard."""

import subprocess
from urllib.parse import quote

CLICKHOUSE_URL = "https://cfi-data-secure.urbanpiper.com:443/"
CLICKHOUSE_DATABASE = "curefoods_test"
CLICKHOUSE_USER = "curefoods"


def parse_tsv_with_names(text):
    stripped = text.strip("\n")
    if not stripped:
        return []
    lines = stripped.split("\n")
    header = lines[0].split("\t")
    rows = []
    for line in lines[1:]:
        if line == "":
            continue
        values = line.split("\t")
        rows.append(dict(zip(header, values)))
    return rows


def run_query(sql, password):
    encoded_password = quote(password, safe="")
    result = subprocess.run(
        [
            "curl", "-sk", "--max-time", "90",
            f"{CLICKHOUSE_URL}?database={CLICKHOUSE_DATABASE}&user={CLICKHOUSE_USER}&password={encoded_password}",
            "--data-binary", sql,
        ],
        capture_output=True, text=True, check=True,
    )
    if result.stdout.startswith("Code:"):
        raise RuntimeError(f"ClickHouse error: {result.stdout}")
    return parse_tsv_with_names(result.stdout)
