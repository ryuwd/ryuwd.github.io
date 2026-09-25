#!/usr/bin/env python3
"""Build chart data for the site from the LbAPI storage-stats endpoint.

Reconstructs a monthly series of Analysis Productions output on disk by
querying /productions/-/storage-stats?at_time=<month> and summing physical
storage across working groups. Sample membership is historical (the AP
database is temporally versioned); byte sizes are today's, so months where
data has since been cleaned are undercounted. The chart caption says so.

Auth: Kerberos via `curl --negotiate` (run `kinit` first), or set
LBAP_TOKEN for bearer-token auth.

Usage:
    python3 scripts/fetch-ap-growth.py [--start 2021-01] [--base-url URL]

Writes src/data/ap-growth.json.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

DEFAULT_BASE_URL = "https://lbap.app.cern.ch"
OUT_PATH = Path(__file__).resolve().parent.parent / "src" / "data" / "ap-growth.json"


def fetch(base_url: str, path: str, params: dict) -> object:
    url = f"{base_url}{path}?" + "&".join(f"{k}={v}" for k, v in params.items())
    cmd = ["curl", "--silent", "--show-error", "--fail-with-body", "--max-time", "120"]
    token = os.environ.get("LBAP_TOKEN")
    if token:
        cmd += ["-H", f"Authorization: Bearer {token}"]
    else:
        cmd += ["--negotiate", "-u", ":"]
    cmd.append(url)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(
            f"Request failed for {url}\n{proc.stderr.strip()}\n{proc.stdout[:500]}\n"
            "Hint: run `kinit` (or export LBAP_TOKEN) and retry."
        )
    return json.loads(proc.stdout)


def month_starts(start: date, end: date):
    y, m = start.year, start.month
    while date(y, m, 1) <= end:
        yield date(y, m, 1)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2021-01", help="First month (YYYY-MM)")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    args = parser.parse_args()

    start = datetime.strptime(args.start, "%Y-%m").date()
    today = datetime.now(timezone.utc).date()

    series = []
    for month in month_starts(start, today):
        at_time = f"{month.isoformat()}T00:00:00"
        rows = fetch(
            args.base_url,
            "/productions/-/storage-stats",
            {"group_by": "wg", "at_time": at_time},
        )
        total_bytes = sum(r.get("physical_storage", 0) for r in rows)
        petabytes = round(total_bytes / 1e15, 2)
        series.append({"date": month.isoformat(), "value": petabytes})
        print(f"{month}: {petabytes} PB", file=sys.stderr)

    # Drop leading empty months.
    while series and series[0]["value"] == 0:
        series.pop(0)
    if not series:
        raise SystemExit("No non-zero data returned; check the query.")

    payload = {
        "title": "Analysis Productions output on disk",
        "caption": (
            "Output attributable to samples existing at each date, "
            "valued at current storage sizes; cleaned data is not counted."
        ),
        "yLabel": "Output on disk (PB)",
        "unit": "PB",
        "series": series,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {OUT_PATH} ({len(series)} points)")


if __name__ == "__main__":
    main()
