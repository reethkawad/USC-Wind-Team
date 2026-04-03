# Wind Farm Layout Optimisation

This project simulates a wind farm, finds the best positions to place turbines on a site, and figures out the best angle to point each turbine so it produces as much electricity as possible. It generates charts and reports showing you how much energy the farm could produce each year.

---

## How to Use

### Step 1 – Install Anaconda

Anaconda is a free program that lets you run Python code. If you already have it, skip to Step 2.

Download it here: https://www.anaconda.com/download

Run the installer and follow the on-screen steps. When it asks, tick "Add Anaconda to my PATH" if given the option.

---

### Step 2 – Download this project

If you downloaded a ZIP file, unzip it somewhere easy to find (like your Desktop or Documents folder).

You should end up with a folder called `wind_farm_project` that contains folders named `scripts`, `configs`, `data`, etc.

---

### Step 3 – Set up the environment

The project needs a few extra tools installed. You only need to do this once.

Double-click the file called `install.bat` inside the project folder. A black window will open and run for a few minutes. When it says "Setup complete!", close it.

If `install.bat` does not work, open the Anaconda Prompt (search for it in the Start menu) and type these commands one at a time, pressing Enter after each:

```
conda create -n floris_env python=3.10 -y
conda activate floris_env
pip install -r requirements.txt
```

---

### Step 4 – Run the project

Open the Anaconda Prompt (search for it in the Start menu). Type these two commands first to activate the project environment and go to the right folder (replace the path with wherever you saved the project):

```
conda activate floris_env
cd C:\Users\YourName\Documents\wind_farm_project
```

Then run whichever step you want using `python run.py` followed by a command name:

**See how wind wakes work** — shows how one turbine's wind shadow affects turbines behind it (~30 seconds):
```
python run.py wake
```

**Find the best turbine positions** — moves turbines around until they produce the most energy (5–20 minutes):
```
python run.py layout
```

**Find the best turbine angles** — adjusts each turbine's facing direction to reduce wake losses (2–10 minutes):
```
python run.py yaw
```

**Full analysis** — runs everything together and produces a complete report (10–30 minutes):
```
python run.py full
```

You can also run multiple steps at once, for example:
```
python run.py wake layout yaw full
```

---

### Step 5 – Find your results

Once a script finishes, open the `outputs` folder inside the project. You will find:

- `wake_field_hub_height.png` – a colour map showing how wind speed changes across the farm
- `turbine_power_bar.png` – a bar chart showing how much power each turbine produces
- `layout_comparison.png` – a side-by-side picture of the original turbine positions versus the optimised ones
- `layout_optimised_coords.csv` – a spreadsheet with the exact coordinates of the optimised turbine positions
- `yaw_power_comparison.png` – a chart showing power output before and after yaw (angle) optimisation
- `yaw_wake_deflection.png` – a colour map showing how wakes are deflected when turbines are angled
- `yaw_optimised_angles.csv` – a spreadsheet of the best angle for each turbine in each wind direction
- `full_analysis_wind_rose.png` – a circular chart showing how often the wind blows from each direction
- `full_analysis_layout.png` – the layout comparison from the full pipeline run
- `full_analysis_wake_optimised.png` – the wake field at the optimised layout
- `full_analysis_aep_breakdown.png` – a waterfall chart showing how much energy is gained at each step
- `full_analysis_report.csv` – a spreadsheet summarising the total annual energy production

---

## Changing the Parameters

You can customise the project without knowing how to code. All the key settings are described in [PARAMETERS.md](PARAMETERS.md).

The most common things to change:

**Site size** – Open `scripts/02_layout_optimization.py` in a text editor (like Notepad). Find the line that says `SITE_SIZE_M = 2000.0` and change the number to your site size in metres.

**Wind data** – Replace the file `data/wind_rose.csv` with your own wind data. It needs three columns: `wind_direction`, `wind_speed`, `frequency`. Frequencies should add up to 1.0 (the project normalises them automatically if they don't).

**Turbine type** – Open `configs/turbines/nrel_5mw.yaml` in a text editor and replace the power and thrust values with your turbine's actual data sheet figures.

**Speed vs accuracy** – In `configs/gch.yaml`, changing `turbine_grid_points` from `3` to `5` gives more accurate results but takes longer to run.

All parameters with full explanations are listed in [PARAMETERS.md](PARAMETERS.md).

---

## Project Structure

```
wind_farm_project/
├── configs/
│   ├── gch.yaml               # Wake model settings (primary)
│   ├── jensen.yaml            # Simpler wake model (for comparison)
│   └── turbines/
│       └── nrel_5mw.yaml      # Turbine specification
├── data/
│   └── wind_rose.csv          # Wind climate data
├── scripts/
│   ├── 01_wake_visualization.py
│   ├── 02_layout_optimization.py
│   ├── 03_yaw_optimization.py
│   └── 04_full_analysis.py
├── outputs/                   # Generated plots and reports (created when you run scripts)
├── install.bat                # One-click setup for Windows
├── requirements.txt           # List of Python packages needed
├── PARAMETERS.md              # Full parameter reference
└── README.md
```

---

## Technical Details

### Setup (manual)

```bash
conda create -n floris_env python=3.10 -y
conda activate floris_env
pip install -r requirements.txt
python -c "import floris; print(floris.__version__)"  # should print 4.6
```

### Wake models

**Gauss-Curl Hybrid (GCH)** — `configs/gch.yaml`

The primary model. Extends the Gaussian wake model with secondary steering and yaw-added recovery effects for more accurate wake deflection predictions.

Key parameters:
- `ka`, `kb` — wake expansion coefficients
- `enable_secondary_steering` — accounts for counter-rotating vortex pairs

**Jensen (top-hat)** — `configs/jensen.yaml`

A simpler, faster model. Less accurate for wake deflection but useful for quick estimates.

Key parameter:
- `we` — wake expansion coefficient (default 0.05)

### Turbine

NREL 5 MW Reference Turbine (`configs/turbines/nrel_5mw.yaml`):

- Rated power: 5,000 kW
- Rotor diameter: 126 m
- Hub height: 90 m
- Cut-in: 3 m/s, Rated: ~11.4 m/s, Cut-out: 25 m/s

Source: Jonkman et al. (2009), *Definition of a 5-MW Reference Wind Turbine for Offshore System Development*, NREL/TP-500-38060.

### Typical AEP results (9 turbines, 2 km × 2 km site)

- Baseline 3×3 grid: ~60–100 GWh/yr
- After layout optimisation: +3–8%
- After yaw optimisation: additional +0.5–2%

### Key FLORIS concepts

- **FlorisModel** — main interface; loads a YAML config, accepts `set()` calls to update layout/conditions, then `run()` triggers the wake calculation
- **AEP** — computed by integrating farm power over all wind condition bins, weighted by frequency, multiplied by 8760 hours/year
- **Layout optimisation** — moves turbine positions within site boundaries to maximise AEP using SciPy SLSQP with minimum-spacing constraints
- **Yaw optimisation** — tilts turbine nacelles to deflect wakes away from downstream rotors

### References

- NREL FLORIS documentation: https://nrel.github.io/floris/
- Jonkman et al. (2009): NREL 5 MW Reference Turbine definition
- King et al. (2021): Controls-oriented wake steering with GCH model
