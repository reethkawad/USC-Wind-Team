"""
yaw.py
======
Optimise yaw angles for a fixed 3×3 turbine layout to maximise farm power
via wake steering across three test wind directions (260°, 270°, 280°).

Outputs (saved to outputs/):
  - yaw_power_comparison.png   : bar chart — baseline vs yaw-optimised power
  - yaw_wake_deflection.png    : wake cut planes with/without yaw for 270°
  - yaw_optimised_angles.csv   : optimised yaw angles per turbine/direction
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

from wind_farm.config import CONFIG_GCH as CONFIG_PATH, OUTPUT_DIR, ROTOR_DIAMETER, TI_DEFAULT
from wind_farm.layouts import build_3x3_grid
from wind_farm.optimization import load_floris_model

TEST_DIRECTIONS = [260.0, 270.0, 280.0]
WIND_SPEED = 8.0
SPACING_D = 5.0


def run_baseline(fm, layout_x: list, layout_y: list) -> dict[float, np.ndarray]:
    """Run the model with zero yaw for all test directions."""
    baseline_powers: dict[float, np.ndarray] = {}
    for wd in TEST_DIRECTIONS:
        fm.set(
            layout_x=layout_x,
            layout_y=layout_y,
            wind_directions=[wd],
            wind_speeds=[WIND_SPEED],
            turbulence_intensities=[TI_DEFAULT],
        )
        fm.run()
        baseline_powers[wd] = fm.get_turbine_powers().flatten()
    return baseline_powers


def run_yaw_optimisation(fm, layout_x: list, layout_y: list) -> dict[float, dict]:
    """Optimise yaw angles for each test wind direction independently."""
    from floris.optimization.yaw_optimization.yaw_optimizer_scipy import YawOptimizationScipy

    results: dict[float, dict] = {}

    for wd in TEST_DIRECTIONS:
        print(f"      Optimising yaw for wind direction {wd:.0f}° …")
        fm.set(
            layout_x=layout_x,
            layout_y=layout_y,
            wind_directions=[wd],
            wind_speeds=[WIND_SPEED],
            turbulence_intensities=[TI_DEFAULT],
        )

        yaw_opt = YawOptimizationScipy(
            fmodel=fm,
            minimum_yaw_angle=-25.0,
            maximum_yaw_angle=25.0,
        )
        df_opt = yaw_opt.optimize()

        yaw_angles = df_opt["yaw_angles_opt"].iloc[0]
        yaw_array = np.array(yaw_angles).flatten()

        fm.set(
            layout_x=layout_x,
            layout_y=layout_y,
            wind_directions=[wd],
            wind_speeds=[WIND_SPEED],
            turbulence_intensities=[TI_DEFAULT],
            yaw_angles=yaw_array.reshape(1, -1),
        )
        fm.run()
        opt_powers = fm.get_turbine_powers().flatten()

        results[wd] = {"yaw_angles": yaw_array, "powers": opt_powers}

    return results


def plot_power_comparison(
    baseline: dict[float, np.ndarray],
    optimised: dict[float, dict],
    output_path: Path,
) -> None:
    """Grouped bar chart comparing baseline vs yaw-optimised farm power."""
    directions = TEST_DIRECTIONS
    baseline_farm_mw = [baseline[wd].sum() / 1e6 for wd in directions]
    opt_farm_mw = [optimised[wd]["powers"].sum() / 1e6 for wd in directions]

    x = np.arange(len(directions))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    bars1 = ax.bar(x - width / 2, baseline_farm_mw, width, label="Baseline (no yaw)", color="steelblue")
    bars2 = ax.bar(x + width / 2, opt_farm_mw, width, label="Yaw-optimised", color="tomato")

    for b1, b2, base, opt in zip(bars1, bars2, baseline_farm_mw, opt_farm_mw):
        gain = (opt / base - 1) * 100
        ax.annotate(
            f"+{gain:.2f}%",
            xy=(b2.get_x() + b2.get_width() / 2, b2.get_height()),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            color="darkred",
        )

    ax.set_xticks(x)
    ax.set_xticklabels([f"{d:.0f}°" for d in directions], fontsize=11)
    ax.set_xlabel("Wind direction", fontsize=11)
    ax.set_ylabel("Farm power (MW)", fontsize=11)
    ax.set_title("Yaw Optimisation — Farm Power vs Wind Direction\n3×3 Grid, 8 m/s", fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {output_path}")


def plot_wake_deflection(fm, layout_x: list, layout_y: list,
                         yaw_opt: np.ndarray, output_path: Path) -> None:
    """Side-by-side wake cut planes at 270° with and without yaw steering."""
    import floris.flow_visualization as flowviz
    import floris.layout_visualization as layoutviz

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    for ax, yaw_angles, title in [
        (axes[0], np.zeros(len(layout_x)), "No Yaw (baseline)"),
        (axes[1], yaw_opt, "Yaw-Optimised"),
    ]:
        fm.set(
            layout_x=layout_x,
            layout_y=layout_y,
            wind_directions=[270.0],
            wind_speeds=[WIND_SPEED],
            turbulence_intensities=[TI_DEFAULT],
            yaw_angles=yaw_angles.reshape(1, -1),
        )
        fm.run()

        hub_height = fm.core.farm.hub_heights.flat[0]
        hp = fm.calculate_horizontal_plane(
            x_resolution=300,
            y_resolution=150,
            height=hub_height,
        )

        flowviz.visualize_cut_plane(hp, ax=ax, min_speed=4.0, max_speed=9.0, color_bar=True)
        layoutviz.plot_turbine_rotors(fm, ax=ax)

        farm_mw = fm.get_turbine_powers().sum() / 1e6
        ax.set_title(f"{title}\nFarm power = {farm_mw:.2f} MW", fontsize=11)
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")

    fig.suptitle("Wake Deflection via Yaw Steering — Wind from 270° at 8 m/s", fontsize=13)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {output_path}")


def run() -> None:
    """Entry point: load model, optimise yaw, generate plots."""
    print("=" * 60)
    print("Yaw Optimisation")
    print("=" * 60)

    layout_x, layout_y = build_3x3_grid(ROTOR_DIAMETER, SPACING_D)

    print("\n[1/4] Computing baseline power (no yaw) …")
    fm = load_floris_model(CONFIG_PATH)
    baseline_powers = run_baseline(fm, layout_x, layout_y)
    for wd, pwr in baseline_powers.items():
        print(f"      WD={wd:.0f}°: {pwr.sum() / 1e6:.3f} MW")

    print("\n[2/4] Running yaw optimisation …")
    fm2 = load_floris_model(CONFIG_PATH)
    opt_results = run_yaw_optimisation(fm2, layout_x, layout_y)

    print("\n      Results:")
    rows = []
    for wd in TEST_DIRECTIONS:
        base_mw = baseline_powers[wd].sum() / 1e6
        opt_mw = opt_results[wd]["powers"].sum() / 1e6
        gain = (opt_mw / base_mw - 1) * 100
        print(f"      WD={wd:.0f}°: baseline={base_mw:.3f} MW  opt={opt_mw:.3f} MW  gain={gain:+.2f}%")
        for t_idx, yaw_val in enumerate(opt_results[wd]["yaw_angles"]):
            rows.append({
                "wind_direction": wd,
                "turbine": t_idx + 1,
                "yaw_angle_deg": float(yaw_val),
                "baseline_power_kw": float(baseline_powers[wd][t_idx] / 1e3),
                "opt_power_kw": float(opt_results[wd]["powers"][t_idx] / 1e3),
            })

    print("\n[3/4] Generating figures …")
    fm3 = load_floris_model(CONFIG_PATH)
    plot_power_comparison(baseline_powers, opt_results, OUTPUT_DIR / "yaw_power_comparison.png")
    plot_wake_deflection(
        fm3, layout_x, layout_y,
        opt_results[270.0]["yaw_angles"],
        OUTPUT_DIR / "yaw_wake_deflection.png",
    )

    print("\n[4/4] Saving CSV …")
    df = pd.DataFrame(rows)
    csv_path = OUTPUT_DIR / "yaw_optimised_angles.csv"
    df.to_csv(csv_path, index=False)
    print(f"  Saved: {csv_path}")

    print("\nDone. Outputs written to:", OUTPUT_DIR)


if __name__ == "__main__":
    run()
