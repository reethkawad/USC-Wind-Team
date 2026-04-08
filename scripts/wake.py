"""
wake.py
=======
Visualize wake fields for a 3x3 turbine grid using the FLORIS GCH model.

Outputs (saved to outputs/):
  - wake_field_hub_height.png  : horizontal cut plane at hub height
  - turbine_power_bar.png      : per-turbine power bar chart
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

import matplotlib.pyplot as plt
import numpy as np

from wind_farm.config import CONFIG_GCH as CONFIG_PATH, OUTPUT_DIR, ROTOR_DIAMETER, TI_DEFAULT
from wind_farm.layouts import build_3x3_grid
from wind_farm.optimization import load_floris_model


def plot_wake_field(fm, output_path: Path) -> None:
    """Compute and plot the horizontal cut plane at hub height.

    Args:
        fm: Configured and run FlorisModel instance.
        output_path: File path for the saved figure.
    """
    import floris.flow_visualization as flowviz
    import floris.layout_visualization as layoutviz

    hub_height = fm.core.farm.hub_heights.flat[0]

    fig, ax = plt.subplots(figsize=(12, 8))

    horizontal_plane = fm.calculate_horizontal_plane(
        x_resolution=300,
        y_resolution=150,
        height=hub_height,
    )

    flowviz.visualize_cut_plane(
        horizontal_plane,
        ax=ax,
        min_speed=4.0,
        max_speed=9.0,
        color_bar=True,
    )
    layoutviz.plot_turbine_rotors(fm, ax=ax)

    ax.set_title(
        f"Wake Field — 3×3 Grid, 5D Spacing, Wind from 270° at 8 m/s\n"
        f"Hub Height = {hub_height:.0f} m  |  GCH Wake Model",
        fontsize=13,
    )
    ax.set_xlabel("x (m)", fontsize=11)
    ax.set_ylabel("y (m)", fontsize=11)

    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {output_path}")


def plot_turbine_powers(powers_kw: np.ndarray, output_path: Path) -> None:
    """Bar chart of per-turbine power output.

    Args:
        powers_kw: Array of turbine powers in kW, shape (n_turbines,).
        output_path: File path for the saved figure.
    """
    n = len(powers_kw)
    fig, ax = plt.subplots(figsize=(10, 5))

    bars = ax.bar(range(1, n + 1), powers_kw / 1e3, color="steelblue", edgecolor="white")

    for bar, pwr in zip(bars, powers_kw):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 20,
            f"{pwr / 1e3:.2f} MW",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    ax.set_xlabel("Turbine number (row-major, L→R per row)", fontsize=11)
    ax.set_ylabel("Power (MW)", fontsize=11)
    ax.set_title("Per-Turbine Power — 3×3 Grid, Wind from 270° at 8 m/s", fontsize=13)
    ax.set_xticks(range(1, n + 1))
    ax.set_ylim(0, powers_kw.max() / 1e3 * 1.2)

    total_mw = powers_kw.sum() / 1e6
    ax.text(
        0.98,
        0.95,
        f"Farm total: {total_mw:.2f} MW",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=11,
        bbox=dict(boxstyle="round", facecolor="lightyellow", alpha=0.8),
    )

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {output_path}")


def run() -> None:
    """Entry point: load model, run simulation, generate plots."""
    print("=" * 60)
    print("Wake Visualisation")
    print("=" * 60)

    print("\n[1/3] Loading FlorisModel …")
    fm = load_floris_model(CONFIG_PATH)

    layout_x, layout_y = build_3x3_grid(rotor_diameter=ROTOR_DIAMETER, spacing_d=5.0)
    n_turbines = len(layout_x)
    print(f"      Layout: {n_turbines} turbines in 3×3 grid (5D spacing = 630 m)")

    fm.set(
        layout_x=layout_x,
        layout_y=layout_y,
        wind_directions=[270.0],
        wind_speeds=[8.6],
        turbulence_intensities=[TI_DEFAULT],
    )

    print("\n[2/3] Running wake model …")
    fm.run()

    turbine_powers = fm.get_turbine_powers().flatten()
    farm_power_mw = turbine_powers.sum() / 1e6

    print(f"      Farm power: {farm_power_mw:.3f} MW")
    print("      Per-turbine (kW):")
    for i, p in enumerate(turbine_powers, 1):
        wake_loss = (1 - p / turbine_powers.max()) * 100
        print(f"        T{i:02d}: {p / 1e3:6.1f} kW  (wake loss {wake_loss:4.1f}%)")

    print("\n[3/3] Generating figures …")
    plot_wake_field(fm, OUTPUT_DIR / "wake_field_hub_height.png")
    plot_turbine_powers(turbine_powers, OUTPUT_DIR / "turbine_power_bar.png")

    print("\nDone. Outputs written to:", OUTPUT_DIR)


if __name__ == "__main__":
    run()
