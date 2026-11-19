"""
Step 4 - Figures.

Reads output/tables/*.csv and writes PNGs to output/figures/.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "output" / "tables"
FIG = ROOT / "output" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

C_ERA1 = "#2c7fb8"
C_ERA2 = "#d7301f"
C_WARM = "#c0392b"
C_COOL = "#2980b9"
C_INK = "#1a1a1a"
C_MUTED = "#6b7280"

plt.rcParams.update({
    "figure.dpi": 150,
    "savefig.dpi": 150,
    "font.size": 9,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.labelsize": 9,
    "axes.edgecolor": "#444444",
    "axes.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": "#e5e7eb",
    "grid.linewidth": 0.6,
    "legend.frameon": False,
})


def load(name: str) -> pd.DataFrame:
    return pd.read_csv(T / name)


def era_means() -> pd.DataFrame:
    return load("era_comparison.csv").set_index("index")


def save(fig: plt.Figure, name: str) -> None:
    out = FIG / name
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  wrote {out.relative_to(ROOT)}")


# --------------------------------------------------------------------------
def fig_temperature_timeseries() -> None:
    r = load("region_annual.csv")
    dec = load("decade_summary.csv")

    fig, (ax, ax2) = plt.subplots(
        2, 1, figsize=(9.5, 6.4), height_ratios=[2.4, 1], sharex=False
    )

    colors = np.where(r["tavg_anom"] >= 0, C_WARM, C_COOL)
    ax.bar(r["year"], r["tavg_anom"], color=colors, width=0.8, alpha=0.55,
           label="Annual anomaly")
    ax.plot(r["year"], r["tavg_anom_smooth"], color=C_INK, lw=2,
            label="10-year running mean")
    ax.axhline(0, color=C_MUTED, lw=0.8)

    m1 = r.loc[r["year"].between(1941, 2000), "tavg_anom"].mean()
    m2 = r.loc[r["year"].between(2001, 2020), "tavg_anom"].mean()
    ax.hlines(m1, 1941, 2000, color=C_ERA1, lw=2.2, ls="--",
              label=f"1941-2000 average ({m1:+.2f} °C)")
    ax.hlines(m2, 2001, 2020, color=C_ERA2, lw=2.2, ls="--",
              label=f"2001-2020 average ({m2:+.2f} °C)")
    ax.axvline(2000.5, color=C_MUTED, lw=0.8, ls=":")
    ax.set_xlim(1940, 2021)
    ax.set_ylabel("Temperature anomaly (°C)")
    ax.set_title("New England annual mean temperature, relative to the 1961-1990 baseline")
    ax.legend(loc="upper left", ncol=2, fontsize=8)

    # Decade means
    dec = dec[dec["years"] >= 5]
    dcol = np.where(dec["tavg_anom"] >= 0, C_WARM, C_COOL)
    ax2.bar(dec["decade_label"], dec["tavg_anom"], color=dcol, alpha=0.8, width=0.7)
    ax2.axhline(0, color=C_MUTED, lw=0.8)
    for x, v in zip(dec["decade_label"], dec["tavg_anom"]):
        ax2.text(x, v + (0.03 if v >= 0 else -0.06), f"{v:+.2f}",
                 ha="center", fontsize=7.5, color=C_INK)
    ax2.set_ylabel("Anomaly (°C)")
    ax2.set_title("Decade averages")
    ax2.set_ylim(dec["tavg_anom"].min() - 0.25, dec["tavg_anom"].max() + 0.25)

    fig.tight_layout()
    save(fig, "fig1_temperature_timeseries.png")


def fig_seasonal_cycle() -> None:
    m = load("monthly_climatology.csv")
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    p = m.pivot(index="month", columns="era", values="tavg")
    delta = p["2001-2020"] - p["1941-2000"]

    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(8.5, 6.2),
                                  height_ratios=[2, 1], sharex=True)

    ax.plot(months, p["1941-2000"], "-o", color=C_ERA1, lw=2, ms=4,
            label="1941-2000")
    ax.plot(months, p["2001-2020"], "-o", color=C_ERA2, lw=2, ms=4,
            label="2001-2020")
    ax.fill_between(months, p["1941-2000"], p["2001-2020"],
                    color=C_ERA2, alpha=0.12)
    ax.set_ylabel("Mean temperature (°C)")
    ax.set_title("Monthly temperature climatology: last six decades of the 20th century vs 2001-2020")
    ax.legend(loc="upper left")

    bars = ax2.bar(months, delta.values,
                   color=np.where(delta.values >= 0, C_WARM, C_COOL), alpha=0.85)
    ax2.axhline(0, color=C_MUTED, lw=0.8)
    ax2.set_ylabel("Δ °C")
    ax2.set_title("Warming by calendar month (2001-2020 minus 1941-2000)")
    for b, v in zip(bars, delta.values):
        ax2.text(b.get_x() + b.get_width() / 2,
                 v + (0.02 if v >= 0 else -0.05), f"{v:+.1f}",
                 ha="center", fontsize=7.5)

    fig.tight_layout()
    save(fig, "fig2_seasonal_cycle.png")


def fig_station_deltas() -> None:
    sd = load("station_annual.csv")
    meta = load("station_coverage.csv")
    w = sd.dropna(subset=["tavg_anom", "year"])
    a = w[w["year"].between(1941, 2000)].groupby("id")["tavg_anom"].mean()
    b = w[w["year"].between(2001, 2020)].groupby("id")["tavg_anom"].mean()
    d = (b - a).dropna().rename("delta").reset_index()
    d = d.merge(meta[["id", "state", "name"]], on="id").sort_values("delta")

    palette = {"CT": "#8dd3c7", "MA": "#ffffb3", "ME": "#bebada",
               "NH": "#fb8072", "RI": "#80b1d3", "VT": "#fdb462"}

    fig, ax = plt.subplots(figsize=(7.5, 8))
    colors = d["state"].map(palette)
    ax.barh(range(len(d)), d["delta"], color=colors, edgecolor="#333", lw=0.4)
    ax.axvline(0, color=C_INK, lw=1)
    ax.set_yticks(range(len(d)))
    ax.set_yticklabels([f"{n.title()} ({s})" for n, s in zip(d["name"], d["state"])],
                       fontsize=7)
    ax.set_xlabel("Change in annual mean temperature (°C), 2001-2020 minus 1941-2000")
    ax.set_title("Station-by-station warming, New England")
    ax.grid(axis="y", visible=False)

    for state, color in palette.items():
        if state in set(d["state"]):
            ax.legend(handles=[Patch(facecolor=color, edgecolor="#333", label=state)
                               for state, color in palette.items() if state in set(d["state"])],
                      loc="lower right", title="State", fontsize=8)

    fig.tight_layout()
    save(fig, "fig3_station_deltas.png")


def fig_extremes() -> None:
    r = load("region_annual.csv")
    idx = load("region_all_indices.csv")
    em = era_means()

    panels = [
        ("frost_days", "Frost days, TMIN <= 0C (days/yr)", "Frost days (TMIN ≤ 0 °C)", "#4575b4"),
        ("growing_season_days", "Growing season length (days)", "Growing season (days)", "#1a9850"),
        ("tropical_nights", "Tropical nights, TMIN >= 20C (days/yr)", "Tropical nights (TMIN ≥ 20 °C)", "#d73027"),
        ("heavy_days", "Heavy-precip days, >= 25.4 mm (days/yr)", "Heavy-precip days (≥ 25.4 mm)", "#7b3294"),
    ]

    fig, axes = plt.subplots(2, 2, figsize=(9.5, 6.4))
    for ax, (col, key, label, color) in zip(axes.flat, panels):
        s = idx[["year", col]].dropna()
        ax.plot(s["year"], s[col], color=color, lw=1, alpha=0.45)
        ax.scatter(s["year"], s[col], s=6, color=color, alpha=0.6)
        roll = s.set_index("year")[col].rolling(10, center=True, min_periods=6).mean()
        ax.plot(roll.index, roll.values, color=C_INK, lw=2, label="10-year mean")

        row = em.loc[key]
        ax.hlines(row["era1_mean"], 1941, 2000, color=C_ERA1, ls="--", lw=1.8,
                  label=f"1941-2000: {row['era1_mean']:.1f}")
        ax.hlines(row["era2_mean"], 2001, 2020, color=C_ERA2, ls="--", lw=1.8,
                  label=f"2001-2020: {row['era2_mean']:.1f}")
        ax.set_title(label)
        ax.set_xlim(1940, 2021)
        ax.legend(fontsize=7, loc="best")

    fig.suptitle("Climate extremes in New England, 1941-2020", fontweight="bold")
    fig.tight_layout()
    save(fig, "fig4_extremes.png")


def fig_precipitation() -> None:
    r = load("region_annual.csv")
    em = era_means()
    pr = em.loc["Annual precipitation (mm)"]

    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(9.5, 6.2), sharex=True,
                                  height_ratios=[2, 1])

    ax.plot(r["year"], r["prcp_total"], color="#2166ac", lw=1, alpha=0.5)
    ax.scatter(r["year"], r["prcp_total"], s=10, color="#2166ac", alpha=0.7)
    roll = r.set_index("year")["prcp_total"].rolling(10, center=True, min_periods=6).mean()
    ax.plot(roll.index, roll.values, color=C_INK, lw=2, label="10-year mean")
    ax.hlines(pr["era1_mean"], 1941, 2000, color=C_ERA1, ls="--", lw=2,
              label=f"1941-2000: {pr['era1_mean']:.0f} mm")
    ax.hlines(pr["era2_mean"], 2001, 2020, color=C_ERA2, ls="--", lw=2,
              label=f"2001-2020: {pr['era2_mean']:.0f} mm")
    ax.axvline(2000.5, color=C_MUTED, ls=":", lw=0.8)
    ax.set_ylabel("Annual precipitation (mm)")
    ax.set_title("New England annual precipitation, averaged over 43 long-record stations")
    ax.legend(loc="upper left", ncol=2, fontsize=8)

    hd = load("region_all_indices.csv")
    ax2.plot(hd["year"], hd["heavy_days"], color="#7b3294", lw=1, alpha=0.5)
    ax2.scatter(hd["year"], hd["heavy_days"], s=10, color="#7b3294", alpha=0.7)
    roll2 = hd.set_index("year")["heavy_days"].rolling(10, center=True, min_periods=6).mean()
    ax2.plot(roll2.index, roll2.values, color=C_INK, lw=2)
    ax2.set_ylabel("Days/yr")
    ax2.set_title("Days with ≥ 25.4 mm (1 inch) of precipitation")
    ax2.set_xlim(1940, 2021)

    fig.tight_layout()
    save(fig, "fig5_precipitation.png")


def fig_station_map() -> None:
    st = load("station_trends.csv")
    fig, ax = plt.subplots(figsize=(8.2, 7))

    vmax = float(np.nanpercentile(np.abs(st["slope_per_decade"]), 95))
    sc = ax.scatter(
        st["lon"], st["lat"], c=st["slope_per_decade"],
        cmap="RdBu_r", vmin=-vmax, vmax=vmax, s=70,
        edgecolor="#222", linewidth=0.5, zorder=3,
    )
    for _, row in st.iterrows():
        ax.annotate(row["name"].title(), (row["lon"], row["lat"]),
                    xytext=(4, 3), textcoords="offset points",
                    fontsize=6.5, color="#333")
    cb = fig.colorbar(sc, ax=ax, shrink=0.75, pad=0.02)
    cb.set_label("Temperature trend (°C per decade), 1941-2020")

    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_title("Station warming trends across New England")
    ax.set_aspect(1 / np.cos(np.deg2rad(44)))
    ax.grid(color="#e5e7eb")
    ax.text(0.01, 0.01, "Bubble size fixed; labels = station name",
            transform=ax.transAxes, fontsize=7, color=C_MUTED)

    fig.tight_layout()
    save(fig, "fig6_station_map.png")


def fig_decade_boxplot() -> None:
    sd = load("station_annual.csv").dropna(subset=["tavg_anom"])
    sd["decade"] = (sd["year"] // 10) * 10
    ok = sd.groupby("decade")["year"].nunique()
    keep = ok[ok >= 5].index
    data = [sd.loc[sd["decade"] == d, "tavg_anom"].dropna().values for d in keep]
    labels = [f"{d}s" for d in keep]

    fig, ax = plt.subplots(figsize=(8.5, 5))
    bp = ax.boxplot(data, tick_labels=labels, patch_artist=True, widths=0.6,
                    medianprops=dict(color="#111", lw=1.6),
                    flierprops=dict(marker="o", ms=3, alpha=0.4))
    for patch, d in zip(bp["boxes"], keep):
        patch.set_facecolor(C_ERA2 if d >= 2000 else C_ERA1)
        patch.set_alpha(0.55)
    ax.axhline(0, color=C_MUTED, lw=0.8)
    ax.set_ylabel("Annual mean temperature anomaly (°C)")
    ax.set_title("Distribution of station-year temperature anomalies by decade")
    ax.set_xlabel("Decade")

    fig.tight_layout()
    save(fig, "fig7_decade_boxplot.png")


def main() -> None:
    print("Writing figures ...")
    fig_temperature_timeseries()
    fig_seasonal_cycle()
    fig_station_deltas()
    fig_extremes()
    fig_precipitation()
    fig_station_map()
    fig_decade_boxplot()


if __name__ == "__main__":
    main()
