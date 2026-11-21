# New England climate comparison — GHCNd

Compare daily station observations from the **last six decades of the 20th century
(1941–2000)** with the **first two decades of the 21st century (2001–2020)** across
Connecticut, Rhode Island, Massachusetts, Vermont, New Hampshire and Maine.

Full findings: **[output/REPORT.md](output/REPORT.md)**

Web report: open **[webpage/index.html](webpage/index.html)** in a browser (no server needed).

## Quick start

```powershell
python -m pip install -r requirements.txt
python src/run_all.py
```

The pipeline downloads ~167 MB of station files (cached in `data/raw/dly/`), parses them
into a 27 MB Parquet table, and writes tables + figures to `output/`.

## What it found

| | 1941–2000 | 2001–2020 | Change |
|---|---:|---:|---:|
| Annual mean temperature | 7.44 °C | 8.07 °C | **+0.62 °C** |
| Mean daily minimum | 1.62 °C | 2.51 °C | **+0.90 °C** |
| Frost days (min ≤ 0 °C) | 159.5 | 152.5 | **−7.0 d** |
| Growing season | 142.7 d | 157.3 d | **+14.7 d** |
| Annual precipitation | 1086 mm | 1206 mm | **+120 mm** |
| Heavy-precip days (≥ 25.4 mm) | 9.7 | 11.5 | **+1.8 d** |

27 temperature and 43 precipitation stations, all six states, ≥ 90 % daily completeness
per station-year, equal-weight station averages, 1961–1990 baseline.

## Layout

```
data/raw/            GHCNd metadata, version file, and per-station *.dly files
data/processed/      candidate list + parsed daily Parquet
src/00_select_stations.py
src/01_download.py
src/02_parse.py
src/03_analyze.py
src/04_plots.py
src/05_build_web.py
src/run_all.py
output/REPORT.md     the write-up
output/figures/      fig1 … fig7 (PNG)
output/tables/       all result CSVs
webpage/index.html   the web report (self-contained, opens from disk)
```

## Web report

`webpage/` is a self-contained report site built from the analysis outputs by
`src/05_build_web.py`. It copies the figures and selected CSVs into `webpage/assets/`
and writes `assets/data.js`, so the charts and tables always match the pipeline run.
No server or build step is needed — open `webpage/index.html` directly from disk.

The page includes an interactive annual temperature chart (mean / max / min / range),
decade and state tables, the full indicator comparison, robustness checks, and links to
download the underlying CSVs.

## Data source

NOAA NCEI Global Historical Climatology Network daily (GHCNd):
<https://www.ncei.noaa.gov/products/land-based-station/global-historical-climatology-network-daily>

Station files: `https://www.ncei.noaa.gov/pub/data/ghcn/daily/all/<STATION_ID>.dly`

## Notes

- GHCNd is **not homogenized**; station moves and instrument changes are not corrected.
- 2001–2020 is a 20-year sample and still contains substantial natural variability.
- Station averages are equal-weight and not area-weighted.
