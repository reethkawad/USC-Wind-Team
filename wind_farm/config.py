"""
wind_farm/config.py
===================
Centralised path resolution and project-wide physical constants.

All paths are derived from this file's location so the package works
regardless of the current working directory when scripts are invoked.
"""
from __future__ import annotations
from pathlib import Path

# ---------------------------------------------------------------------------
# Root directories
# ---------------------------------------------------------------------------
PACKAGE_DIR: Path = Path(__file__).resolve().parent       # .../wind_farm/
PROJECT_DIR: Path = PACKAGE_DIR.parent                    # .../wind_farm_project/

# ---------------------------------------------------------------------------
# Input paths
# ---------------------------------------------------------------------------
CONFIG_DIR: Path    = PROJECT_DIR / "configs"
CONFIG_GCH: Path    = CONFIG_DIR / "gch.yaml"
CONFIG_JENSEN: Path = CONFIG_DIR / "jensen.yaml"
WIND_ROSE_CSV: Path = PROJECT_DIR / "data" / "wind_rose.csv"

# ---------------------------------------------------------------------------
# Output directory (created on import)
# ---------------------------------------------------------------------------
OUTPUT_DIR: Path = PROJECT_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Physical / turbine constants matching configs/turbines/nrel_5mw.yaml
# ---------------------------------------------------------------------------
ROTOR_DIAMETER: float = 126.0   # metres
HUB_HEIGHT: float     = 90.0    # metres
TI_DEFAULT: float     = 0.06    # turbulence intensity (fraction)
