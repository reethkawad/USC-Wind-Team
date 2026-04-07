"""
tests/test_layout_opt.py
========================
Verify run_layout_optimization() improves AEP vs the initial layout.

Uses N=4, maxiter=20 for speed. This is an integration test — it runs
the actual FLORIS optimizer.

Pass conditions:
  - Optimised AEP >= initial AEP
  - Returned coordinates have correct length
  - All optimised coordinates are within site bounds
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
from wind_farm.optimization import load_floris_model, compute_aep, run_layout_optimization

SITE_SIZE = 5000.0
N = 4  # small for speed
BOUNDARIES = [(0, 0), (SITE_SIZE, 0), (SITE_SIZE, SITE_SIZE), (0, SITE_SIZE)]


def test_layout_opt_improves_aep() -> None:
    wind_rose = load_wind_rose(WIND_ROSE_CSV)[0]
    layout_x, layout_y = build_rowmajor_layout(N, rotor_diameter=ROTOR_DIAMETER)

    fm_init = load_floris_model(CONFIG_GCH)
    aep_init = compute_aep(fm_init, wind_rose, layout_x, layout_y)

    fm_opt = load_floris_model(CONFIG_GCH)
    opt_x, opt_y = run_layout_optimization(
        fm_opt, wind_rose, layout_x, layout_y, BOUNDARIES,
        min_spacing_d=2.0, rotor_diameter=ROTOR_DIAMETER, maxiter=20,
    )

    fm_eval = load_floris_model(CONFIG_GCH)
    aep_opt = compute_aep(fm_eval, wind_rose, opt_x, opt_y)

    assert len(opt_x) == N, f"Expected {N} x-coords, got {len(opt_x)}"
    assert len(opt_y) == N, f"Expected {N} y-coords, got {len(opt_y)}"

    for i, (x, y) in enumerate(zip(opt_x, opt_y)):
        assert -1 <= x <= SITE_SIZE + 1, f"Turbine {i} x={x:.1f} out of bounds"
        assert -1 <= y <= SITE_SIZE + 1, f"Turbine {i} y={y:.1f} out of bounds"

    assert aep_opt >= aep_init - 1e-3, (
        f"Optimised AEP {aep_opt:.4f} GWh < initial {aep_init:.4f} GWh"
    )

    gain = (aep_opt / aep_init - 1) * 100
    print(f"PASS  test_layout_opt_improves_aep  "
          f"({aep_init:.3f} → {aep_opt:.3f} GWh, {gain:+.2f}%)")


if __name__ == "__main__":
    test_layout_opt_improves_aep()
    print("\nAll tests passed.")
