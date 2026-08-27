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
- `.github/workflows/refresh.yml` runs this every 30 min (`workflow_dispatch` also available for
  an on-demand run from the Actions tab) and commits `data.json` if it changed. Note: GitHub's
  scheduled-workflow cron is best-effort, not guaranteed — it can be delayed or occasionally skip
  a run under platform load. The dashboard's stale-data banner (>50 min since last pull) is the
  safety net for that; if it fires, trigger a manual run from the Actions tab or `gh workflow run`.
- `index.html` is a static page that reads `data.json`, auto-refreshing every 30 min client-side too.

## Manual run

```
CLICKHOUSE_PASSWORD='...' python3 -m build.build_data
```

Requires repo secret `CLICKHOUSE_PASSWORD` set for the Actions job to run.
