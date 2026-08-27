"""Pulls today's (IST) Rakhi-SKU performance for Krispy Kreme and writes data.json.

Three tables (revenue / units / revenue_share), rows = the 6 SKUs + Total,
columns = Overall | Online | Online-<city>... | Offline | Offline-<city>...
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

from build.clickhouse_client import run_query
from build.queries import build_sku_query, build_total_revenue_query, SKUS

IST = timezone(timedelta(hours=5, minutes=30))

DATA_JSON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data.json"
)

# Validated KK city grouping (from the "Online Revenue (Jul vs Aug 1-25)"
# sheet on project-krispy-kreme-online-dashboard) — fixed order/set so the
# table's column layout stays stable across refreshes through the day.
CITY_GROUPS = ["Bengaluru", "Chennai", "Hyderabad", "NCR", "Jaipur", "Chandigarh", "Pune"]

_CITY_MAP = {
    "bangalore": "Bengaluru", "bengaluru": "Bengaluru",
    "bangalore urban": "Bengaluru", "bangalore rural": "Bengaluru",
    "chennai": "Chennai",
    "hyderabad": "Hyderabad",
    "delhi": "NCR", "new delhi": "NCR", "gurgaon": "NCR", "gurugram": "NCR",
    "noida": "NCR", "ghaziabad": "NCR", "faridabad": "NCR",
    "jaipur": "Jaipur",
    "chandigarh": "Chandigarh", "mohali": "Chandigarh",
    "panchkula": "Chandigarh", "karnal": "Chandigarh",
    "pune": "Pune",
}

_ONLINE_CHANNELS = {"swiggy", "zomato", "ownly"}
_OFFLINE_CHANNELS = {"pos"}


def city_group(raw_city):
    key = (raw_city or "").strip().lower()
    return _CITY_MAP.get(key, "Other")


def today_ist():
    return datetime.now(IST).date()


def channel_bucket(channel):
    c = (channel or "").strip().lower()
    if c in _ONLINE_CHANNELS:
        return "Online"
    if c in _OFFLINE_CHANNELS:
        return "Offline"
    return "Other"  # unexpected channel value — surfaced, not silently dropped


def run(query_runner, date_ist):
    rows = query_runner(build_sku_query(date_ist))
    total_rows = query_runner(build_total_revenue_query(date_ist))

    # Discover which "Other" (unmapped) buckets actually have data, so we
    # never silently drop revenue that doesn't fit the fixed city list.
    extra_cities = {"Online": set(), "Offline": set()}
    extra_channel_seen = False

    revenue = {sku: {} for sku in SKUS}
    units = {sku: {} for sku in SKUS}
    day_total = {}  # whole-brand revenue per column, for the "share of day" table

    def add(table, key, col, val):
        table[key][col] = table[key].get(col, 0) + val

    def add_flat(table, col, val):
        table[col] = table.get(col, 0) + val

    for row in rows:
        item_name = row["item_name"]
        sku = next((s for s in SKUS if s.lower() in item_name.lower()), None)
        if sku is None:
            continue  # shouldn't happen given the SQL filter, but stay safe
        qty = float(row["qty"] or 0)
        rev = float(row["revenue"] or 0)
        bucket = channel_bucket(row["channel"])
        if bucket == "Other":
            extra_channel_seen = True
            continue
        cgroup = city_group(row["city"])
        if cgroup == "Other":
            extra_cities[bucket].add(row["city"] or "(blank)")

        add(revenue, sku, "Overall", rev)
        add(units, sku, "Overall", qty)
        add(revenue, sku, bucket, rev)
        add(units, sku, bucket, qty)
        col = f"{bucket} - {cgroup}"
        add(revenue, sku, col, rev)
        add(units, sku, col, qty)

    for row in total_rows:
        rev = float(row["revenue"] or 0)
        bucket = channel_bucket(row["channel"])
        if bucket == "Other":
            extra_channel_seen = True
            continue
        cgroup = city_group(row["city"])
        if cgroup == "Other":
            extra_cities[bucket].add(row["city"] or "(blank)")
        add_flat(day_total, "Overall", rev)
        add_flat(day_total, bucket, rev)
        add_flat(day_total, f"{bucket} - {cgroup}", rev)

    # Column order: the 3 top-level totals first, then all city cuts —
    # Overall | Online | Offline | Online-<city>... | Offline-<city>...
    columns = ["Overall", "Online", "Offline"]
    columns += [f"Online - {c}" for c in CITY_GROUPS]
    if extra_cities["Online"]:
        columns.append("Online - Other")
    columns += [f"Offline - {c}" for c in CITY_GROUPS]
    if extra_cities["Offline"]:
        columns.append("Offline - Other")

    def total_row(table):
        return {col: sum(table[sku].get(col, 0) for sku in SKUS) for col in columns}

    revenue["Total"] = total_row(revenue)
    units["Total"] = total_row(units)

    # Table 3: each SKU's share of the 6-SKU Rakhi-range total, per column.
    revenue_share = {}
    for sku in SKUS + ["Total"]:
        revenue_share[sku] = {}
        for col in columns:
            denom = revenue["Total"].get(col, 0)
            val = revenue[sku].get(col, 0)
            revenue_share[sku][col] = (val / denom * 100) if denom else 0

    # Table 4: each SKU's share of the WHOLE BRAND's revenue that day, per column.
    revenue_share_of_day = {}
    for sku in SKUS + ["Total"]:
        revenue_share_of_day[sku] = {}
        for col in columns:
            denom = day_total.get(col, 0)
            val = revenue[sku].get(col, 0)
            revenue_share_of_day[sku][col] = (val / denom * 100) if denom else 0

    for sku in SKUS + ["Total"]:
        for col in columns:
            revenue[sku].setdefault(col, 0)
            units[sku].setdefault(col, 0)
    for col in columns:
        day_total.setdefault(col, 0)

    return {
        "generated_at_ist": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
        "date_ist": str(date_ist),
        "skus": SKUS,
        "columns": columns,
        "revenue": revenue,
        "units": units,
        "revenue_share": revenue_share,
        "revenue_share_of_day": revenue_share_of_day,
        "day_total_revenue": day_total,
        "notes": {
            "extra_channel_seen": extra_channel_seen,
            "unmapped_cities": {k: sorted(v) for k, v in extra_cities.items() if v},
        },
    }


def main():
    password = os.environ.get("CLICKHOUSE_PASSWORD")
    if not password:
        print("CLICKHOUSE_PASSWORD not set", file=sys.stderr)
        sys.exit(1)

    date_ist = today_ist()
    payload = run(lambda sql: run_query(sql, password), date_ist)

    with open(DATA_JSON_PATH, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"Wrote {DATA_JSON_PATH} for {date_ist} ({payload['generated_at_ist']})")


if __name__ == "__main__":
    main()
