"""
wind_farm/wind_data.py
======================
Wind rose loading utilities.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.interpolate import griddata


def load_wind_rose(
    csv_path: Path,
    ti: float = 0.06,
) -> tuple:
    """Load a wind rose CSV and return a FLORIS WindRose plus raw arrays.

    The CSV must contain columns: wind_direction, wind_speed, frequency.
    Frequencies are normalised to sum to 1.0 before building the WindRose.

    Args:
        csv_path: Path to the wind rose CSV file.
        ti:       Turbulence intensity scalar applied to all bins.

    Returns:
        Tuple of (wind_rose, wind_directions, wind_speeds, freq_table) where:
          - wind_rose:       floris.WindRose instance
          - wind_directions: sorted 1-D float64 array, shape (n_wd,)
          - wind_speeds:     sorted 1-D float64 array, shape (n_ws,)
          - freq_table:      normalised 2-D array, shape (n_wd, n_ws)

    Raises:
        ValueError: If required columns are missing.
        FileNotFoundError: If csv_path does not exist.
    """
    from floris import WindRose

    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Wind rose CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)
    required = {"wind_direction", "wind_speed", "frequency"}
    if not required.issubset(df.columns):
        raise ValueError(
            f"wind_rose.csv must contain columns: {required}. "
            f"Found: {set(df.columns)}"
        )

    wind_directions = np.sort(df["wind_direction"].unique()).astype(float)
    wind_speeds     = np.sort(df["wind_speed"].unique()).astype(float)

    # Build frequency table using pivot instead of iterrows
    freq_table = (
        df.pivot_table(
            index="wind_direction",
            columns="wind_speed",
            values="frequency",
            aggfunc="sum",
            fill_value=0.0,
        )
        .reindex(index=wind_directions, columns=wind_speeds, fill_value=0.0)
        .to_numpy(dtype=float)
    )

    # Interpolate to evenly spaced grid for FLORIS compatibility
    target_dirs = np.arange(0, 360, 30)  # 0, 30, 60, ..., 330
    target_speeds = np.arange(5, 11, 1)  # 5, 6, 7, 8, 9, 10

    # Create mesh for current grid
    dirs_mesh, speeds_mesh = np.meshgrid(wind_directions, wind_speeds, indexing='ij')
    points = np.column_stack([dirs_mesh.flatten(), speeds_mesh.flatten()])
    values = freq_table.flatten()

    # Target mesh
    target_dirs_mesh, target_speeds_mesh = np.meshgrid(target_dirs, target_speeds, indexing='ij')

    # Interpolate
    interpolated = griddata(points, values, (target_dirs_mesh, target_speeds_mesh), method='linear', fill_value=0.0)

    # Clip negative values to 0
    interpolated = np.clip(interpolated, 0.0, None)

    # Update to interpolated grid
    wind_directions = target_dirs
    wind_speeds = target_speeds
    freq_table = interpolated

    total = freq_table.sum()
    if total > 0:
        freq_table /= total

    wind_rose = WindRose(
        wind_directions=wind_directions,
        wind_speeds=wind_speeds,
        freq_table=freq_table,
        ti_table=ti,
    )
    return wind_rose, wind_directions, wind_speeds, freq_table
