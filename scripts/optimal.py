"""
optimal.py
==========
Full optimisation pipeline for a user-specified turbine count N.

Run AFTER scripts/count.py has identified the ideal N. This script:
  1. Optimises turbine layout (SLSQP, maxiter=300) starting from row-major grid
  2. Runs wake study at the dominant wind direction → layout+wake combined plot
  3. Computes per-turbine AEP over the full wind rose
  4. Runs comprehensive yaw optimisation across all significant wind directions
  5. Produces an AEP waterfall (initial → layout opt → yaw opt) and full report

Outputs (saved to outputs/):
  optimal_layout_coords.csv        : optimised turbine (x, y)
  optimal_layout_comparison.png    : initial vs optimised layout
  optimal_wake_field.png           : hub-height wake at dominant direction
  optimal_turbine_power_bar.png    : per-turbine power at dominant direction
  optimal_layout_wake.png          : turbine rotors overlaid on wake colormap
  optimal_turbine_aep.csv          : per-turbine AEP (GWh/yr) and capacity factor
  optimal_yaw_angles.csv           : yaw angles per turbine per significant direction
  optimal_yaw_aep_comparison.png   : per-direction power gain from yaw steering
  optimal_aep_waterfall.png        : 3-stage AEP waterfall chart
  optimal_full_report.csv          : all stages, per-turbine AEP breakdown
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from wind_farm.config import (
    CONFIG_GCH as CONFIG_PATH,
    WIND_ROSE_CSV,
    OUTPUT_DIR,
    ROTOR_DIAMETER,
    HUB_HEIGHT,
    TI_DEFAULT,
)
from wind_farm.wind_data import load_wind_rose
from wind_farm.layouts import build_rowmajor_layout
from wind_farm.optimization import (
    load_floris_model,
    compute_aep,
    run_layout_optimization,
    compute_per_turbine_aep,
    compute_aep_with_yaw,
)
from wind_farm.plotting import plot_layout_comparison

# ---------------------------------------------------------------------------
# Site parameters — edit if needed
# ---------------------------------------------------------------------------
SITE_SIZE_M: float = 5000.0
MIN_SPACING_D: float = 2.0
LAYOUT_MAXITER: int = 300          # higher than count sweep (100)
YAW_FREQ_THRESHOLD: float = 0.01   # directions contributing >1% of annual hours
WAKE_WIND_DIR: float | None = None  # None → auto-detect dominant direction
WAKE_WIND_SPEED: float = 8.0       # m/s for wake/yaw visualisation
RATED_POWER_MW: float = 5.0        # NREL 5 MW

BOUNDARIES: list[tuple[float, float]] = [
    (0.0, 0.0),
    (SITE_SIZE_M, 0.0),
    (SITE_SIZE_M, SITE_SIZE_M),
    (0.0, SITE_SIZE_M),
]


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------

def _plot_wake_field(fm, title: str, output_path: Path) -> None:
    import floris.flow_visualization as flowviz
    import floris.layout_visualization as layoutviz

    hub_h = fm.core.farm.hub_heights.flat[0]
    fig, ax = plt.subplots(figsize=(12, 8))

    horizontal_plane = fm.calculate_horizontal_plane(
        x_resolution=300,
        y_resolution=150,
        height=hub_h,
    )
    flowviz.visualize_cut_plane(
        horizontal_plane, ax=ax, min_speed=4.0, max_speed=9.0, color_bar=True
    )
    layoutviz.plot_turbine_rotors(fm, ax=ax)

    ax.set_title(title, fontsize=13)
    ax.set_xlabel("x (m)", fontsize=11)
    ax.set_ylabel("y (m)", fontsize=11)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {output_path}")


def _plot_layout_wake(fm, layout_x, layout_y, title: str, output_path: Path) -> None:
    """Turbine rotor positions overlaid on hub-height wake velocity colormap."""
    import floris.flow_visualization as flowviz
    import floris.layout_visualization as layoutviz

    hub_h = fm.core.farm.hub_heights.flat[0]
    fig, ax = plt.subplots(figsize=(12, 8))

    horizontal_plane = fm.calculate_horizontal_plane(
        x_resolution=300,
        y_resolution=150,
        height=hub_h,
    )
    flowviz.visualize_cut_plane(
        horizontal_plane, ax=ax, min_speed=4.0, max_speed=9.0, color_bar=True
    )
    # Rotor circles on top of the velocity colormap
    for x, y in zip(layout_x, layout_y):
        ax.add_patch(plt.Circle(
            (x, y), ROTOR_DIAMETER / 2,
            fill=False, edgecolor="white", linewidth=2, zorder=5,
        ))
    ax.scatter(layout_x, layout_y, color="white", s=30, zorder=6)
    for i, (x, y) in enumerate(zip(layout_x, layout_y), 1):
        ax.annotate(
            f"T{i}", (x, y),
            xytext=(4, 4), textcoords="offset points",
            color="white", fontsize=7, zorder=7,
        )

    ax.set_title(title, fontsize=13)
    ax.set_xlabel("x (m)", fontsize=11)
    ax.set_ylabel("y (m)", fontsize=11)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {output_path}")


def _plot_turbine_powers(powers_kw: np.ndarray, wind_dir: float, wind_speed: float,
                         output_path: Path) -> None:
    n = len(powers_kw)
    fig, ax = plt.subplots(figsize=(max(8, n), 5))
    bars = ax.bar(range(1, n + 1), powers_kw / 1e3, color="steelblue", edgecolor="white")
    for bar, pwr in zip(bars, powers_kw):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 10,
            f"{pwr / 1e3:.2f}",
            ha="center", va="bottom", fontsize=8,
        )
    ax.set_xlabel("Turbine number", fontsize=11)
    ax.set_ylabel("Power (MW)", fontsize=11)
    ax.set_title(
        f"Per-Turbine Power — Wind from {wind_dir:.0f}° at {wind_speed:.0f} m/s",
        fontsize=13,
    )
    ax.set_xticks(range(1, n + 1))
    ax.set_ylim(0, powers_kw.max() / 1e3 * 1.25)
    total_mw = powers_kw.sum() / 1e6
    ax.text(
        0.98, 0.95, f"Farm total: {total_mw:.2f} MW",
        transform=ax.transAxes, ha="right", va="top", fontsize=10,
        bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.8),
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {output_path}")


def _plot_yaw_comparison(yaw_df: pd.DataFrame, output_path: Path) -> None:
    """Bar chart: per-direction farm power gain from yaw steering (W → MW)."""
    dirs = yaw_df["wind_direction"].values
    power_base = yaw_df["power_baseline_mw"].values
    power_yaw  = yaw_df["power_yaw_mw"].values
    gains_pct  = (power_yaw / power_base - 1) * 100

    x = np.arange(len(dirs))
    width = 0.35
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(max(10, len(dirs) * 0.5), 8),
                                   gridspec_kw={"height_ratios": [2, 1]})

    ax1.bar(x - width / 2, power_base, width, label="Baseline", color="steelblue", alpha=0.85)
    ax1.bar(x + width / 2, power_yaw,  width, label="Yaw-optimised", color="tomato", alpha=0.85)
    ax1.set_xticks(x)
    ax1.set_xticklabels([f"{d:.0f}°" for d in dirs], rotation=45, ha="right")
    ax1.set_ylabel("Farm power (MW)", fontsize=11)
    ax1.set_title("Farm Power — Baseline vs Yaw-Optimised per Wind Direction", fontsize=13)
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.3, axis="y")

    colors = ["green" if g > 0 else "gray" for g in gains_pct]
    ax2.bar(x, gains_pct, color=colors, alpha=0.85)
    ax2.axhline(0, color="black", linewidth=0.8)
    ax2.set_xticks(x)
    ax2.set_xticklabels([f"{d:.0f}°" for d in dirs], rotation=45, ha="right")
    ax2.set_ylabel("Gain (%)", fontsize=11)
    ax2.grid(True, alpha=0.3, axis="y")

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {output_path}")


def _plot_aep_waterfall(aep_init: float, aep_layout: float, aep_yaw: float,
                        output_path: Path) -> None:
    stages = ["Initial\n(row-major)", "Layout\noptimised", "Yaw\noptimised"]
    values = [aep_init, aep_layout, aep_yaw]
    deltas = [0, aep_layout - aep_init, aep_yaw - aep_layout]
    colors = ["steelblue", "tomato", "seagreen"]

    fig, ax = plt.subplots(figsize=(8, 5))
    bottoms = [0, aep_init, aep_layout]
    for i, (stage, val, delta, bottom, color) in enumerate(
        zip(stages, values, deltas, bottoms, colors)
    ):
        if i == 0:
            ax.bar(i, val, color=color, alpha=0.85, edgecolor="white")
            ax.text(i, val + 0.05, f"{val:.2f} GWh", ha="center", va="bottom", fontsize=9)
        else:
            ax.bar(i, val, color=color, alpha=0.85, edgecolor="white")
            ax.text(i, val + 0.05, f"{val:.2f} GWh", ha="center", va="bottom", fontsize=9)
            sign = "+" if delta >= 0 else ""
            ax.text(
                i, bottom + delta / 2,
                f"{sign}{delta * 1000:.1f} MWh\n({sign}{delta / aep_init * 100:.2f}%)",
                ha="center", va="center", fontsize=8, color="white", fontweight="bold",
            )

    ax.set_xticks(range(len(stages)))
    ax.set_xticklabels(stages, fontsize=11)
    ax.set_ylabel("Annual Energy Production (GWh)", fontsize=11)
    ax.set_title("AEP Optimisation Waterfall", fontsize=13)
    ax.set_ylim(0, max(values) * 1.12)
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {output_path}")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run(n_turbines: int = 9) -> None:
    print("=" * 60)
    print(f"Optimal Pipeline — N = {n_turbines} turbines")
    print(f"  Site: {SITE_SIZE_M/1000:.1f} km × {SITE_SIZE_M/1000:.1f} km")
    print(f"  Min spacing: {MIN_SPACING_D:.0f}D = {MIN_SPACING_D * ROTOR_DIAMETER:.0f} m")
    print(f"  Layout optimiser: SLSQP, maxiter={LAYOUT_MAXITER}")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 0. Load wind rose
    # ------------------------------------------------------------------
    print("\n[0/5] Loading wind rose …")
    wind_rose, wind_directions, wind_speeds, freq_table = load_wind_rose(
        WIND_ROSE_CSV, ti=TI_DEFAULT
    )

    dir_freqs = freq_table.sum(axis=1)  # total freq per direction
    dominant_dir = float(wind_directions[np.argmax(dir_freqs)])
    wake_dir = WAKE_WIND_DIR if WAKE_WIND_DIR is not None else dominant_dir
    print(f"  Dominant wind direction: {dominant_dir:.0f}°  (used for wake study)")
    n_sig_dirs = int((dir_freqs > YAW_FREQ_THRESHOLD).sum())
    print(f"  Significant directions (>{YAW_FREQ_THRESHOLD*100:.0f}% freq): {n_sig_dirs}")

    # ------------------------------------------------------------------
    # 1. Layout optimisation
    # ------------------------------------------------------------------
    print(f"\n[1/5] Layout optimisation (maxiter={LAYOUT_MAXITER}) …")
    layout_x_init, layout_y_init = build_rowmajor_layout(
        n_turbines, site_size=SITE_SIZE_M, rotor_diameter=ROTOR_DIAMETER
    )

    fm = load_floris_model(CONFIG_PATH)
    aep_init = compute_aep(fm, wind_rose, layout_x_init, layout_y_init)
    print(f"  Initial AEP (row-major): {aep_init:.3f} GWh")

    fm2 = load_floris_model(CONFIG_PATH)
    layout_x_opt, layout_y_opt = run_layout_optimization(
        fm2, wind_rose, layout_x_init, layout_y_init, BOUNDARIES,
        min_spacing_d=MIN_SPACING_D, rotor_diameter=ROTOR_DIAMETER,
        maxiter=LAYOUT_MAXITER,
    )

    fm3 = load_floris_model(CONFIG_PATH)
    aep_layout = compute_aep(fm3, wind_rose, layout_x_opt, layout_y_opt)
    gain_layout = (aep_layout / aep_init - 1) * 100
    print(f"  Optimised AEP:           {aep_layout:.3f} GWh  ({gain_layout:+.2f}%)")

    # Save coords
    coords_csv = OUTPUT_DIR / "optimal_layout_coords.csv"
    pd.DataFrame({"turbine": range(1, n_turbines + 1),
                  "x_m": layout_x_opt,
                  "y_m": layout_y_opt}).to_csv(coords_csv, index=False)
    print(f"  Saved: {coords_csv}")

    # Layout comparison plot
    plot_layout_comparison(
        layout_x_init, layout_y_init,
        layout_x_opt, layout_y_opt,
        rotor_diameter=ROTOR_DIAMETER,
        site_size=SITE_SIZE_M,
        aep_init_gwh=aep_init,
        aep_opt_gwh=aep_layout,
        output_path=OUTPUT_DIR / "optimal_layout_comparison.png",
        title=f"Layout Optimisation — N={n_turbines} Turbines",
        init_label="Initial (row-major)",
        opt_label="Optimised",
    )

    # ------------------------------------------------------------------
    # 2. Wake study
    # ------------------------------------------------------------------
    print(f"\n[2/5] Wake study at {wake_dir:.0f}° / {WAKE_WIND_SPEED:.0f} m/s …")
    fm_wake = load_floris_model(CONFIG_PATH)
    fm_wake.set(
        layout_x=layout_x_opt,
        layout_y=layout_y_opt,
        wind_directions=[wake_dir],
        wind_speeds=[WAKE_WIND_SPEED],
        turbulence_intensities=[TI_DEFAULT],
    )
    fm_wake.run()

    turbine_powers = fm_wake.get_turbine_powers().flatten()
    farm_power_mw = turbine_powers.sum() / 1e6
    print(f"  Farm power: {farm_power_mw:.3f} MW")
    for i, p in enumerate(turbine_powers, 1):
        wake_loss = (1 - p / turbine_powers.max()) * 100
        print(f"    T{i:02d}: {p/1e3:6.1f} kW  (wake loss {wake_loss:4.1f}%)")

    _plot_wake_field(
        fm_wake,
        title=(f"Wake Field — {n_turbines} Turbines (Optimised Layout)\n"
               f"Wind from {wake_dir:.0f}° at {WAKE_WIND_SPEED:.0f} m/s | GCH model"),
        output_path=OUTPUT_DIR / "optimal_wake_field.png",
    )
    _plot_turbine_powers(
        turbine_powers, wake_dir, WAKE_WIND_SPEED,
        output_path=OUTPUT_DIR / "optimal_turbine_power_bar.png",
    )
    _plot_layout_wake(
        fm_wake, layout_x_opt, layout_y_opt,
        title=(f"Layout + Wake — {n_turbines} Turbines\n"
               f"Wind from {wake_dir:.0f}° at {WAKE_WIND_SPEED:.0f} m/s"),
        output_path=OUTPUT_DIR / "optimal_layout_wake.png",
    )

    # Per-turbine AEP (layout-optimised, no yaw)
    print("\n  Computing per-turbine AEP over full wind rose …")
    fm_pt = load_floris_model(CONFIG_PATH)
    turbine_aep_layout = compute_per_turbine_aep(
        fm_pt, layout_x_opt, layout_y_opt,
        wind_directions, wind_speeds, freq_table, ti=TI_DEFAULT,
    )
    rated_annual_gwh = RATED_POWER_MW * 8760.0 / 1e3
    capacity_factors = turbine_aep_layout / rated_annual_gwh

    turbine_aep_csv = OUTPUT_DIR / "optimal_turbine_aep.csv"
    pd.DataFrame({
        "turbine": range(1, n_turbines + 1),
        "x_m": layout_x_opt,
        "y_m": layout_y_opt,
        "aep_gwh": np.round(turbine_aep_layout, 4),
        "capacity_factor": np.round(capacity_factors, 4),
    }).to_csv(turbine_aep_csv, index=False)
    print(f"  Saved: {turbine_aep_csv}")
    print(f"  Farm AEP (sum of turbines): {turbine_aep_layout.sum():.3f} GWh")

    # ------------------------------------------------------------------
    # 3. Comprehensive yaw optimisation
    # ------------------------------------------------------------------
    print(f"\n[3/5] Yaw optimisation across {n_sig_dirs} significant directions …")

    from floris.optimization.yaw_optimization.yaw_optimizer_scipy import YawOptimizationScipy

    significant_dir_indices = np.where(dir_freqs > YAW_FREQ_THRESHOLD)[0]
    significant_dirs = wind_directions[significant_dir_indices]

    yaw_rows = []
    fm_yaw = load_floris_model(CONFIG_PATH)

    for wd in significant_dirs:
        fm_yaw.set(
            layout_x=layout_x_opt,
            layout_y=layout_y_opt,
            wind_directions=[float(wd)],
            wind_speeds=[WAKE_WIND_SPEED],
            turbulence_intensities=[TI_DEFAULT],
        )
        # Baseline power (no yaw)
        fm_yaw.run()
        power_base_mw = fm_yaw.get_farm_power().item() / 1e6

        yaw_opt = YawOptimizationScipy(
            fmodel=fm_yaw,
            minimum_yaw_angle=-25.0,
            maximum_yaw_angle=25.0,
        )
        df_opt = yaw_opt.optimize()
        yaw_angles = np.array(df_opt["yaw_angles_opt"].iloc[0]).flatten()

        # Power with optimised yaw
        fm_yaw.set(
            layout_x=layout_x_opt,
            layout_y=layout_y_opt,
            wind_directions=[float(wd)],
            wind_speeds=[WAKE_WIND_SPEED],
            turbulence_intensities=[TI_DEFAULT],
            yaw_angles=yaw_angles.reshape(1, -1),
        )
        fm_yaw.run()
        power_yaw_mw = fm_yaw.get_farm_power().item() / 1e6

        gain_pct = (power_yaw_mw / power_base_mw - 1) * 100 if power_base_mw > 0 else 0.0
        print(f"    {wd:5.0f}°  base={power_base_mw:.2f} MW  yaw={power_yaw_mw:.2f} MW  gain={gain_pct:+.2f}%")

        yaw_rows.append({
            "wind_direction": wd,
            "yaw_angles": yaw_angles.tolist(),
            "power_baseline_mw": round(power_base_mw, 4),
            "power_yaw_mw": round(power_yaw_mw, 4),
            "gain_pct": round(gain_pct, 3),
        })

    yaw_df = pd.DataFrame(yaw_rows)

    yaw_csv = OUTPUT_DIR / "optimal_yaw_angles.csv"
    yaw_export = yaw_df[["wind_direction", "yaw_angles", "power_baseline_mw",
                          "power_yaw_mw", "gain_pct"]].copy()
    yaw_export.to_csv(yaw_csv, index=False)
    print(f"  Saved: {yaw_csv}")

    _plot_yaw_comparison(yaw_df, OUTPUT_DIR / "optimal_yaw_aep_comparison.png")

    # ------------------------------------------------------------------
    # 4. Yaw AEP — manual sweep with per-direction yaw map
    # ------------------------------------------------------------------
    print("\n[4/5] Computing yaw-optimised AEP over full wind rose …")
    yaw_map = {
        float(row["wind_direction"]): np.array(row["yaw_angles"])
        for _, row in yaw_df.iterrows()
    }

    fm_aep_yaw = load_floris_model(CONFIG_PATH)
    total_aep_yaw_wh = 0.0
    for i, wd in enumerate(wind_directions):
        yaw_angles = yaw_map.get(float(wd), np.zeros(n_turbines))
        for j, ws in enumerate(wind_speeds):
            freq = freq_table[i, j]
            if freq <= 0:
                continue
            fm_aep_yaw.set(
                layout_x=layout_x_opt,
                layout_y=layout_y_opt,
                wind_directions=[float(wd)],
                wind_speeds=[float(ws)],
                turbulence_intensities=[TI_DEFAULT],
                yaw_angles=yaw_angles.reshape(1, -1),
            )
            fm_aep_yaw.run()
            total_aep_yaw_wh += fm_aep_yaw.get_farm_power().item() * freq * 8760.0

    aep_yaw = total_aep_yaw_wh / 1e9
    gain_yaw = (aep_yaw / aep_layout - 1) * 100
    print(f"  Yaw-optimised AEP: {aep_yaw:.3f} GWh  ({gain_yaw:+.3f}% vs layout-opt)")

    # ------------------------------------------------------------------
    # 5. Reports and waterfall
    # ------------------------------------------------------------------
    print("\n[5/5] Generating reports …")

    _plot_aep_waterfall(
        aep_init, aep_layout, aep_yaw,
        output_path=OUTPUT_DIR / "optimal_aep_waterfall.png",
    )

    # Full report CSV — one row per turbine
    report_df = pd.DataFrame({
        "turbine": range(1, n_turbines + 1),
        "x_m": layout_x_opt,
        "y_m": layout_y_opt,
        "aep_layout_opt_gwh": np.round(turbine_aep_layout, 4),
        "capacity_factor": np.round(capacity_factors, 4),
    })
    # Add farm-level summary rows at the bottom
    summary = pd.DataFrame({
        "turbine": ["FARM_INITIAL", "FARM_LAYOUT_OPT", "FARM_YAW_OPT"],
        "x_m": [None, None, None],
        "y_m": [None, None, None],
        "aep_layout_opt_gwh": [round(aep_init, 4), round(aep_layout, 4), round(aep_yaw, 4)],
        "capacity_factor": [None, None, None],
    })
    full_report = pd.concat([report_df, summary], ignore_index=True)
    report_csv = OUTPUT_DIR / "optimal_full_report.csv"
    full_report.to_csv(report_csv, index=False)
    print(f"  Saved: {report_csv}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  N turbines           : {n_turbines}")
    print(f"  Initial AEP          : {aep_init:.3f} GWh")
    print(f"  Layout-optimised AEP : {aep_layout:.3f} GWh  ({gain_layout:+.2f}%)")
    print(f"  Yaw-optimised AEP    : {aep_yaw:.3f} GWh  ({(aep_yaw/aep_init-1)*100:+.2f}% total)")
    print(f"  Yaw dirs optimised   : {n_sig_dirs}")
    print(f"\nOutputs written to: {OUTPUT_DIR}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Optimal wind farm pipeline")
    parser.add_argument("--n", type=int, default=9, help="Number of turbines")
    args = parser.parse_args()
    run(n_turbines=args.n)
