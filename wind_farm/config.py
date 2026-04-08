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

# ---------------------------------------------------------------------------
# Site / campaign parameters — edit here, nowhere else
# ---------------------------------------------------------------------------
SITE_SIZE_M: float    = 5320.34  # square site side length (metres)
N_TURBINES: int       = 20       # turbines used in single-count scripts
MIN_SPACING_D: float  = 2.0     # minimum turbine spacing (rotor diameters)
WIND_SPEED_YAW: float = 8.6     # representative wind speed for yaw opt & wake viz (m/s)
N_YAW_DIRS: int       = 2       # top-frequency directions to yaw-optimise

# ---------------------------------------------------------------------------
# Yaw optimisation bounds
# ---------------------------------------------------------------------------
YAW_MIN_ANGLE: float   = -25.0   # minimum yaw misalignment (degrees)
YAW_MAX_ANGLE: float   =  25.0   # maximum yaw misalignment (degrees)

# ---------------------------------------------------------------------------
# Wake / plot rendering constants
# ---------------------------------------------------------------------------
WAKE_PLOT_X_RES: int      = 300   # horizontal plane x resolution
WAKE_PLOT_Y_RES: int      = 150   # horizontal plane y resolution
WAKE_VIZ_MIN_SPEED: float = 4.0   # colorbar floor (m/s)
WAKE_VIZ_MAX_SPEED: float = 9.0   # colorbar ceiling (m/s)
FIGURE_DPI: int           = 150   # output figure DPI

# ---------------------------------------------------------------------------
# Time constant
# ---------------------------------------------------------------------------
HOURS_PER_YEAR: float = 8760.0
