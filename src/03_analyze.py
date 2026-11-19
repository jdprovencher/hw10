"""
Step 3 - Build station-year climate indices and compare the eras.

Eras (configurable at the top):
    20th-century tail : 1941-2000  (last six decades of the 1900s)
    21st-century head : 2001-2020  (first two decades of the 2000s)
    baseline          : 1961-1990  (WMO reference period, inside era 1)

Outputs (output/tables/*.csv):
    station_coverage.csv      per-station record completeness + trend
    region_annual.csv         regional annual series for every variable
    era_comparison.csv        era means / deltas / significance per index
    station_deltas.csv        per-station era delta for every index
    monthly_climatology.csv   monthly normals by era
    trends.csv                regional and station trends
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
TABLES = ROOT / "output" / "tables"
TABLES.mkdir(parents=True, exist_ok=True)

ERA1 = (1941, 2000)
ERA2 = (2001, 2020)
BASELINE = (1961, 1990)

# Completeness rules
TEMP_DAYS_MIN = 330        # valid days for a station-year mean temperature
PRCP_DAYS_MIN = 330        # valid days for a station-year precipitation total
ERA1_YEARS_MIN = 50        # of 60 (~83% of years)
ERA2_YEARS_MIN = 16        # of 20 (80% of years)

MM_PER_INCH = 25.4
FROST_C = 0.0
SUMMER_C = 25.0
HOT_C = 30.0
HOT90_C = 32.222
TROPICAL_NIGHT_C = 20.0
HEAVY_PRCP_MM = 25.4


# --------------------------------------------------------------------------
# Loading / reshaping
# --------------------------------------------------------------------------
def load_daily() -> pd.DataFrame:
    path = PROC / "ghcnd_ne_daily.parquet"
    daily = pd.read_parquet(path)
    wide = daily.pivot(index=["id", "date"], columns="element", values="value")
    wide = wide.reset_index()
    wide.columns.name = None
    wide["id"] = wide["id"].astype(str)

    wide["year"] = wide["date"].dt.year.astype("int16")
    wide["month"] = wide["date"].dt.month.astype("int8")
    wide["doy"] = wide["date"].dt.day_of_year.astype("int16")

    has_both = wide["TMAX"].notna() & wide["TMIN"].notna()
    wide["TAVG"] = np.where(has_both, (wide["TMAX"] + wide["TMIN"]) / 2.0, np.nan)
    wide["DTR"] = np.where(has_both, wide["TMAX"] - wide["TMIN"], np.nan)
    return wide


def yearly_indices(wide: pd.DataFrame) -> pd.DataFrame:
    """Collapse daily data to one row per station-year."""
    w = wide
    w = w.assign(
        frost=(w["TMIN"] <= FROST_C).astype("float"),
        frost_valid=w["TMIN"].notna().astype("float"),
        ice=(w["TMAX"] < 0).astype("float"),
        summer=(w["TMAX"] >= SUMMER_C).astype("float"),
        hot=(w["TMAX"] >= HOT_C).astype("float"),
        hot90=(w["TMAX"] >= HOT90_C).astype("float"),
        tropical=(w["TMIN"] >= TROPICAL_NIGHT_C).astype("float"),
        wet=(w["PRCP"] >= 1.0).astype("float"),
        heavy=(w["PRCP"] >= HEAVY_PRCP_MM).astype("float"),
        prcp_valid=w["PRCP"].notna().astype("float"),
    )

    g = w.groupby(["id", "year"], observed=True)
    out = pd.DataFrame(
        {
            "tavg": g["TAVG"].mean(),
            "tmax": g["TMAX"].mean(),
            "tmin": g["TMIN"].mean(),
            "dtr": g["DTR"].mean(),
            "tavg_n": g["TAVG"].count(),
            "tmin_n": g["TMIN"].count(),
            "frost_frac": g["frost"].sum() / g["frost_valid"].sum(),
            "ice_frac": g["ice"].sum() / g["frost_valid"].sum(),
            "summer_frac": g["summer"].sum() / g["frost_valid"].sum(),
            "hot_frac": g["hot"].sum() / g["frost_valid"].sum(),
            "hot90_frac": g["hot90"].sum() / g["frost_valid"].sum(),
            "tropical_frac": g["tropical"].sum() / g["frost_valid"].sum(),
            "prcp_total": g["PRCP"].sum(min_count=1),
            "prcp_n": g["PRCP"].count(),
            "wet_frac": g["wet"].sum() / g["prcp_valid"].sum(),
            "heavy_frac": g["heavy"].sum() / g["prcp_valid"].sum(),
            "rx1day": g["PRCP"].max(),
            "snow_total": g["SNOW"].sum(min_count=1),
            "snow_n": g["SNOW"].count(),
        }
    ).reset_index()

    days = np.where(
        pd.to_datetime(out["year"].astype(str) + "-01-01").dt.is_leap_year, 366, 365
    )
    out["days_in_year"] = days

    temp_ok = out["tavg_n"] >= TEMP_DAYS_MIN
    prcp_ok = out["prcp_n"] >= PRCP_DAYS_MIN

    # Convert fractions to counts (so "frost days" is directly interpretable)
    for frac, count in [
        ("frost_frac", "frost_days"),
        ("ice_frac", "ice_days"),
        ("summer_frac", "summer_days"),
        ("hot_frac", "hot_days"),
        ("hot90_frac", "hot90_days"),
        ("tropical_frac", "tropical_nights"),
        ("wet_frac", "wet_days"),
        ("heavy_frac", "heavy_days"),
    ]:
        out[count] = out[frac] * out["days_in_year"]

    # Snowfall needs its own completeness rule (snow is reported separately)
    out["snow_ok"] = out["snow_n"] >= 300
    out.loc[~out["snow_ok"], "snow_total"] = np.nan

    keep = [
        "id", "year", "days_in_year",
        "tavg", "tmax", "tmin", "dtr", "tavg_n",
        "frost_days", "ice_days", "summer_days", "hot_days", "hot90_days",
        "tropical_nights",
        "prcp_total", "prcp_n", "wet_days", "heavy_days", "rx1day",
        "snow_total", "snow_n",
    ]
    out = out[keep]
    out["temp_ok"] = temp_ok
    out["prcp_ok"] = prcp_ok

    # Blank out aggregates built on too few days, so they never enter averages
    temp_cols = ["tavg", "tmax", "tmin", "dtr", "frost_days", "ice_days",
                 "summer_days", "hot_days", "hot90_days", "tropical_nights"]
    prcp_cols = ["prcp_total", "wet_days", "heavy_days", "rx1day"]
    out.loc[~temp_ok, temp_cols] = np.nan
    out.loc[~prcp_ok, prcp_cols] = np.nan
    return out


def growing_season(wide: pd.DataFrame) -> pd.DataFrame:
    """Frost-free season length: last spring frost -> first autumn frost."""
    w = wide.dropna(subset=["TMIN"])
    spring = w[(w["doy"] < 183) & (w["TMIN"] <= FROST_C)]
    autumn = w[(w["doy"] > 183) & (w["TMIN"] <= FROST_C)]

    last_spring = spring.groupby(["id", "year"])["doy"].max().rename("last_spring_frost")
    first_autumn = autumn.groupby(["id", "year"])["doy"].min().rename("first_autumn_frost")
    valid_days = w.groupby(["id", "year"]).size().rename("n_days")

    gs = pd.concat([last_spring, first_autumn, valid_days], axis=1).reset_index()
    gs["growing_season_days"] = gs["first_autumn_frost"] - gs["last_spring_frost"]
    gs.loc[gs["n_days"] < TEMP_DAYS_MIN, "growing_season_days"] = np.nan
    return gs[["id", "year", "growing_season_days",
               "last_spring_frost", "first_autumn_frost"]]


# --------------------------------------------------------------------------
# Statistics helpers
# --------------------------------------------------------------------------
def era_stats(series: pd.DataFrame, value_col: str, label: str) -> dict:
    s = series[["id", "year", value_col]].dropna()
    a = s[(s["year"] >= ERA1[0]) & (s["year"] <= ERA1[1])]
    b = s[(s["year"] >= ERA2[0]) & (s["year"] <= ERA2[1])]
    pa = a.groupby("id")[value_col].mean()
    pb = b.groupby("id")[value_col].mean()
    common = pa.index.intersection(pb.index)
    delta = (pb.loc[common] - pa.loc[common]).dropna()

    row = {
        "index": label,
        "era1_mean": a[value_col].mean(),
        "era2_mean": b[value_col].mean(),
        "delta": b[value_col].mean() - a[value_col].mean(),
        "pct_change": np.nan,
        "era1_std": a[value_col].std(),
        "era2_std": b[value_col].std(),
        "n_stations": len(common),
        "median_station_delta": delta.median(),
        "p25_station_delta": delta.quantile(0.25),
        "p75_station_delta": delta.quantile(0.75),
        "pct_stations_increase": 100 * (delta > 0).mean(),
        "p_wilcoxon": np.nan,
    }
    if a[value_col].mean() != 0:
        row["pct_change"] = 100 * row["delta"] / abs(a[value_col].mean())
    if len(delta) >= 5:
        try:
            row["p_wilcoxon"] = stats.wilcoxon(delta).pvalue
        except ValueError:
            pass
    return row


def trend_stats(df: pd.DataFrame, value_col: str) -> dict:
    s = df[["year", value_col]].dropna()
    if len(s) < 20:
        return {"slope_per_decade": np.nan, "p_value": np.nan,
                "sen_slope_per_decade": np.nan, "n_years": len(s)}
    lr = stats.linregress(s["year"], s[value_col])
    sen = stats.theilslopes(s[value_col], s["year"], 0.95)
    return {
        "slope_per_decade": lr.slope * 10,
        "p_value": lr.pvalue,
        "sen_slope_per_decade": sen[0] * 10,
        "n_years": len(s),
    }


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main() -> None:
    meta = pd.read_csv(PROC / "candidate_stations.csv")
    wide = load_daily()
    annual = yearly_indices(wide)

    # Strict site de-duplication: same coordinates to ~100 m -> keep the
    # station with the most valid temperature years.
    meta["lat_r"] = meta["lat"].round(3)
    meta["lon_r"] = meta["lon"].round(3)
    coverage = annual.groupby("id")["temp_ok"].sum().rename("temp_years")
    meta = meta.merge(coverage, on="id", how="left")
    n_before = meta["id"].nunique()
    meta = meta.sort_values("temp_years", ascending=False).drop_duplicates(
        subset=["lat_r", "lon_r"], keep="first"
    )
    print(f"Site de-duplication: {n_before} -> {meta['id'].nunique()} stations")

    annual = annual.merge(growing_season(wide), on=["id", "year"], how="left")
    annual = annual[annual["id"].isin(meta["id"])]
    annual = annual[annual["year"].between(ERA1[0], ERA2[1])]

    # ---- station eligibility -------------------------------------------
    def valid_years(df: pd.DataFrame, flag: str, era: tuple) -> pd.Series:
        sub = df[(df["year"] >= era[0]) & (df["year"] <= era[1])]
        return sub.groupby("id")[flag].sum()

    temp_e1 = valid_years(annual, "temp_ok", ERA1).reindex(meta["id"], fill_value=0)
    temp_e2 = valid_years(annual, "temp_ok", ERA2).reindex(meta["id"], fill_value=0)
    prcp_e1 = valid_years(annual, "prcp_ok", ERA1).reindex(meta["id"], fill_value=0)
    prcp_e2 = valid_years(annual, "prcp_ok", ERA2).reindex(meta["id"], fill_value=0)

    meta["temp_years_era1"] = temp_e1.values
    meta["temp_years_era2"] = temp_e2.values
    meta["prcp_years_era1"] = prcp_e1.values
    meta["prcp_years_era2"] = prcp_e2.values
    meta["temp_station"] = (
        (temp_e1 >= ERA1_YEARS_MIN) & (temp_e2 >= ERA2_YEARS_MIN)
    ).to_numpy()
    meta["prcp_station"] = (
        (prcp_e1 >= ERA1_YEARS_MIN) & (prcp_e2 >= ERA2_YEARS_MIN)
    ).to_numpy()

    print(f"Temperature stations (>= {ERA1_YEARS_MIN}/60 and >= {ERA2_YEARS_MIN}/20 yrs): "
          f"{int(meta['temp_station'].sum())}")
    print(f"Precipitation stations: {int(meta['prcp_station'].sum())}")

    temp_ids = set(meta.loc[meta["temp_station"], "id"])
    prcp_ids = set(meta.loc[meta["prcp_station"], "id"])

    # ---- regional annual series (only eligible stations) ---------------
    t = annual[annual["id"].isin(temp_ids)].copy()
    p = annual[annual["id"].isin(prcp_ids)].copy()

    # Station anomalies w.r.t. the 1961-1990 baseline, then equal-weight mean
    def add_anomalies(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
        base = df[(df["year"] >= BASELINE[0]) & (df["year"] <= BASELINE[1])]
        ref = base.groupby("id")[cols].mean()
        ref.columns = [f"{c}_base" for c in cols]
        df = df.merge(ref, left_on="id", right_index=True, how="left")
        for c in cols:
            df[f"{c}_anom"] = df[c] - df[f"{c}_base"]
        return df

    t = add_anomalies(t, ["tavg", "tmax", "tmin", "dtr"])
    p = add_anomalies(p, ["prcp_total"])

    region = (
        t.groupby("year")
        .agg(
            tavg_anom=("tavg_anom", "mean"),
            tmax_anom=("tmax_anom", "mean"),
            tmin_anom=("tmin_anom", "mean"),
            dtr_anom=("dtr_anom", "mean"),
            tavg=("tavg", "mean"),
            n_temp=("tavg", "count"),
        )
        .join(
            p.groupby("year").agg(
                prcp_total=("prcp_total", "mean"),
                prcp_anom=("prcp_total_anom", "mean"),
                n_prcp=("prcp_total", "count"),
            )
        )
        .reset_index()
    )
    region["tavg_anom_smooth"] = region["tavg_anom"].rolling(10, center=True, min_periods=6).mean()
    region.to_csv(TABLES / "region_annual.csv", index=False)

    # ---- era comparison ------------------------------------------------
    temp_indices = {
        "tavg": "Mean temperature (degC)",
        "tmax": "Mean daily maximum (degC)",
        "tmin": "Mean daily minimum (degC)",
        "dtr": "Diurnal temperature range (degC)",
        "frost_days": "Frost days, TMIN <= 0C (days/yr)",
        "ice_days": "Ice days, TMAX < 0C (days/yr)",
        "summer_days": "Summer days, TMAX >= 25C (days/yr)",
        "hot_days": "Hot days, TMAX >= 30C (days/yr)",
        "hot90_days": "Hot days, TMAX >= 90F (days/yr)",
        "tropical_nights": "Tropical nights, TMIN >= 20C (days/yr)",
        "growing_season_days": "Growing season length (days)",
    }
    prcp_indices = {
        "prcp_total": "Annual precipitation (mm)",
        "wet_days": "Wet days, PRCP >= 1 mm (days/yr)",
        "heavy_days": "Heavy-precip days, >= 25.4 mm (days/yr)",
        "rx1day": "Wettest day of year (mm)",
        "snow_total": "Annual snowfall (mm)",
    }

    rows, station_deltas = [], []
    for col, label in {**temp_indices, **prcp_indices}.items():
        frame = p if col in prcp_indices else t
        rows.append(era_stats(frame, col, label))

        s = frame[["id", "year", col]].dropna()
        pa = s[s["year"].between(*ERA1)].groupby("id")[col].mean()
        pb = s[s["year"].between(*ERA2)].groupby("id")[col].mean()
        d = (pb - pa).dropna().rename("delta").reset_index()
        d["index"] = label
        station_deltas.append(d)

    era_table = pd.DataFrame(rows)
    era_table.to_csv(TABLES / "era_comparison.csv", index=False)
    pd.concat(station_deltas, ignore_index=True).to_csv(
        TABLES / "station_deltas.csv", index=False
    )

    # ---- monthly climatology -------------------------------------------
    w2 = wide.copy()
    w2["era"] = np.where(
        w2["year"].between(*ERA1), "1941-2000",
        np.where(w2["year"].between(*ERA2), "2001-2020", None),
    )
    w2 = w2[w2["id"].isin(temp_ids) & w2["era"].notna()]
    monthly = (
        w2.groupby(["era", "month"])[["TMAX", "TMIN", "TAVG"]]
        .mean()
        .reset_index()
        .rename(columns={"TMAX": "tmax", "TMIN": "tmin", "TAVG": "tavg"})
    )
    monthly.to_csv(TABLES / "monthly_climatology.csv", index=False)

    # Monthly anomaly of mean temperature relative to era 1
    m_pivot = monthly.pivot(index="month", columns="era", values="tavg")
    m_pivot["delta"] = m_pivot["2001-2020"] - m_pivot["1941-2000"]
    m_pivot.to_csv(TABLES / "monthly_delta.csv")

    # ---- seasonal climatology ------------------------------------------
    w2["season"] = np.select(
        [w2["month"].isin([12, 1, 2]), w2["month"].isin([3, 4, 5]),
         w2["month"].isin([6, 7, 8]), w2["month"].isin([9, 10, 11])],
        ["DJF", "MAM", "JJA", "SON"],
        default="",
    )
    seasonal = (
        w2.groupby(["era", "season"])[["TMAX", "TMIN", "TAVG"]]
        .mean()
        .reset_index()
        .rename(columns={"TMAX": "tmax", "TMIN": "tmin", "TAVG": "tavg"})
    )
    seasonal.to_csv(TABLES / "seasonal_climatology.csv", index=False)

    # ---- growing-season endpoints ---------------------------------------
    gs = annual[(annual["id"].isin(temp_ids))
                & annual["growing_season_days"].notna()].copy()
    gs["era"] = np.where(gs["year"].between(*ERA1), "1941-2000", "2001-2020")
    gs_comp = (
        gs.groupby("era")[["last_spring_frost", "first_autumn_frost",
                           "growing_season_days"]]
        .mean()
        .reset_index()
    )
    gs_comp.to_csv(TABLES / "growing_season_components.csv", index=False)

    # ---- decade summary --------------------------------------------------
    dec = t[["id", "year", "tavg_anom", "frost_days", "tropical_nights",
             "growing_season_days"]].copy()
    dec = dec.merge(
        p[["id", "year", "prcp_total", "heavy_days"]], on=["id", "year"], how="outer"
    )
    dec["decade"] = (dec["year"] // 10) * 10
    decade = (
        dec.groupby("decade")
        .agg(
            years=("year", "nunique"),
            tavg_anom=("tavg_anom", "mean"),
            frost_days=("frost_days", "mean"),
            tropical_nights=("tropical_nights", "mean"),
            growing_season_days=("growing_season_days", "mean"),
            prcp_total=("prcp_total", "mean"),
            heavy_days=("heavy_days", "mean"),
        )
        .reset_index()
    )
    decade["decade_label"] = decade["decade"].astype(str) + "s"
    decade.to_csv(TABLES / "decade_summary.csv", index=False)

    # ---- trends --------------------------------------------------------
    # Build a regional time series for every index (equal-weight station mean).
    # Temperature aggregates use anomalies so a changing station mix cannot
    # masquerade as a climate trend; the count-based indices need no baseline.
    anom_cols = ["tavg_anom", "tmax_anom", "tmin_anom", "dtr_anom"]
    rt = t.groupby("year")[anom_cols].mean()
    rt.columns = [c.replace("_anom", "") for c in rt.columns]
    other_temp = [c for c in temp_indices if c not in rt.columns]
    rt = rt.join(t.groupby("year")[other_temp].mean())
    rp = p.groupby("year")[list(prcp_indices)].mean()
    region_all = rt.join(rp).reset_index()
    region_all.to_csv(TABLES / "region_all_indices.csv", index=False)

    trend_rows = []
    for col, label in {**temp_indices, **prcp_indices}.items():
        r = trend_stats(region_all, col)
        trend_rows.append({"series": "region", "index": label, **r})
    pd.DataFrame(trend_rows).to_csv(TABLES / "trends.csv", index=False)

    # Per-station trends for the map + distribution figures
    station_trends = []
    for sid, grp in t.groupby("id"):
        trend = trend_stats(grp, "tavg")
        trend.update({f"frost_{k}": v for k, v in trend_stats(grp, "frost_days").items()})
        trend["id"] = sid
        station_trends.append(trend)
    st = pd.DataFrame(station_trends).merge(
        meta[["id", "name", "state", "lat", "lon", "elev_m"]], on="id", how="left"
    )
    st.to_csv(TABLES / "station_trends.csv", index=False)

    # ---- state-level warming -------------------------------------------
    ts = t.merge(meta[["id", "state"]], on="id", how="left")
    state_rows = []
    for state, grp in ts.groupby("state"):
        a = grp[grp["year"].between(*ERA1)].groupby("id")["tavg"].mean()
        b = grp[grp["year"].between(*ERA2)].groupby("id")["tavg"].mean()
        d = (b - a).dropna()
        state_rows.append({
            "state": state,
            "n_stations": len(d),
            "era1_mean": grp[grp["year"].between(*ERA1)]["tavg"].mean(),
            "era2_mean": grp[grp["year"].between(*ERA2)]["tavg"].mean(),
            "delta": d.mean(),
            "share_warming": 100 * (d > 0).mean(),
        })
    pd.DataFrame(state_rows).sort_values("delta", ascending=False).to_csv(
        TABLES / "state_summary.csv", index=False
    )

    # ---- robustness of the temperature delta ----------------------------
    ann_all = annual[annual["temp_ok"]]
    robust_rows = []
    for y1, y2 in [(50, 16), (55, 18), (45, 15), (30, 10), (5, 5)]:
        c1 = ann_all[ann_all["year"].between(*ERA1)].groupby("id").size()
        c2 = ann_all[ann_all["year"].between(*ERA2)].groupby("id").size()
        ids = c1[c1 >= y1].index.intersection(c2[c2 >= y2].index)
        s = ann_all[ann_all["id"].isin(ids)]
        a = s[s["year"].between(*ERA1)].groupby("id")["tavg"].mean()
        b = s[s["year"].between(*ERA2)].groupby("id")["tavg"].mean()
        d = (b - a).dropna()
        robust_rows.append({
            "years_required_era1": y1,
            "years_required_era2": y2,
            "n_stations": len(d),
            "mean_delta": d.mean(),
            "median_delta": d.median(),
            "pct_warming": 100 * (d > 0).mean(),
        })
    # independent check with the 1951-1980 -> 1991-2020 normal periods
    a = ann_all[ann_all["year"].between(1951, 1980)].groupby("id")["tavg"].mean()
    b = ann_all[ann_all["year"].between(1991, 2020)].groupby("id")["tavg"].mean()
    d = (b - a).dropna()
    robust_rows.append({
        "years_required_era1": np.nan,
        "years_required_era2": np.nan,
        "n_stations": len(d),
        "mean_delta": d.mean(),
        "median_delta": d.median(),
        "pct_warming": 100 * (d > 0).mean(),
    })
    robust = pd.DataFrame(robust_rows)
    robust["comparison"] = ["50/16 (main)", "55/18", "45/15", "30/10",
                            "5/5 (all)", "1951-1980 vs 1991-2020"]
    robust.to_csv(TABLES / "robustness.csv", index=False)

    # ---- station coverage table ----------------------------------------
    cov = (
        annual.groupby("id")
        .agg(
            record_first_year=("year", "min"),
            record_last_year=("year", "max"),
            temp_years=("temp_ok", "sum"),
            prcp_years=("prcp_ok", "sum"),
        )
        .reset_index()
    )
    cov = meta.drop(columns=["temp_years", "first_year", "last_year"]).merge(
        cov, on="id", how="left"
    )
    cov.to_csv(TABLES / "station_coverage.csv", index=False)

    # Station-year table for distribution figures
    station_annual = t[[
        "id", "year", "tavg", "tavg_anom", "tmax_anom", "tmin_anom", "dtr_anom",
        "frost_days", "ice_days", "summer_days", "hot_days", "tropical_nights",
        "growing_season_days",
    ]].merge(
        p[["id", "year", "prcp_total", "heavy_days", "rx1day"]],
        on=["id", "year"], how="outer",
    )
    station_annual.to_csv(TABLES / "station_annual.csv", index=False)

    # ---- console summary ------------------------------------------------
    print("\n=== ERA COMPARISON (equal-weight station means) ===")
    show = era_table.copy()
    for c in ["era1_mean", "era2_mean", "delta", "median_station_delta"]:
        show[c] = show[c].round(2)
    show["p_wilcoxon"] = show["p_wilcoxon"].round(4)
    show["pct_stations_increase"] = show["pct_stations_increase"].round(0)
    print(show[["index", "era1_mean", "era2_mean", "delta",
                "median_station_delta", "pct_stations_increase", "p_wilcoxon"]]
          .to_string(index=False))

    print("\n=== REGIONAL ANNUAL TRENDS ===")
    tr = pd.read_csv(TABLES / "trends.csv")
    tr["slope_per_decade"] = tr["slope_per_decade"].round(3)
    tr["p_value"] = tr["p_value"].round(4)
    print(tr[["series", "index", "slope_per_decade", "p_value", "n_years"]].to_string(index=False))

    print(f"\nRegional temperature trend: {trend_stats(region, 'tavg_anom')}")
    print(f"Baseline {BASELINE[0]}-{BASELINE[1]}, years {int(region['year'].min())}-{int(region['year'].max())}")
    print(f"Stations in regional temperature series: {len(temp_ids)}")
    print(f"Stations in regional precipitation series: {len(prcp_ids)}")


if __name__ == "__main__":
    main()
