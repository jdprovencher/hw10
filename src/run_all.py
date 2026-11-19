"""Run the whole pipeline in order."""

import subprocess
import sys
from pathlib import Path

STEPS = [
    "00_select_stations.py",
    "01_download.py",
    "02_parse.py",
    "03_analyze.py",
    "04_plots.py",
]

here = Path(__file__).resolve().parent

for step in STEPS:
    print(f"\n=== {step} ===", flush=True)
    result = subprocess.run([sys.executable, str(here / step)])
    if result.returncode != 0:
        sys.exit(f"Step {step} failed with exit code {result.returncode}")

print("\nDone. See output/REPORT.md, output/tables/ and output/figures/")
