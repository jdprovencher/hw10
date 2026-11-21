"""
Step 5 - Build the static website in webpage/ from the analysis outputs.

- copies the figures into webpage/assets/
- copies the main CSV tables into webpage/assets/data/
- writes webpage/assets/data.js (a plain <script> payload, so the page also
  works when opened directly from disk with file://)

The HTML, CSS and small chart renderer are hand-written alongside this script.
"""

import json
import shutil
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "output" / "tables"
FIGURES = ROOT / "output" / "figures"
WEB = ROOT / "webpage"
ASSETS = WEB / "assets"
DATA = ASSETS / "data"

# Human-readable labels for the era-comparison table
DISPLAY = {
    "Mean temperature (degC)": ("Annual mean temperature (°C)", "°C", 2),
    "Mean daily maximum (degC)": ("Mean daily maximum (°C)", "°C", 2),
    "Mean daily minimum (degC)": ("Mean daily minimum (°C)", "°C", 2),
    "Diurnal temperature range (degC)": ("Diurnal range, max − min (°C)", "°C", 2),
    "Frost days, TMIN <= 0C (days/yr)": ("Frost days, min ≤ 0 °C (days/yr)", "days", 1),
    "Ice days, TMAX < 0C (days/yr)": ("Ice days, max < 0 °C (days/yr)", "days", 1),
    "Summer days, TMAX >= 25C (days/yr)": ("Summer days, max ≥ 25 °C (days/yr)", "days", 1),
    "Hot days, TMAX >= 30C (days/yr)": ("Hot days, max ≥ 30 °C (days/yr)", "days", 1),
    "Hot days, TMAX >= 90F (days/yr)": ("Hot days, max ≥ 90 °F (days/yr)", "days", 1),
    "Tropical nights, TMIN >= 20C (days/yr)": ("Tropical nights, min ≥ 20 °C (days/yr)", "days", 1),
    "Growing season length (days)": ("Growing season length (days)", "days", 1),
    "Annual precipitation (mm)": ("Annual precipitation (mm)", "mm", 0),
    "Wet days, PRCP >= 1 mm (days/yr)": ("Wet days, ≥ 1 mm (days/yr)", "days", 1),
    "Heavy-precip days, >= 25.4 mm (days/yr)": ("Heavy-precip days, ≥ 25.4 mm (days/yr)", "days", 1),
    "Wettest day of year (mm)": ("Wettest day of the year (mm)", "mm", 1),
    "Annual snowfall (mm)": ("Annual snowfall (mm)", "mm", 0),
}


def round_list(values, ndigits=3):
    out = []
    for v in values:
        if pd.isna(v):
            out.append(None)
        else:
            out.append(round(float(v), ndigits))
    return out


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)

    era = pd.read_csv(TABLES / "era_comparison.csv")
    region = pd.read_csv(TABLES / "region_annual.csv")
    monthly = pd.read_csv(TABLES / "monthly_delta.csv")
    decade = pd.read_csv(TABLES / "decade_summary.csv")
    states = pd.read_csv(TABLES / "state_summary.csv")
    robust = pd.read_csv(TABLES / "robustness.csv")
    coverage = pd.read_csv(TABLES / "station_coverage.csv")

    # ---- figures and data downloads -----------------------------------
    for png in sorted(FIGURES.glob("*.png")):
        shutil.copy2(png, ASSETS / png.name)
    for name in ["era_comparison.csv", "region_annual.csv",
                 "station_coverage.csv", "station_trends.csv", "robustness.csv"]:
        shutil.copy2(TABLES / name, DATA / name)

    # ---- indicator table ------------------------------------------------
    indicators = []
    for _, row in era.iterrows():
        label, unit, nd = DISPLAY.get(row["index"], (row["index"], "", 2))
        p = row["p_wilcoxon"]
        indicators.append({
            "label": label,
            "unit": unit,
            "decimals": nd,
            "e1": round(float(row["era1_mean"]), nd),
            "e2": round(float(row["era2_mean"]), nd),
            "delta": round(float(row["delta"]), nd),
            "median": round(float(row["median_station_delta"]), nd),
            "share": round(float(row["pct_stations_increase"]), 0),
            "n": int(row["n_stations"]),
            "p": None if pd.isna(p) else float(p),
        })

    # ---- annual regional series ----------------------------------------
    region_series = [
        {
            "y": int(r.year),
            "tavg": None if pd.isna(r.tavg_anom) else round(float(r.tavg_anom), 3),
            "tmax": None if pd.isna(r.tmax_anom) else round(float(r.tmax_anom), 3),
            "tmin": None if pd.isna(r.tmin_anom) else round(float(r.tmin_anom), 3),
            "dtr": None if pd.isna(r.dtr_anom) else round(float(r.dtr_anom), 3),
            "prcp": None if pd.isna(r.prcp_total) else round(float(r.prcp_total), 0),
            "n": int(r.n_temp) if pd.notna(r.n_temp) else 0,
        }
        for r in region.itertuples()
    ]

    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    monthly_series = [
        {
            "m": int(r.month),
            "label": months[int(r.month) - 1],
            "e1": round(float(r["1941-2000"]), 2),
            "e2": round(float(r["2001-2020"]), 2),
            "d": round(float(r["delta"]), 2),
        }
        for _, r in monthly.iterrows()
    ]

    decade_series = [
        {
            "label": str(r.decade_label),
            "anom": round(float(r.tavg_anom), 2),
            "frost": round(float(r.frost_days), 1),
            "gsl": round(float(r.growing_season_days), 1),
            "tropical": round(float(r.tropical_nights), 1),
            "prcp": round(float(r.prcp_total), 0),
            "heavy": round(float(r.heavy_days), 1),
            "years": int(r.years),
        }
        for r in decade.itertuples()
        if r.years >= 5
    ]

    state_series = [
        {
            "state": r.state,
            "n": int(r.n_stations),
            "e1": round(float(r.era1_mean), 2),
            "e2": round(float(r.era2_mean), 2),
            "delta": round(float(r.delta), 2),
            "share": round(float(r.share_warming), 0),
        }
        for r in states.itertuples()
    ]

    robust_series = [
        {
            "label": r.comparison,
            "n": int(r.n_stations),
            "mean": round(float(r.mean_delta), 2),
            "median": round(float(r.median_delta), 2),
            "share": round(float(r.pct_warming), 0),
        }
        for r in robust.itertuples()
    ]

    payload = {
        "generated": "2026-11-20",
        "counts": {
            "downloaded": int(coverage["id"].nunique()),
            "temp": int(coverage["temp_station"].sum()),
            "prcp": int(coverage["prcp_station"].sum()),
        },
        "eras": {"e1": [1941, 2000], "e2": [2001, 2020], "baseline": [1961, 1990]},
        "region": region_series,
        "monthly": monthly_series,
        "decade": decade_series,
        "indicators": indicators,
        "states": state_series,
        "robust": robust_series,
    }

    out = ASSETS / "data.js"
    out.write_text(
        "window.CLIMATE = " + json.dumps(payload, ensure_ascii=False, indent=1) + ";\n",
        encoding="utf-8",
    )
    print(f"  figures copied : {len(list(FIGURES.glob('*.png')))}")
    print(f"  wrote {out.relative_to(ROOT)} ({out.stat().st_size / 1024:.0f} KB)")
    print(f"  region years   : {len(region_series)}")


if __name__ == "__main__":
    main()
