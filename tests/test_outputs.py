"""
tests/test_outputs.py
=====================
End-to-end smoke test: run optimal.py with N=4 (small/fast) and verify
all expected output files are created.

Pass conditions:
  - All 10 output files exist in outputs/ after the run
  - No exceptions raised during the run
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

from wind_farm.config import OUTPUT_DIR

EXPECTED_FILES = [
    "optimal_layout_coords.csv",
    "optimal_layout_comparison.png",
    "optimal_wake_field.png",
    "optimal_turbine_power_bar.png",
    "optimal_layout_wake.png",
    "optimal_turbine_aep.csv",
    "optimal_yaw_angles.csv",
    "optimal_yaw_aep_comparison.png",
    "optimal_aep_waterfall.png",
    "optimal_full_report.csv",
]


def test_outputs_exist() -> None:
    """Run the optimal pipeline with N=4 and check all output files are created."""
    # Remove any pre-existing optimal outputs so we're sure they're freshly generated
    for fname in EXPECTED_FILES:
        p = OUTPUT_DIR / fname
        if p.exists():
            p.unlink()

    from scripts.optimal import run
    run(n_turbines=4)

    missing = [f for f in EXPECTED_FILES if not (OUTPUT_DIR / f).exists()]
    assert not missing, f"Missing output files: {missing}"

    print("PASS  test_outputs_exist")
    for f in EXPECTED_FILES:
        size = (OUTPUT_DIR / f).stat().st_size
        print(f"      {f}  ({size:,} bytes)")


if __name__ == "__main__":
    test_outputs_exist()
    print("\nAll tests passed.")
