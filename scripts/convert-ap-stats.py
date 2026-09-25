#!/usr/bin/env python3
"""Convert the TransformationDB export in ~/ap-stats into site chart data.

Produces two files in src/data/:

- ap-growth.json — Analysis Productions samples created per month: one per
  TransformationFamily, attributed to the month of its first WGProduction
  transformation (matching plot_transformations_evolution.py).
- ap-output.json — cumulative output data stored, attributing each family's
  output size to its creation month. Sizes come from the public LHCbDIRAC
  storage-usage snapshot joined on ProductionID == output TransformationID
  (again matching plot_transformations_evolution.py), so they reflect data
  currently stored, not originally produced.

The final (partial) month of the export is dropped from both series.

Usage:
    pixi run --manifest-path ~/ap-stats/pixi.toml \
        python scripts/convert-ap-stats.py [--csv ...] [--skip-output]
"""

import argparse
import json
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "src" / "data"
DEFAULT_CSV = Path.home() / "ap-stats" / "results_2026_detailed.csv"
STORAGE_URL = "https://lhcbdirac.s3.cern.ch/storage-usage/storage.csv.zst"


def load_storage_sizes() -> pd.DataFrame:
    """ProductionID -> SESize (bytes), FakeSE rows only (logical sizes)."""

    def keep(df: pd.DataFrame) -> pd.DataFrame:
        df = df[df["SEName"] == "FakeSE"]
        df = df[df["production"].astype(int) >= 0]
        return df

    with pd.read_csv(STORAGE_URL, iterator=True, compression="zstd", chunksize=65536) as reader:
        chunks = [keep(chunk)[["production", "SESize"]] for chunk in reader]
    storage = pd.concat(chunks)
    storage["production"] = storage["production"].astype(int)
    return storage.groupby("production", as_index=False).SESize.sum().rename(
        columns={"production": "ProductionID"}
    )


def write_chart(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {path} ({len(payload['series'])} points)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument(
        "--skip-output",
        action="store_true",
        help="Skip the output-volume chart (avoids the storage snapshot download)",
    )
    args = parser.parse_args()

    df = pd.read_csv(args.csv)
    wg = df[df.TransformationType == "WGProduction"]

    families = wg.groupby("TransformationFamily").MonthStart.min()
    monthly = families.value_counts().sort_index()
    monthly = monthly.iloc[:-1]  # drop the partial final month
    last_full_month = monthly.index[-1]

    per_year = (
        families[families.isin(monthly.index)].str.slice(0, 4).value_counts().sort_index()
    )
    print("Samples per year (sanity check):")
    print(per_year.to_string())

    write_chart(
        DATA_DIR / "ap-growth.json",
        {
            "title": "Analysis Productions samples created per month",
            "caption": (
                "One sample per transformation family, counted in the month of "
                "its first transformation."
            ),
            "yLabel": "Samples created / month",
            "unit": "",
            "series": [
                {"date": month, "value": int(count)} for month, count in monthly.items()
            ],
        },
    )

    if args.skip_output:
        return

    print("\nDownloading storage-usage snapshot...")
    storage = load_storage_sizes()
    print(f"{len(storage)} productions with stored data")

    out = df[df.IsOutputTransformation == 1].copy()
    out["ProductionID"] = out.TransformationID.astype(int)
    out = out.merge(storage, on="ProductionID", how="left")
    family_bytes = out.groupby("TransformationFamily").SESize.sum()

    by_month = (
        pd.DataFrame({"month": families, "bytes": family_bytes})
        .dropna()
        .groupby("month")
        .bytes.sum()
        .sort_index()
    )
    by_month = by_month[by_month.index <= last_full_month]
    cumulative_pb = (by_month.cumsum() / 1e15).round(3)

    total_pb = cumulative_pb.iloc[-1]
    print(f"Total output currently stored: {total_pb:.2f} PB "
          f"({by_month.sum() / 1024**5:.2f} PiB)")

    write_chart(
        DATA_DIR / "ap-output.json",
        {
            "title": "Analysis Productions output data",
            "caption": (
                "Cumulative output attributed to each sample's creation month, "
                "valued at currently stored sizes; data cleaned since is not "
                "counted."
            ),
            "yLabel": "Output stored, cumulative (PB)",
            "unit": "PB",
            "series": [
                {"date": month, "value": float(value)}
                for month, value in cumulative_pb.items()
            ],
        },
    )


if __name__ == "__main__":
    main()
