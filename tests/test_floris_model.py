"""
tests/test_floris_model.py
==========================
Verify load_floris_model() and compute_aep() work correctly.

Pass conditions:
  - FlorisModel loads without error from gch.yaml
  - compute_aep() returns a positive float for any valid layout
  - compute_aep() is consistent when called twice with the same inputs
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

from wind_farm.config import CONFIG_GCH, WIND_ROSE_CSV, ROTOR_DIAMETER
from wind_farm.wind_data import load_wind_rose
from wind_farm.layouts import build_rowmajor_layout
from wind_farm.optimization import load_floris_model, compute_aep


def test_load_floris_model() -> None:
    fm = load_floris_model(CONFIG_GCH)
    assert fm is not None, "load_floris_model returned None"
    print("PASS  test_load_floris_model")


def test_compute_aep_positive() -> None:
    fm = load_floris_model(CONFIG_GCH)
    wind_rose = load_wind_rose(WIND_ROSE_CSV)[0]
    layout_x, layout_y = build_rowmajor_layout(6, rotor_diameter=ROTOR_DIAMETER)

    aep = compute_aep(fm, wind_rose, layout_x, layout_y)

    assert isinstance(aep, float), f"Expected float, got {type(aep)}"
    assert aep > 0, f"AEP should be positive, got {aep}"
    print(f"PASS  test_compute_aep_positive  (AEP={aep:.3f} GWh)")


def test_compute_aep_consistent() -> None:
    wind_rose = load_wind_rose(WIND_ROSE_CSV)[0]
    layout_x, layout_y = build_rowmajor_layout(6, rotor_diameter=ROTOR_DIAMETER)

    fm1 = load_floris_model(CONFIG_GCH)
    aep1 = compute_aep(fm1, wind_rose, layout_x, layout_y)

    fm2 = load_floris_model(CONFIG_GCH)
    aep2 = compute_aep(fm2, wind_rose, layout_x, layout_y)

    assert abs(aep1 - aep2) < 1e-6, (
        f"compute_aep not consistent: {aep1:.6f} vs {aep2:.6f}"
    )
    print(f"PASS  test_compute_aep_consistent  ({aep1:.6f} == {aep2:.6f})")


if __name__ == "__main__":
    test_load_floris_model()
    test_compute_aep_positive()
    test_compute_aep_consistent()
    print("\nAll tests passed.")
