"""
layout.py
=========
Optimise turbine layout for maximum AEP over a 5 km × 5 km site using
the FLORIS Gauss-Curl Hybrid (GCH) wake model and SciPy SLSQP.

Outputs (saved to outputs/):
  - layout_comparison.png         : initial vs optimised layout overlay
  - layout_optimised_coords.csv   : final turbine (x, y) co-ordinates
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

import pandas as pd

from wind_farm.config import (
    CONFIG_GCH as CONFIG_PATH, WIND_ROSE_CSV, OUTPUT_DIR, ROTOR_DIAMETER,
    SITE_SIZE_M, N_TURBINES,
)
from wind_farm.wind_data import load_wind_rose
from wind_farm.layouts import build_meshgrid_layout
from wind_farm.optimization import load_floris_model, compute_aep, run_layout_optimization
from wind_farm.plotting import plot_layout_comparison

BOUNDARIES: list[tuple[float, float]] = [
    (0.0, 0.0),
    (SITE_SIZE_M, 0.0),
    (SITE_SIZE_M, SITE_SIZE_M),
    (0.0, SITE_SIZE_M),
]


def run() -> None:
    """Entry point: load inputs, run layout optimisation, save results."""
    print("=" * 60)
    print("Layout Optimisation")
    print("=" * 60)

    print("\n[1/4] Loading wind rose …")
    wind_rose, wind_directions, wind_speeds, _ = load_wind_rose(WIND_ROSE_CSV)
    n_wd = len(wind_directions)
    n_ws = len(wind_speeds)
    print(f"      {n_wd} directions × {n_ws} speeds = {n_wd * n_ws} wind cases")

    print("\n[2/4] Building initial layout …")
    fm = load_floris_model(CONFIG_PATH)
    layout_x_init, layout_y_init = build_meshgrid_layout(
        n_turbines=N_TURBINES, rotor_diameter=ROTOR_DIAMETER, spacing_d=5.0, site_size=SITE_SIZE_M
    )
    print(f"      {len(layout_x_init)} turbines in 3×3 grid")

    aep_init = compute_aep(fm, wind_rose, layout_x_init, layout_y_init)
    print(f"      Baseline AEP: {aep_init:.2f} GWh")

    print("\n[3/4] Running layout optimisation (SLSQP, max 100 iterations) …")
    print("      This may take several minutes …")

    t0 = time.perf_counter()
    layout_x_opt, layout_y_opt = run_layout_optimization(
        fm, wind_rose, layout_x_init, layout_y_init, BOUNDARIES,
        min_spacing_d=2.0, rotor_diameter=ROTOR_DIAMETER,
    )
    elapsed = time.perf_counter() - t0
    print(f"      Optimisation complete in {elapsed:.1f} s")

    # Evaluate optimised AEP on a fresh model to avoid state contamination
    fm_opt = load_floris_model(CONFIG_PATH)
    aep_opt = compute_aep(fm_opt, wind_rose, layout_x_opt, layout_y_opt)
    print(f"      Optimised AEP:  {aep_opt:.2f} GWh")
    print(f"      AEP gain:       {aep_opt - aep_init:+.2f} GWh "
          f"({(aep_opt / aep_init - 1) * 100:+.1f}%)")

    print("\n[4/4] Saving outputs …")

    plot_layout_comparison(
        layout_x_init, layout_y_init,
        layout_x_opt, layout_y_opt,
        rotor_diameter=ROTOR_DIAMETER,
        site_size=SITE_SIZE_M,
        aep_init_gwh=aep_init,
        aep_opt_gwh=aep_opt,
        output_path=OUTPUT_DIR / "layout_comparison.png",
        title="Layout Optimisation — 9 Turbines, 5 km × 5 km Site",
    )

    coords_df = pd.DataFrame({"x_m": layout_x_opt, "y_m": layout_y_opt})
    coords_csv = OUTPUT_DIR / "layout_optimised_coords.csv"
    coords_df.to_csv(coords_csv, index=False)
    print(f"  Saved: {coords_csv}")

    print("\nSummary")
    print(f"  Baseline AEP : {aep_init:.2f} GWh")
    print(f"  Optimised AEP: {aep_opt:.2f} GWh")
    print(f"  Gain         : {aep_opt - aep_init:+.2f} GWh ({(aep_opt / aep_init - 1) * 100:+.1f}%)")
    print("\nDone. Outputs written to:", OUTPUT_DIR)


if __name__ == "__main__":
    run()
