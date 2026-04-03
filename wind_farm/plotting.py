"""
wind_farm/plotting.py
=====================
Reusable matplotlib plotting utilities for wind farm analysis.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def plot_layout_comparison(
    init_x: list,
    init_y: list,
    opt_x: list,
    opt_y: list,
    rotor_diameter: float,
    site_size: float,
    aep_init_gwh: float,
    aep_opt_gwh: float,
    output_path: Path,
    title: str = "Layout Optimisation",
    init_label: str = "Initial (grid)",
    opt_label: str = "Optimised",
) -> None:
    """Side-by-side plot of initial and optimised turbine layouts.

    Args:
        init_x/init_y:    Initial layout coordinates.
        opt_x/opt_y:      Optimised layout coordinates.
        rotor_diameter:   Rotor diameter in metres (for circle radius).
        site_size:        Side length of square site in metres.
        aep_init_gwh:     Initial AEP in GWh (shown in subplot title).
        aep_opt_gwh:      Optimised AEP in GWh (shown in subplot title).
        output_path:      Save path for the figure.
        title:            Figure suptitle prefix.
        init_label:       Label for the initial layout subplot.
        opt_label:        Label for the optimised layout subplot.
    """
    site_verts = [(0, 0), (site_size, 0), (site_size, site_size), (0, site_size)]

    fig, axes = plt.subplots(1, 2, figsize=(14, 7), sharey=True)

    for ax, xs, ys, label, aep, color in [
        (axes[0], init_x, init_y, init_label, aep_init_gwh, "steelblue"),
        (axes[1], opt_x,  opt_y,  opt_label,  aep_opt_gwh,  "tomato"),
    ]:
        ax.add_patch(plt.Polygon(
            site_verts, fill=False, edgecolor="black", linewidth=2, linestyle="--"
        ))
        for x, y in zip(xs, ys):
            ax.add_patch(plt.Circle((x, y), rotor_diameter / 2, color=color, alpha=0.5))
        ax.scatter(xs, ys, color=color, s=30, zorder=5)
        ax.set_title(f"{label}\nAEP = {aep:.2f} GWh", fontsize=12)
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
        ax.set_xlim(-100, site_size + 100)
        ax.set_ylim(-100, site_size + 100)
        ax.set_aspect("equal")
        ax.grid(True, alpha=0.3)

    gain_pct = (aep_opt_gwh / aep_init_gwh - 1) * 100 if aep_init_gwh else 0.0
    fig.suptitle(
        f"{title}\nAEP gain: {aep_opt_gwh - aep_init_gwh:.2f} GWh  ({gain_pct:+.1f}%)",
        fontsize=13,
    )
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {output_path}")


def plot_wind_rose(
    wind_directions: np.ndarray,
    wind_speeds: np.ndarray,
    freq_table: np.ndarray,
    output_path: Path,
    title: str = "Wind Rose — Site Wind Climate",
) -> None:
    """Polar wind rose plot coloured by wind speed bin.

    Args:
        wind_directions: 1-D array of directions in degrees.
        wind_speeds:     1-D array of wind speeds in m/s.
        freq_table:      2-D frequency array, shape (n_wd, n_ws).
        output_path:     Save path.
        title:           Plot title.
    """
    fig, ax = plt.subplots(subplot_kw={"projection": "polar"}, figsize=(8, 8))

    colors    = plt.cm.plasma(np.linspace(0.2, 0.9, len(wind_speeds)))
    bar_width = np.deg2rad(10.0) * 0.8
    theta     = np.deg2rad(90.0 - wind_directions)
    bottom    = np.zeros(len(wind_directions))

    for j, (ws, color) in enumerate(zip(wind_speeds, colors)):
        ax.bar(
            theta, freq_table[:, j], width=bar_width,
            bottom=bottom, color=color, alpha=0.85, label=f"{ws:.0f} m/s",
        )
        bottom += freq_table[:, j]

    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_xticks(np.deg2rad([0, 45, 90, 135, 180, 225, 270, 315]))
    ax.set_xticklabels(["N", "NE", "E", "SE", "S", "SW", "W", "NW"])
    ax.set_title(title, pad=20, fontsize=13)
    ax.legend(loc="lower left", bbox_to_anchor=(-0.15, -0.15), title="Wind speed", fontsize=9)

    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {output_path}")
