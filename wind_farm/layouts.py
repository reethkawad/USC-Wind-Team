"""
wind_farm/layouts.py
====================
Turbine layout generators.

Three algorithms are provided — each script uses a different one and they
produce different coordinates, so do not interchange them:

  build_3x3_grid        — row-major nested loop (wake.py, yaw.py)
  build_meshgrid_layout — np.meshgrid / linspace for perfect-square N (layout.py, full.py)
  build_rowmajor_layout — rectangular fill for arbitrary N (count.py)
"""
from __future__ import annotations

import numpy as np


def build_3x3_grid(
    rotor_diameter: float = 126.0,
    spacing_d: float = 5.0,
) -> tuple[list[float], list[float]]:
    """Return (layout_x, layout_y) for a 3×3 turbine grid.

    Iterates row-major: row 0 col 0, row 0 col 1, …, row 2 col 2.

    Args:
        rotor_diameter: Turbine rotor diameter in metres.
        spacing_d:      Turbine spacing in rotor diameters.

    Returns:
        Tuple (layout_x, layout_y) of 9-element float lists.
    """
    spacing = spacing_d * rotor_diameter
    layout_x, layout_y = [], []
    for row in range(3):
        for col in range(3):
            layout_x.append(col * spacing)
            layout_y.append(row * spacing)
    return layout_x, layout_y


def build_meshgrid_layout(
    n_turbines: int = 9,
    rotor_diameter: float = 126.0,
    spacing_d: float = 5.0,
    site_size: float = 5000.0,
) -> tuple[list[float], list[float]]:
    """Create a regular-grid starting layout within site boundaries.

    Uses np.linspace + meshgrid with a one-rotor-diameter margin on all sides.

    Args:
        n_turbines:     Number of turbines (best with a perfect square).
        rotor_diameter: Rotor diameter in metres.
        spacing_d:      Spacing in rotor diameters (affects n_side derivation).
        site_size:      Side length of the square site in metres.

    Returns:
        Tuple (layout_x, layout_y).
    """
    n_side = int(np.round(np.sqrt(n_turbines)))
    margin = rotor_diameter
    xs = np.linspace(margin, site_size - margin, n_side)
    ys = np.linspace(margin, site_size - margin, n_side)
    xx, yy = np.meshgrid(xs, ys)
    return xx.flatten().tolist(), yy.flatten().tolist()


def build_rowmajor_layout(
    n: int,
    site_size: float = 5000.0,
    rotor_diameter: float = 126.0,
) -> tuple[list[float], list[float]]:
    """Place N turbines on a near-square rectangular grid inside the site.

    Fills columns left-to-right, rows bottom-to-top, clipping to exactly n
    turbines. Handles non-square turbine counts.

    Args:
        n:             Number of turbines.
        site_size:     Side length of the square site in metres.
        rotor_diameter: Rotor diameter in metres (used for margin).

    Returns:
        Tuple (layout_x, layout_y).
    """
    n_cols = int(np.ceil(np.sqrt(n)))
    n_rows = int(np.ceil(n / n_cols))

    margin = rotor_diameter
    usable = site_size - 2 * margin

    xs = (
        np.linspace(margin, margin + usable, n_cols)
        if n_cols > 1
        else np.array([site_size / 2])
    )
    ys = (
        np.linspace(margin, margin + usable, n_rows)
        if n_rows > 1
        else np.array([site_size / 2])
    )

    layout_x, layout_y = [], []
    for row in range(n_rows):
        for col in range(n_cols):
            if len(layout_x) >= n:
                break
            layout_x.append(float(xs[col]))
            layout_y.append(float(ys[row]))

    return layout_x, layout_y
