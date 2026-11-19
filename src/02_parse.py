"""
Step 2 - Parse the fixed-width GHCNd *.dly files into one tidy table.

.dly layout (per line = one station / month / element):
    ID 1-11 | YEAR 12-15 | MONTH 16-17 | ELEMENT 18-21 |
    31 x (VALUE 5 | MFLAG 1 | QFLAG 1 | SFLAG 1)

Values are integers in tenths:  TMAX/TMIN = 0.1 degC,
PRCP/SNOW/SNWD = 0.1 mm, -9999 = missing.

Data-quality flags: any non-blank QFLAG means the value failed one of the
GHCNd quality tests, so those values are dropped. The SFLAG (source) is
kept because it is useful for provenance checks.

Output: data/processed/ghcnd_ne_daily.parquet
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DLY = ROOT / "data" / "raw" / "dly"
PROC = ROOT / "data" / "processed"

YEARS = range(1941, 2022)  # study window + 1 spare year
ELEMENTS = {"TMAX", "TMIN", "PRCP", "SNOW", "SNWD"}
SCALE = {"TMAX": 10.0, "TMIN": 10.0, "PRCP": 10.0, "SNOW": 10.0, "SNWD": 10.0}

# Column layout for pandas.read_fwf: header + 31 value fields + 31 q-flags
COLSPECS = [(0, 11), (11, 15), (15, 17), (17, 21)]
NAMES = ["id", "year", "month", "element"]
for d in range(1, 32):
    start = 21 + (d - 1) * 8
    COLSPECS.append((start, start + 5))
    NAMES.append(f"v{d}")
for d in range(1, 32):
    start = 21 + (d - 1) * 8 + 6
    COLSPECS.append((start, start + 1))
    NAMES.append(f"q{d}")

VALUE_COLS = [f"v{d}" for d in range(1, 32)]
QFLAG_COLS = [f"q{d}" for d in range(1, 32)]


def parse_file(path: Path) -> pd.DataFrame | None:
    df = pd.read_fwf(path, colspecs=COLSPECS, names=NAMES, dtype=str)
    df = df[df["element"].isin(ELEMENTS)]
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df[df["year"].isin(YEARS)]
    if df.empty:
        return None

    long = df.melt(
        id_vars=["id", "year", "month", "element"],
        value_vars=VALUE_COLS,
        var_name="day_col",
        value_name="raw_value",
    )
    qlong = df.melt(
        id_vars=["id", "year", "month", "element"],
        value_vars=QFLAG_COLS,
        var_name="day_col_q",
        value_name="qflag",
    )
    # melt preserves row order, so the two frames line up 1:1
    long["qflag"] = qlong["qflag"].to_numpy()

    long["day"] = long["day_col"].str[1:].astype(int)
    long["value"] = pd.to_numeric(long["raw_value"], errors="coerce")
    long = long[(long["value"] != -9999) & long["value"].notna()]

    # Drop values that failed GHCNd quality control
    long["qflag"] = long["qflag"].fillna(" ").str.strip()
    long = long[long["qflag"] == ""]
    long = long.drop(columns=["raw_value", "qflag", "day_col"])

    long["date"] = pd.to_datetime(
        dict(year=long["year"], month=long["month"], day=long["day"]),
        errors="coerce",
    )
    long = long[long["date"].notna()]

    long["value"] = (long["value"] / long["element"].map(SCALE)).astype("float32")
    long["month"] = long["month"].astype("int8")
    long["year"] = long["year"].astype("int16")
    long["id"] = long["id"].astype("category")
    long["element"] = long["element"].astype("category")
    return long[["id", "date", "year", "month", "element", "value"]]


def main() -> None:
    files = sorted(DLY.glob("*.dly"))
    if not files:
        raise SystemExit("No .dly files found - run src/01_download.py first")

    frames = []
    for i, path in enumerate(files, 1):
        parsed = parse_file(path)
        if parsed is not None:
            frames.append(parsed)
        if i % 20 == 0 or i == len(files):
            print(f"  parsed {i}/{len(files)} files", flush=True)

    daily = pd.concat(frames, ignore_index=True)
    daily = daily.sort_values(["id", "date", "element"], ignore_index=True)

    out = PROC / "ghcnd_ne_daily.parquet"
    daily.to_parquet(out, index=False, compression="zstd")

    print(f"\nRows: {len(daily):,}")
    print(f"Stations: {daily['id'].nunique()}")
    print(f"Date range: {daily['date'].min().date()} -> {daily['date'].max().date()}")
    print("\nRows per element:")
    print(daily["element"].value_counts().to_string())
    print(f"\nWrote {out.relative_to(ROOT)} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
