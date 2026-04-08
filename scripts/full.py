"""
full.py
=======
Full pipeline: layout optimisation → yaw optimisation → AEP report.

Steps
-----
1. Load site data and wind rose
2. Optimise turbine layout for maximum AEP
3. For the optimised layout, optimise yaw angles per wind direction
4. Calculate final AEP with combined layout + yaw optimisation
5. Generate comprehensive report with summary plots

Outputs (saved to outputs/):
  - full_analysis_layout.png          : initial vs optimised layout
  - full_analysis_wind_rose.png       : wind rose polar plot
  - full_analysis_wake_optimised.png  : wake field for optimised layout at 270°
  - full_analysis_aep_breakdown.png   : AEP gain waterfall chart
  - full_analysis_report.csv          : numerical summary
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from wind_farm.config import (
    CONFIG_GCH as CONFIG_PATH, WIND_ROSE_CSV, OUTPUT_DIR,
    ROTOR_DIAMETER, TI_DEFAULT,
    SITE_SIZE_M, N_TURBINES, WIND_SPEED_YAW, N_YAW_DIRS,
    WAKE_PLOT_X_RES, WAKE_PLOT_Y_RES, WAKE_VIZ_MIN_SPEED, WAKE_VIZ_MAX_SPEED, FIGURE_DPI,
)
from wind_farm.wind_data import load_wind_rose
from wind_farm.layouts import build_meshgrid_layout
from wind_farm.optimization import (
    load_floris_model, compute_aep, run_layout_optimization, compute_aep_with_yaw,
)
from wind_farm.plotting import plot_layout_comparison, plot_wind_rose

BOUNDARIES = [
    (0.0, 0.0),
    (SITE_SIZE_M, 0.0),
    (SITE_SIZE_M, SITE_SIZE_M),
    (0.0, SITE_SIZE_M),
]


def plot_wake_optimised(fm, layout_x: list, layout_y: list, output_path: Path) -> None:
    """Wake cut plane at hub height for optimised layout at 270° / 8 m/s."""
    import floris.flow_visualization as flowviz
    import floris.layout_visualization as layoutviz

    fm.set(
        layout_x=layout_x,
        layout_y=layout_y,
        wind_directions=[270.0],
        wind_speeds=[WIND_SPEED_YAW],
        turbulence_intensities=[TI_DEFAULT],
        yaw_angles=np.zeros((1, len(layout_x))),
    )
    fm.run()
    hub_height = fm.core.farm.hub_heights.flat[0]
    hp = fm.calculate_horizontal_plane(x_resolution=WAKE_PLOT_X_RES, y_resolution=WAKE_PLOT_Y_RES, height=hub_height)

    fig, ax = plt.subplots(figsize=(12, 8))
    flowviz.visualize_cut_plane(hp, ax=ax, min_speed=WAKE_VIZ_MIN_SPEED, max_speed=WAKE_VIZ_MAX_SPEED, color_bar=True)
    layoutviz.plot_turbine_rotors(fm, ax=ax)
    farm_mw = fm.get_turbine_powers().sum() / 1e6
    ax.set_title(
        f"Wake Field — Optimised Layout, Wind 270° at {WIND_SPEED_YAW:.0f} m/s\n"
        f"Farm power = {farm_mw:.2f} MW  |  GCH Wake Model",
        fontsize=13,
    )
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {output_path}")


def plot_aep_waterfall(
    aep_init: float,
    aep_layout: float,
    aep_combined: float,
    output_path: Path,
) -> None:
    """Waterfall bar chart showing AEP progression through optimisation stages."""
    labels = ["Baseline\n(grid layout)", "After Layout\nOptimisation", "After Layout +\nYaw Optimisation"]
    values = [aep_init, aep_layout, aep_combined]
    colors = ["steelblue", "darkorange", "forestgreen"]

    fig, ax = plt.subplots(figsize=(9, 6))
    bars = ax.bar(labels, values, color=colors, width=0.45, edgecolor="white")

    for bar, val in zip(bars, values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.5,
            f"{val:.2f} GWh",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
        )

    total_gain = (aep_combined / aep_init - 1) * 100
    ax.set_ylabel("Annual Energy Production (GWh)", fontsize=11)
    ax.set_title(
        f"AEP Progression Through Optimisation\nTotal gain: {total_gain:+.1f}%",
        fontsize=13,
    )
    ax.set_ylim(0, max(values) * 1.15)
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {output_path}")


def run() -> None:
    """Full analysis pipeline."""
    print("=" * 60)
    print("Full Pipeline Analysis")
    print("=" * 60)
    t_total = time.perf_counter()

    # Step 1: Load site data and wind rose
    print("\n[1/5] Loading wind rose …")
    wind_rose, wind_directions, wind_speeds, freq_table = load_wind_rose(WIND_ROSE_CSV)
    print(f"      {len(wind_directions)} directions × {len(wind_speeds)} speeds loaded")

    plot_wind_rose(wind_directions, wind_speeds, freq_table,
                   OUTPUT_DIR / "full_analysis_wind_rose.png")

    # Step 2: Baseline AEP
    print("\n[2/5] Computing baseline AEP (3×3 grid) …")
    layout_x_init, layout_y_init = build_meshgrid_layout(
        n_turbines=N_TURBINES, rotor_diameter=ROTOR_DIAMETER, site_size=SITE_SIZE_M,
    )
    fm_base = load_floris_model(CONFIG_PATH)
    aep_init = compute_aep(fm_base, wind_rose, layout_x_init, layout_y_init)
    print(f"      Baseline AEP: {aep_init:.2f} GWh")

    # Step 3: Layout optimisation
    print("\n[3/5] Optimising layout (SLSQP, max 100 iterations) …")
    fm_layout = load_floris_model(CONFIG_PATH)
    t0 = time.perf_counter()
    layout_x_opt, layout_y_opt = run_layout_optimization(
        fm_layout, wind_rose, layout_x_init, layout_y_init, BOUNDARIES,
        min_spacing_d=2.0, rotor_diameter=ROTOR_DIAMETER,
    )
    print(f"      Layout optimisation complete in {time.perf_counter() - t0:.1f} s")

    fm_layout2 = load_floris_model(CONFIG_PATH)
    aep_layout = compute_aep(fm_layout2, wind_rose, layout_x_opt, layout_y_opt)
    print(f"      Post-layout AEP: {aep_layout:.2f} GWh  "
          f"(gain: {(aep_layout / aep_init - 1) * 100:+.1f}%)")

    plot_layout_comparison(
        layout_x_init, layout_y_init, layout_x_opt, layout_y_opt,
        rotor_diameter=ROTOR_DIAMETER,
        site_size=SITE_SIZE_M,
        aep_init_gwh=aep_init,
        aep_opt_gwh=aep_layout,
        output_path=OUTPUT_DIR / "full_analysis_layout.png",
        title="Turbine Layout: Initial vs Optimised",
        init_label="Initial (3×3 grid)",
        opt_label="Layout-optimised",
    )

    # Step 4: Yaw optimisation on optimised layout
    print(f"\n[4/5] Yaw optimisation for top-{N_YAW_DIRS} wind directions …")
    fm_yaw = load_floris_model(CONFIG_PATH)
    t0 = time.perf_counter()
    aep_combined, yaw_df = compute_aep_with_yaw(
        fm_yaw, layout_x_opt, layout_y_opt,
        wind_rose, wind_directions, wind_speeds, freq_table,
        top_n_dirs=N_YAW_DIRS,
    )
    print(f"      Yaw optimisation complete in {time.perf_counter() - t0:.1f} s")
    print(f"      Combined AEP: {aep_combined:.2f} GWh  "
          f"(gain from yaw: {(aep_combined / aep_layout - 1) * 100:+.1f}%)")

    fm_wake = load_floris_model(CONFIG_PATH)
    plot_wake_optimised(fm_wake, layout_x_opt, layout_y_opt,
                        OUTPUT_DIR / "full_analysis_wake_optimised.png")

    # Step 5: Report
    print("\n[5/5] Generating final report …")
    plot_aep_waterfall(aep_init, aep_layout, aep_combined,
                       OUTPUT_DIR / "full_analysis_aep_breakdown.png")

    total_layout_gain = aep_layout - aep_init
    total_yaw_gain = aep_combined - aep_layout
    total_gain = aep_combined - aep_init

    report = pd.DataFrame([
        {"stage": "Baseline (3x3 grid)", "AEP_GWh": round(aep_init, 3),
         "gain_GWh": 0.0, "gain_pct": 0.0},
        {"stage": "After layout optimisation", "AEP_GWh": round(aep_layout, 3),
         "gain_GWh": round(total_layout_gain, 3),
         "gain_pct": round((aep_layout / aep_init - 1) * 100, 2)},
        {"stage": "After layout + yaw optimisation", "AEP_GWh": round(aep_combined, 3),
         "gain_GWh": round(total_gain, 3),
         "gain_pct": round((aep_combined / aep_init - 1) * 100, 2)},
    ])
    csv_path = OUTPUT_DIR / "full_analysis_report.csv"
    report.to_csv(csv_path, index=False)
    print(f"  Saved: {csv_path}")

    elapsed_total = time.perf_counter() - t_total
    print("\n" + "=" * 60)
    print("FULL ANALYSIS COMPLETE")
    print("=" * 60)
    print(f"  Turbines       : {N_TURBINES}")
    print(f"  Site           : {SITE_SIZE_M / 1000:.0f} km × {SITE_SIZE_M / 1000:.0f} km")
    print(f"  Baseline AEP   : {aep_init:.2f} GWh")
    print(f"  Layout gain    : {total_layout_gain:+.2f} GWh ({(aep_layout / aep_init - 1) * 100:+.1f}%)")
    print(f"  Yaw gain       : {total_yaw_gain:+.2f} GWh ({(aep_combined / aep_layout - 1) * 100:+.1f}%)")
    print(f"  Total gain     : {total_gain:+.2f} GWh ({(aep_combined / aep_init - 1) * 100:+.1f}%)")
    print(f"  Final AEP      : {aep_combined:.2f} GWh")
    print(f"  Total runtime  : {elapsed_total:.1f} s")
    print(f"\nOutputs written to: {OUTPUT_DIR}")


if __name__ == "__main__":
    run()
