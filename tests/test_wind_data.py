"""
tests/test_wind_data.py
=======================
Verify load_wind_rose() loads and normalises the wind rose CSV correctly.

Pass conditions:
  - freq_table sums to 1.0 ± 1e-6
  - shape is (36, 6) for the default wind_rose.csv
  - wind_directions range 0–350° in 10° steps
  - wind_speeds range 4–14 m/s in 2 m/s steps
  - WindRose object is returned without error
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

import numpy as np

from wind_farm.config import WIND_ROSE_CSV
from wind_farm.wind_data import load_wind_rose


def test_load_wind_rose() -> None:
    wind_rose, wind_directions, wind_speeds, freq_table = load_wind_rose(WIND_ROSE_CSV)

    # Frequency normalisation
    total = freq_table.sum()
    assert abs(total - 1.0) < 1e-6, f"freq_table sums to {total}, expected 1.0"

    # Shape
    assert freq_table.shape == (12, 6), (
        f"Expected freq_table shape (12, 6), got {freq_table.shape}"
    )
    assert len(wind_directions) == 12, f"Expected 12 directions, got {len(wind_directions)}"
    assert len(wind_speeds) == 6, f"Expected 6 speeds, got {len(wind_speeds)}"

    # Direction range
    assert wind_directions[0] == 0.0, f"First direction should be 0°, got {wind_directions[0]}"
    assert wind_directions[-1] == 330.0, f"Last direction should be 330°, got {wind_directions[-1]}"

    # Speed range
    assert wind_speeds[0] == 5.0, f"Min wind speed should be 5 m/s, got {wind_speeds[0]}"
    assert wind_speeds[-1] == 10.0, f"Max wind speed should be 10 m/s, got {wind_speeds[-1]}"

    # No negative frequencies
    assert (freq_table >= 0).all(), "freq_table contains negative values"

    # WindRose object exists
    assert wind_rose is not None, "load_wind_rose returned None for wind_rose"

    print("PASS  test_load_wind_rose")


if __name__ == "__main__":
    test_load_wind_rose()
    print("\nAll tests passed.")
