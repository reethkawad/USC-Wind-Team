"""
wind_farm/optimization.py
=========================
FlorisModel factory, AEP computation, layout optimisation, and yaw optimisation.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


def load_floris_model(config_path: Path):
    """Import FlorisModel and instantiate from a YAML config file.

    Centralises the try/except ImportError pattern used in all scripts.

    Args:
        config_path: Path to a FLORIS YAML configuration file.

    Returns:
        FlorisModel instance.

    Raises:
        SystemExit: If floris is not installed.
        FileNotFoundError: If config_path does not exist.
    """
    import sys

    try:
        from floris import FlorisModel
    except ImportError as exc:
        sys.exit(f"ERROR: Could not import floris. Run: pip install floris\n{exc}")

    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    return FlorisModel(str(config_path))


def compute_aep(
    fm,
    wind_rose,
    layout_x: Optional[list] = None,
    layout_y: Optional[list] = None,
) -> float:
    """Compute AEP in GWh using a FLORIS WindRose object.

    If layout_x/layout_y are provided, sets them on fm before running.
    Otherwise uses whatever layout is already set on fm.

    Args:
        fm:        FlorisModel instance.
        wind_rose: floris.WindRose object carrying frequency data.
        layout_x:  Optional turbine x-coordinates.
        layout_y:  Optional turbine y-coordinates.

    Returns:
        AEP in GWh (float).
    """
    if layout_x is not None and layout_y is not None:
        fm.set(layout_x=layout_x, layout_y=layout_y, wind_data=wind_rose)
    else:
        fm.set(wind_data=wind_rose)
    fm.run()
    return float(fm.get_farm_AEP() / 1e9)


def run_layout_optimization(
    fm,
    wind_rose,
    layout_x_init: list,
    layout_y_init: list,
    boundaries: list,
    min_spacing_d: float = 2.0,
    rotor_diameter: float = 126.0,
    maxiter: int = 100,
    ftol: float = 1e-6,
) -> tuple[list, list]:
    """Run SciPy SLSQP layout optimisation.

    Args:
        fm:             FlorisModel instance (mutated by optimizer).
        wind_rose:      floris.WindRose for AEP objective.
        layout_x_init:  Starting x-coordinates.
        layout_y_init:  Starting y-coordinates.
        boundaries:     List of (x, y) tuples defining site polygon vertices.
        min_spacing_d:  Minimum turbine spacing in rotor diameters.
        rotor_diameter: Rotor diameter in metres.
        maxiter:        Maximum SLSQP iterations.
        ftol:           Function value tolerance for convergence.

    Returns:
        Tuple (layout_x_opt, layout_y_opt) of optimised coordinates.
    """
    from floris.optimization.layout_optimization.layout_optimization_scipy import (
        LayoutOptimizationScipy,
    )

    fm.set(
        layout_x=layout_x_init,
        layout_y=layout_y_init,
        wind_data=wind_rose,
    )

    layout_opt = LayoutOptimizationScipy(
        fmodel=fm,
        boundaries=boundaries,
        min_dist=min_spacing_d * rotor_diameter,
        optOptions={"maxiter": maxiter, "ftol": ftol},
    )
    layout_opt.optimize()

    return (
        layout_opt.fmodel.layout_x.tolist(),
        layout_opt.fmodel.layout_y.tolist(),
    )


def compute_per_turbine_aep(
    fm,
    layout_x: list,
    layout_y: list,
    wind_directions: np.ndarray,
    wind_speeds: np.ndarray,
    freq_table: np.ndarray,
    ti: float = 0.06,
) -> np.ndarray:
    """Compute per-turbine AEP in GWh by integrating over the full wind rose.

    Uses the same freq * 8760 * power formula as get_farm_AEP() internally,
    but accumulates per-turbine instead of farm-total.

    Args:
        fm:              FlorisModel instance.
        layout_x/y:      Turbine coordinates.
        wind_directions: 1-D array from load_wind_rose.
        wind_speeds:     1-D array from load_wind_rose.
        freq_table:      Normalised 2-D array from load_wind_rose, shape (n_wd, n_ws).
        ti:              Turbulence intensity.

    Returns:
        1-D float64 array of shape (n_turbines,) in GWh/year.
    """
    n_turbines = len(layout_x)
    turbine_aep_wh = np.zeros(n_turbines)

    for i, wd in enumerate(wind_directions):
        for j, ws in enumerate(wind_speeds):
            freq = freq_table[i, j]
            if freq <= 0:
                continue
            fm.set(
                layout_x=layout_x,
                layout_y=layout_y,
                wind_directions=[float(wd)],
                wind_speeds=[float(ws)],
                turbulence_intensities=[ti],
            )
            fm.run()
            turbine_powers = fm.get_turbine_powers().flatten()
            turbine_aep_wh += turbine_powers * freq * 8760.0

    return turbine_aep_wh / 1e9  # GWh/year


def compute_aep_with_yaw(
    fm,
    layout_x: list,
    layout_y: list,
    wind_rose,
    wind_directions: np.ndarray,
    wind_speeds: np.ndarray,
    freq_table: np.ndarray,
    top_n_dirs: int = 2,
    wind_speed_yaw: float = 8.0,
    ti: float = 0.06,
) -> tuple[float, pd.DataFrame]:
    """Compute AEP after per-direction yaw optimisation.

    The top_n_dirs most frequent directions are yaw-optimised at wind_speed_yaw.
    Remaining directions use zero yaw. AEP is then computed by manually sweeping
    all (wd, ws) bins with the normalised freq_table from load_wind_rose, which
    is mathematically equivalent to fm.get_farm_AEP() for the zero-yaw case.
    The manual sweep is needed here because FLORIS WindRose does not support
    per-direction yaw overrides natively.

    Args:
        fm:              FlorisModel instance.
        layout_x/y:      Turbine coordinates.
        wind_rose:       floris.WindRose object (used for yaw opt runs).
        wind_directions: 1-D array from load_wind_rose.
        wind_speeds:     1-D array from load_wind_rose.
        freq_table:      Normalised 2-D array from load_wind_rose.
        top_n_dirs:      Number of highest-frequency directions to yaw-optimise.
        wind_speed_yaw:  Representative wind speed for yaw optimisation runs.
        ti:              Turbulence intensity.

    Returns:
        Tuple (aep_gwh: float, yaw_df: pd.DataFrame) where yaw_df has
        columns ["wind_direction", "yaw_angles"].
    """
    from floris.optimization.yaw_optimization.yaw_optimizer_scipy import (
        YawOptimizationScipy,
    )

    n_turbines = len(layout_x)

    # Identify top-N directions by summed frequency
    dir_freqs = freq_table.sum(axis=1)
    top_indices = np.argsort(dir_freqs)[-top_n_dirs:][::-1]
    top_dirs = wind_directions[top_indices]

    # Optimise yaw for top directions
    yaw_map: dict[float, np.ndarray] = {}
    rows = []
    for wd in top_dirs:
        fm.set(
            layout_x=layout_x,
            layout_y=layout_y,
            wind_directions=[float(wd)],
            wind_speeds=[wind_speed_yaw],
            turbulence_intensities=[ti],
        )
        yaw_opt = YawOptimizationScipy(
            fmodel=fm,
            minimum_yaw_angle=-25.0,
            maximum_yaw_angle=25.0,
        )
        df_opt = yaw_opt.optimize()
        yaw_angles = np.array(df_opt["yaw_angles_opt"].iloc[0]).flatten()
        yaw_map[float(wd)] = yaw_angles
        rows.append({"wind_direction": wd, "yaw_angles": yaw_angles.tolist()})

    yaw_df = pd.DataFrame(rows)

    # AEP sweep applying optimised yaw where available, zero elsewhere.
    # Uses freq * 8760 * power — same math as fm.get_farm_AEP() internally.
    total_aep_wh = 0.0
    for i, wd in enumerate(wind_directions):
        yaw_angles = yaw_map.get(float(wd), np.zeros(n_turbines))
        for j, ws in enumerate(wind_speeds):
            freq = freq_table[i, j]
            if freq <= 0:
                continue
            fm.set(
                layout_x=layout_x,
                layout_y=layout_y,
                wind_directions=[float(wd)],
                wind_speeds=[float(ws)],
                turbulence_intensities=[ti],
                yaw_angles=yaw_angles.reshape(1, -1),
            )
            fm.run()
            farm_power = fm.get_farm_power().item()
            total_aep_wh += farm_power * freq * 8760.0

    aep_gwh = total_aep_wh / 1e9
    return aep_gwh, yaw_df
