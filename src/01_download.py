"""
Step 1 - Download the GHCNd *.dly files for the candidate stations.

Files are cached in data/raw/dly/ so the script can be re-run cheaply.
Downloads are parallel; already-present files are skipped.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DLY = RAW / "dly"
DLY.mkdir(parents=True, exist_ok=True)

BASE = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/all"
TIMEOUT = 120
WORKERS = 8


def download_one(station_id: str, session: requests.Session) -> tuple[str, str]:
    dest = DLY / f"{station_id}.dly"
    if dest.exists() and dest.stat().st_size > 10_000:
        return station_id, "cached"

    url = f"{BASE}/{station_id}.dly"
    resp = session.get(url, timeout=TIMEOUT)
    if resp.status_code != 200:
        return station_id, f"HTTP {resp.status_code}"
    if len(resp.content) < 10_000:
        return station_id, f"suspiciously small ({len(resp.content)} bytes)"
    dest.write_bytes(resp.content)
    return station_id, f"ok ({len(resp.content) / 1e6:.1f} MB)"


def main() -> None:
    stations = pd.read_csv(ROOT / "data" / "processed" / "candidate_stations.csv")
    ids = stations["id"].tolist()

    version = requests.get(
        "https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-version.txt", timeout=30
    )
    if version.ok:
        (RAW / "ghcnd-version.txt").write_text(version.text)

    results: dict[str, str] = {}
    with requests.Session() as session:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = [pool.submit(download_one, sid, session) for sid in ids]
            for i, fut in enumerate(as_completed(futures), 1):
                sid, status = fut.result()
                results[sid] = status
                if i % 10 == 0 or i == len(ids):
                    print(f"  {i}/{len(ids)} stations processed", flush=True)

    failed = {k: v for k, v in results.items() if not (v.startswith("ok") or v == "cached")}
    print(f"\nDownloaded/cached: {len(results) - len(failed)} / {len(results)}")
    if failed:
        print("Problems:")
        for sid, status in failed.items():
            print(f"  {sid}: {status}")


if __name__ == "__main__":
    main()
