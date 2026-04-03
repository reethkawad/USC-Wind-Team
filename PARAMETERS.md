# Parameters Reference

## Site Size
`SITE_SIZE_M` in `scripts/02_layout_optimization.py` and `scripts/04_full_analysis.py`
Default: `2000.0` metres (2 km × 2 km square). Change this to match your actual site area.

The boundary shape is also defined by `BOUNDARIES` just below it — update those corner
coordinates if your site is not a square.

---

## Wind Speed & Direction
`wind_directions`, `wind_speeds`, `turbulence_intensities` in `scripts/01_wake_visualization.py`

- **wind_directions** — compass bearing the wind comes *from* (270° = west, 0° = north)
- **wind_speeds** — hub-height wind speed in m/s
- **turbulence_intensities** — 0.06 = 6% TI; higher = faster wake recovery

For AEP calculations (scripts 02 and 04), wind conditions come from `data/wind_rose.csv`.
Replace that file with your real site data — three columns: `wind_direction`, `wind_speed`, `frequency`.
Frequencies are normalised automatically.

---

## Turbine Parameters
Turbine spec lives in `configs/turbines/nrel_5mw.yaml`.

Key values at the top of that file:

- **rotor_diameter** — `126.0` m
- **hub_height** — `90.0` m
- **power_thrust_table** — the Cp/Ct curve; replace with your turbine's actual data

If you have a manufacturer power curve, replace the `wind_speed`, `power`, and
`thrust_coefficient` lists with your values. `power` is in kW, `thrust_coefficient`
is dimensionless (0–1).

The `rotor_diameter` constant at the top of each script must match whatever you set in the YAML.

---

## Turbine Count (script 05)

`N_MIN` and `N_MAX` in `scripts/05_turbine_count_optimization.py` control the range swept.
Default: 4 to 20 turbines. The script runs a full layout optimisation for every count in that
range, then reports two things: the count with the highest total AEP, and the count with the
highest AEP-per-turbine (the point where adding another turbine stops paying off).

`MIN_SPACING_D` sets the minimum allowed gap between turbines (in rotor diameters). Default `2.0`
(252 m for the NREL 5MW). Reducing it lets the optimizer pack more turbines in but increases
wake losses.

---

## Accuracy
These settings trade off run time vs. precision.

**`turbine_grid_points`** in `configs/gch.yaml` (default `3`)
Increase to `5` for more accurate power estimates. Slower.

**`maxiter`** in scripts 02 and 04 (default `100`)
Increase for a more thoroughly optimised layout. Each extra iteration adds ~30 s.

**`N_YAW_DIRS`** in `scripts/04_full_analysis.py` (default `2`)
How many wind directions get yaw-optimised in the full pipeline.
Increase toward `36` for full accuracy; decrease to `1` for a fast test run.

**`enable_secondary_steering`** in `configs/gch.yaml` (default `true`)
Set to `false` to use simpler plain-Gaussian wake model. Faster, less accurate for yaw cases.
