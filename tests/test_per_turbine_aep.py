"""
tests/test_per_turbine_aep.py
=============================
Verify compute_per_turbine_aep() returns a per-turbine array that sums
to the farm total from compute_aep().

Pass conditions:
  - Returns 1-D array of length n_turbines
  - All values are positive
  - sum(per_turbine_aep) ≈ farm_total_aep (within 0.1%)
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

import numpy as np

from wind_farm.config import CONFIG_GCH, WIND_ROSE_CSV, ROTOR_DIAMETER, TI_DEFAULT
from wind_farm.wind_data import load_wind_rose
from wind_farm.layouts import build_rowmajor_layout
from wind_farm.optimization import load_floris_model, compute_aep, compute_per_turbine_aep

N = 4  # small for speed


def test_per_turbine_aep_sums_to_farm_total() -> None:
    wind_rose, wind_directions, wind_speeds, freq_table = load_wind_rose(WIND_ROSE_CSV)
    layout_x, layout_y = build_rowmajor_layout(N, rotor_diameter=ROTOR_DIAMETER)

    # Farm-level AEP via compute_aep (uses fm.get_farm_AEP() with WindRose)
    fm_farm = load_floris_model(CONFIG_GCH)
    aep_farm = compute_aep(fm_farm, wind_rose, layout_x, layout_y)

    # Per-turbine AEP via manual loop
    fm_pt = load_floris_model(CONFIG_GCH)
    turbine_aep = compute_per_turbine_aep(
        fm_pt, layout_x, layout_y,
        wind_directions, wind_speeds, freq_table, ti=TI_DEFAULT,
    )

    assert turbine_aep.shape == (N,), (
        f"Expected shape ({N},), got {turbine_aep.shape}"
    )
    assert (turbine_aep > 0).all(), "Some per-turbine AEP values are non-positive"

    aep_sum = turbine_aep.sum()
    rel_err = abs(aep_sum - aep_farm) / aep_farm

    assert rel_err < 0.001, (
        f"sum(per_turbine_aep)={aep_sum:.4f} GWh vs farm_aep={aep_farm:.4f} GWh "
        f"(rel error {rel_err*100:.3f}% > 0.1%)"
    )

    print(f"PASS  test_per_turbine_aep_sums_to_farm_total")
    print(f"      Farm AEP: {aep_farm:.4f} GWh")
    print(f"      Sum of per-turbine: {aep_sum:.4f} GWh  (error {rel_err*100:.4f}%)")
    print(f"      Per-turbine: {np.round(turbine_aep, 3)}")


if __name__ == "__main__":
    test_per_turbine_aep_sums_to_farm_total()
    print("\nAll tests passed.")
