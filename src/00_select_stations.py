"""
Step 0 - Pick candidate GHCNd stations for New England.

Reads the GHCNd station metadata and inventory files and writes
data/processed/candidate_stations.csv with every station that has a
plausible long record of temperature and/or precipitation.

GHCNd fixed-width layouts
-------------------------
ghcnd-stations.txt
    ID 1-11 | LAT 13-20 | LON 22-30 | ELEV 32-37 | STATE 39-40 |
    NAME 42-71 | GSN 73-75 | HCN/CRN 77-79 | WMO 81-85

ghcnd-inventory.txt
    ID 1-11 | LAT 13-20 | LON 22-30 | ELEMENT 32-35 |
    FIRSTYEAR 37-40 | LASTYEAR 42-45
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
PROC.mkdir(parents=True, exist_ok=True)

# New England = the six states requested
STATES = {"VT", "NH", "ME", "MA", "CT", "RI"}
ELEMENTS = ["TMAX", "TMIN", "PRCP", "SNOW", "SNWD"]

# A station must at least *claim* data reaching back before the mid-1940s
# and forward past 2010 to be worth downloading. Actual completeness is
# checked after parsing, because the inventory only lists begin/end years.
FIRST_YEAR_MAX = 1946
LAST_YEAR_MIN = 2010


def read_stations(path: Path) -> pd.DataFrame:
    rows = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.startswith("US") or line[38:40].strip() not in STATES:
                continue
            rows.append(
                {
                    "id": line[0:11],
                    "lat": float(line[12:20]),
                    "lon": float(line[21:30]),
                    "elev_m": float(line[31:37]) if line[31:37].strip() else None,
                    "state": line[38:40].strip(),
                    "name": line[41:71].strip(),
                    "gsn": line[72:75].strip() or None,
                    "hcn_crn": line[76:79].strip() or None,
                }
            )
    df = pd.DataFrame(rows)
    df["name"] = df["name"].str.replace(r"\s+", " ", regex=True)
    return df


def read_inventory(path: Path) -> pd.DataFrame:
    rows = []
    with open(path) as fh:
        for line in fh:
            element = line[31:35].strip()
            if element not in ELEMENTS or not line.startswith("US"):
                continue
            rows.append(
                {
                    "id": line[0:11],
                    "element": element,
                    "first_year": int(line[36:40]),
                    "last_year": int(line[41:45]),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    stations = read_stations(RAW / "ghcnd-stations.txt")
    inventory = read_inventory(RAW / "ghcnd-inventory.txt")

    # The inventory file is global - restrict it to the New England stations
    inventory = inventory[inventory["id"].isin(stations["id"])]

    # Keep only records whose claimed span covers both study eras
    long = inventory[
        (inventory["first_year"] <= FIRST_YEAR_MAX)
        & (inventory["last_year"] >= LAST_YEAR_MIN)
    ]

    summary = (
        long.groupby("id")
        .agg(
            elements=("element", lambda s: ",".join(sorted(set(s)))),
            first_year=("first_year", "min"),
            last_year=("last_year", "max"),
        )
        .reset_index()
    )

    out = summary.merge(stations, on="id", how="left")
    out["has_temp"] = out["elements"].str.contains("TMAX") & out[
        "elements"
    ].str.contains("TMIN")
    out["has_precip"] = out["elements"].str.contains("PRCP")
    out = out.sort_values(["state", "name"]).reset_index(drop=True)

    out.to_csv(PROC / "candidate_stations.csv", index=False)

    print(f"New England stations in metadata : {len(stations)}")
    print(f"Long-record candidates          : {len(out)}")
    print(f"  with TMAX+TMIN                : {int(out['has_temp'].sum())}")
    print(f"  with PRCP                     : {int(out['has_precip'].sum())}")
    print(f"  with all three                : {int((out['has_temp'] & out['has_precip']).sum())}")
    print("\nCandidates per state:")
    print(out.groupby("state").size().to_string())
    print("\nFirst 15 candidates:")
    print(out.head(15)[["id", "state", "name", "first_year", "last_year", "elements"]].to_string(index=False))


if __name__ == "__main__":
    main()
