# Krispy Kreme · Rakhi SKU Tracker

Tracks same-day performance (revenue, units, revenue share) of the 6 Rakhi-launch SKUs:

- Rakhi Special Gift Hamper
- Rakhi Special Doughnut Box of 3
- Rakhi Special Doughnut Box of 6
- Rakhi Sunshine Doughnut
- Choco Caramel Luxe Doughnut
- Nutty Stars Doughnut

Each table's columns: Overall | Online | Online-<city> ... | Offline | Offline-<city> ...
(cities: Bengaluru, Chennai, Hyderabad, NCR, Jaipur, Chandigarh, Pune)

## How it works

- `build/build_data.py` pulls today's (IST) ClickHouse data for brand_id 95469015, using the
  validated item-level `price_share` revenue formula, and writes `data.json`.
- `.github/workflows/refresh.yml` runs this every hour (`workflow_dispatch` also available for
  an on-demand run from the Actions tab) and commits `data.json` if it changed.
- `index.html` is a static page that reads `data.json`, auto-refreshing every hour client-side too.

## Manual run

```
CLICKHOUSE_PASSWORD='...' python3 -m build.build_data
```

Requires repo secret `CLICKHOUSE_PASSWORD` set for the Actions job to run.
