#!/usr/bin/env python3
"""Build site chart data from the Analysis Productions bookkeeping stats CSVs.

Emits cumulative monthly series, which is what the prose on the projects page
claims ("processed over N exabytes of input"):

    src/data/ap-input.json    cumulative input read, EB
    src/data/ap-output.json   cumulative output created, PB

Note on what these count, carried into the chart captions:
  * successful jobs only, since failed jobs are never registered in the
    bookkeeping, so real resource use is higher than shown;
  * the input side counts every (job, file) read, so a file read by N jobs
    counts N times;
  * output is what was *created*, not what still has a replica, so unlike a
    storage snapshot it does not shrink as old samples are cleaned.

Usage:
    python3 scripts/convert-ap-io.py [--indir ~/cernbox]
"""

import argparse
import csv
import datetime
import json
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "src" / "data"


def load(path: Path, byte_col: str) -> list[tuple[datetime.date, int]]:
    rows = [
        (datetime.date.fromisoformat(r["day"]), int(r[byte_col]))
        for r in csv.DictReader(open(path))
    ]
    if not rows:
        raise SystemExit(f"{path} has no data rows")
    return sorted(rows)


def monthly_cumulative(rows, divisor: float, digits: int):
    """Running total sampled at the end of each complete month."""
    per_month: dict[tuple[int, int], int] = defaultdict(int)
    for day, byts in rows:
        per_month[(day.year, day.month)] += byts

    last_day = rows[-1][0]
    series, running = [], 0
    for (year, month) in sorted(per_month):
        running += per_month[(year, month)]
        # Last day of this month, or where the data stops.
        nxt = datetime.date(year + month // 12, month % 12 + 1, 1)
        end = nxt - datetime.timedelta(days=1)
        if end > last_day:
            continue  # partial trailing month: drop rather than plot a dip
        series.append({"date": end.isoformat(), "value": round(running / divisor, digits)})
    return series


def write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n")
    last = payload["series"][-1]
    print(f"wrote {path.name}  {len(payload['series'])} points, "
          f"ending {last['date']} at {last['value']} {payload['unit']}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--indir", type=Path, default=Path.home() / "cernbox")
    args = p.parse_args()

    inp = load(args.indir / "combined.csv", "total_input_bytes")
    out = load(args.indir / "combined_output.csv", "total_output_bytes")
    through = max(inp[-1][0], out[-1][0])
    print(f"bookkeeping covers {min(inp[0][0], out[0][0])} to {through}")

    in_series = monthly_cumulative(inp, 1e18, 3)
    write(DATA_DIR / "ap-input.json", {
        "title": "Data processed by Analysis Productions",
        "caption": (
            "Cumulative input read by Analysis Productions jobs. Counts "
            "successful jobs only, and a file read by several jobs counts "
            f"each time."
        ),
        "yLabel": "Input processed, cumulative (EB)",
        "unit": "EB",
        "series": in_series,
    })

    out_series = monthly_cumulative(out, 1e15, 2)
    write(DATA_DIR / "ap-output.json", {
        "title": "Analysis Productions output created",
        "caption": (
            "Cumulative output produced for analysts. This is what was "
            "created, not what remains on disk, so it does not shrink as old "
            "samples are cleaned."
        ),
        "yLabel": "Output created, cumulative (PB)",
        "unit": "PB",
        "series": out_series,
    })

    print(f"\nheadline: {in_series[-1]['value']} EB in, {out_series[-1]['value']} PB out "
          f"({in_series[-1]['value'] * 1000 / out_series[-1]['value']:.0f}:1 reduction)")


if __name__ == "__main__":
    main()
