"""
tests/test_yaw_opt.py
=====================
Verify YawOptimizationScipy returns valid angles and improves farm power.

Uses a small 4-turbine layout at the dominant wind direction (270°).

Pass conditions:
  - All yaw angles are within [-25°, 25°]
  - Farm power with optimised yaw >= farm power without yaw
  - Yaw angle array has correct length (n_turbines)
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

import numpy as np

from wind_farm.config import CONFIG_GCH, ROTOR_DIAMETER, TI_DEFAULT
from wind_farm.layouts import build_rowmajor_layout
from wind_farm.optimization import load_floris_model


def test_yaw_angles_in_bounds_and_improve_power() -> None:
    from floris.optimization.yaw_optimization.yaw_optimizer_scipy import YawOptimizationScipy

    N = 4
    layout_x, layout_y = build_rowmajor_layout(N, rotor_diameter=ROTOR_DIAMETER)

    fm = load_floris_model(CONFIG_GCH)
    fm.set(
        layout_x=layout_x,
        layout_y=layout_y,
        wind_directions=[270.0],
        wind_speeds=[8.0],
        turbulence_intensities=[TI_DEFAULT],
    )

    # Baseline power (zero yaw)
    fm.run()
    power_base = fm.get_farm_power().item()

    # Yaw optimisation
    yaw_opt = YawOptimizationScipy(
        fmodel=fm,
        minimum_yaw_angle=-25.0,
        maximum_yaw_angle=25.0,
    )
    df_opt = yaw_opt.optimize()
    yaw_angles = np.array(df_opt["yaw_angles_opt"].iloc[0]).flatten()

    # Bounds
    assert len(yaw_angles) == N, f"Expected {N} yaw angles, got {len(yaw_angles)}"
    assert (yaw_angles >= -25.0 - 1e-6).all(), "Some yaw angles below -25°"
    assert (yaw_angles <= 25.0 + 1e-6).all(), "Some yaw angles above +25°"

    # Power with yaw
    fm.set(
        layout_x=layout_x,
        layout_y=layout_y,
        wind_directions=[270.0],
        wind_speeds=[8.0],
        turbulence_intensities=[TI_DEFAULT],
        yaw_angles=yaw_angles.reshape(1, -1),
    )
    fm.run()
    power_yaw = fm.get_farm_power().item()

    assert power_yaw >= power_base - 1.0, (
        f"Yaw power {power_yaw/1e3:.1f} kW < baseline {power_base/1e3:.1f} kW"
    )

    gain_pct = (power_yaw / power_base - 1) * 100
    print(f"PASS  test_yaw_angles_in_bounds_and_improve_power  "
          f"(base={power_base/1e3:.1f} kW → yaw={power_yaw/1e3:.1f} kW, {gain_pct:+.3f}%)")
    print(f"      Yaw angles: {np.round(yaw_angles, 2)}")


if __name__ == "__main__":
    test_yaw_angles_in_bounds_and_improve_power()
    print("\nAll tests passed.")
