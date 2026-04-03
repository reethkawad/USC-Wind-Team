# Wind Farm Optimization Pipeline — Technical Logic

**Framework:** FLORIS v4.6 (NREL) · **Optimizer:** SciPy SLSQP · **Turbine:** NREL 5MW Reference

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Inputs](#2-system-inputs)
3. [Turbine Physics](#3-turbine-physics)
4. [Wake Modeling](#4-wake-modeling)
5. [AEP Calculation](#5-aep-calculation)
6. [Layout Optimization](#6-layout-optimization)
7. [Yaw Optimization](#7-yaw-optimization)
8. [Combined Pipeline — Script 04](#8-combined-pipeline--script-04)
9. [Turbine Count Sweep — Script 05](#9-turbine-count-sweep--script-05)
10. [Results Summary](#10-results-summary)
11. [Configuration Reference](#11-configuration-reference)

---

## 1. Project Overview

This pipeline finds the maximum Annual Energy Production (AEP) for a wind farm by solving two coupled optimization problems:

1. **Where to place turbines** — layout optimization on a 5 km × 5 km site
2. **How to point turbines** — yaw angle optimization (wake steering) per wind direction

The physics engine is FLORIS, a steady-state wake model solver developed by NREL. Every decision — turbine spacing, yaw angle, number of turbines — flows through FLORIS's wake calculations to produce a power estimate, which is then integrated over a wind climate to give AEP.

**End-to-end data flow:**

```
Wind Rose (freq table)
        +
Turbine Specs (Cp, Ct curves)       ──►  FLORIS Wake Solver
        +                                        │
Site Boundary (5 km × 5 km)                      ▼
                                        Farm Power P(wd, ws)
                                                 │
                                                 ▼
                          Layout Optimizer (SLSQP) ──► Optimized x,y coords
                                                 │
                                                 ▼
                          Yaw Optimizer (SLSQP)  ──► Optimized γ map
                                                 │
                                                 ▼
                                    AEP = Σ P × freq × 8760
```

---

## 2. System Inputs

### 2.1 Site

| Parameter         | Value              |
|-------------------|--------------------|
| Site dimensions   | 5,000 m × 5,000 m  |
| Turbine count     | 9 (configurable)   |
| Min. spacing      | 2D = 252 m         |
| Initial layout    | 3×3 grid, 630 m (5D) spacing |

### 2.2 NREL 5MW Reference Turbine

| Parameter          | Value     |
|--------------------|-----------|
| Rated power        | 5,000 kW  |
| Rotor diameter (D) | 126 m     |
| Hub height         | 90 m      |
| Swept area (A)     | 12,469 m² |
| Tip-speed ratio    | 8.0       |
| Cut-in speed       | 3 m/s     |
| Rated speed        | ~11.4 m/s |
| Cut-out speed      | 25 m/s    |

### 2.3 Wind Rose

Stored in `data/wind_rose.csv`:

- **36 wind directions:** 0°–350° in 10° bins
- **6 wind speeds:** 4, 6, 8, 10, 12, 14 m/s
- **216 total bins,** frequency values normalized to sum = 1.0
- The site is **westerly-dominant:** wind direction 270° carries the highest frequencies

---

## 3. Turbine Physics

### 3.1 Rotor Power Equation

The mechanical power extracted from the wind by a turbine rotor is:

```
P = 0.5 × ρ × A × v³ × Cp(v)
```

Where:
- `ρ` = air density = 1.225 kg/m³
- `A` = rotor swept area = π(D/2)² = π(63)² ≈ 12,469 m²
- `v` = local wind speed at the rotor hub (m/s)
- `Cp(v)` = power coefficient — a non-dimensional efficiency from the turbine's look-up table

The theoretical maximum Cp for any rotor is **16/27 ≈ 0.593** (Betz limit). Real turbines operate below this.

### 3.2 Thrust Force

The rotor also exerts a drag force on the airflow (thrust), which creates the velocity deficit (wake) downstream:

```
T = 0.5 × ρ × A × v² × Ct(v)
```

Where `Ct(v)` is the **thrust coefficient** — also from a look-up table, distinct from Cp.

### 3.3 NREL 5MW Cp and Ct Curves

The turbine's `power_thrust_table` in `nrel_5mw.yaml` gives Cp and Ct as a function of wind speed:

| Wind Speed (m/s) | Power (kW) | Ct    | Operating Region |
|-----------------|------------|-------|------------------|
| 3.0             | 40         | ~0.82 | Below rated      |
| 8.0             | ~1,750     | ~0.79 | Below rated      |
| 11.4            | 5,000      | ~0.48 | At rated         |
| 15.0            | 5,000      | ~0.24 | Above rated      |
| 25.0            | 5,000      | ~0.10 | Near cut-out     |
| 25.01+          | 0          | 0     | Cut-out          |

**Key insight:** Ct is highest at low speeds (~0.82 near cut-in) and decreases above rated speed. A high Ct means more energy extracted from the wind — but also a stronger, longer wake downstream.

### 3.4 Turbine Grid Discretization

FLORIS does not treat the rotor as a point; it samples the velocity field on a **3×3 grid** of points across the rotor disk. Power is computed by averaging these 9 sampled velocities, then applying the Cp look-up. This captures the non-uniform velocity profile across the rotor when it is partly inside a wake.

```
Solver setting: turbine_grid_points = 3  →  3×3 = 9 sample points per rotor
```

---

## 4. Wake Modeling

A wind turbine extracts kinetic energy from the flow, leaving a **wake** — a region of reduced wind speed — downstream. Turbines positioned inside these wakes produce less power. Accurately modeling wakes is the core challenge of wind farm optimization.

FLORIS implements two models for comparison:

---

### 4.1 Gauss-Curl Hybrid (GCH) — Primary Model

**Config:** `configs/gch.yaml`

GCH is a high-fidelity analytical model that describes the wake velocity deficit as a **Gaussian (bell-shaped) profile** in the cross-stream plane.

#### Velocity Deficit Equation

At a downstream distance `x` and radial offset `r` from the wake centreline:

```
u_deficit(r, x) = Δu_max(x) × exp( -(r / σ(x))² )
```

Where:
- `Δu_max(x)` = centreline velocity deficit (maximum depth of the wake)
- `σ(x)` = wake width parameter (standard deviation of the Gaussian)

#### Wake Expansion

The wake widens as it travels downstream. σ grows linearly with distance:

```
σ(x) = ka × x + kb × D
```

FLORIS parameters from `gch.yaml`:

| Parameter | Value | Role |
|-----------|-------|------|
| `ka`      | 0.38  | Far-wake lateral expansion rate |
| `kb`      | 0.004 | Near-wake correction |
| `alpha`   | 0.58  | Near-wake mixing angle |
| `beta`    | 0.077 | Far-wake decay coefficient |

#### Wake Deflection (Yaw Steering)

When a turbine yaws by angle γ (rotates out of the wind), the wake is deflected laterally. The GCH model computes this deflection analytically. The key physics:

1. **Thrust reduction:** `Ct(γ) = Ct(0) × cos²(γ)`
   - Yawing reduces thrust → shallower wake deficit
2. **Lateral momentum imbalance** creates a cross-stream velocity that steers the wake away from downstream turbines

This is called **wake steering** and is the physical basis for yaw optimization (Section 7).

#### GCH Enhancements (all enabled in `gch.yaml`)

| Feature | Parameter | Description |
|---------|-----------|-------------|
| Secondary steering | `enable_secondary_steering: true` | Counter-rotating vortex pairs generated by yaw improve deflection accuracy |
| Yaw-added recovery | `enable_yaw_added_recovery: true` | Yawed wakes recover faster due to enhanced turbulent mixing |
| Transverse velocities | `enable_transverse_velocities: true` | Cross-flow components included for deflected wakes |

#### Crespo-Hernández Turbulence Model

Controls how turbulence intensity (TI) evolves through the wake, which in turn governs how quickly the deficit recovers:

```
TI_wake = TI_ambient + C × (Ct)^a × (TI_ambient)^b × (x/D)^c
```

FLORIS parameters:

| Parameter    | Value | Role |
|-------------|-------|------|
| `initial`   | 0.1   | Ambient TI |
| `constant`  | 0.5   | Decay scaling constant |
| `ai`        | 0.8   | Induction factor exponent |
| `downstream`| -0.32 | Downstream distance exponent |

---

### 4.2 Jensen Top-Hat Model — Comparison

**Config:** `configs/jensen.yaml`

The Jensen model is the classical wind farm wake model (1983). It assumes the velocity deficit is **uniform** inside a conical wake region, and zero outside.

#### Wake Cone Geometry

```
Wake radius at distance x:  r_wake(x) = r_rotor + we × x
```

Where `we = 0.05` is the wake expansion coefficient.

#### Velocity Deficit Inside the Cone

Using conservation of momentum (actuator disk theory):

```
u_wake / u_inf = 1 - (1 - √(1 - Ct)) × (D / (D + 2×we×x))²
```

This is a **top-hat** profile: constant deficit inside the cone, zero outside. Computationally fast but physically less accurate than GCH, especially for yawed turbines.

**Jensen is used for comparison only** — all optimization runs use GCH.

---

### 4.3 Wake Superposition

When multiple wakes overlap at a downstream rotor, FLORIS combines them using the **Sum-of-Squares (SOSFS)** method:

```
u_total_deficit = √( Σ u_deficit_i² )
```

This is a common compromise between linear superposition (overestimates losses) and direct linear addition (underestimates).

---

## 5. AEP Calculation

Annual Energy Production is the integral of farm power over the wind climate for one year:

```
AEP [GWh] = Σ_{wd} Σ_{ws}  P_farm(wd, ws) × freq(wd, ws) × 8760
             ──────────────────────────────────────────────────────
                                    1 × 10⁹
```

Where:
- `P_farm(wd, ws)` = total farm power output in **Watts** at wind direction `wd`, speed `ws`
- `freq(wd, ws)` = probability (fraction of hours per year) from wind rose — normalized, sums to 1.0
- `8760` = hours per year
- `1×10⁹` = unit conversion from Wh to GWh

### Step-by-Step Computation

```
for each wind direction wd in [0°, 10°, ..., 350°]:
    for each wind speed ws in [4, 6, 8, 10, 12, 14] m/s:
        1. Set FLORIS: layout, yaw angles, wd, ws
        2. Run wake solver: fm.run()
        3. Get farm power: P = sum(fm.get_turbine_powers())   [W]
        4. Get frequency:  f = freq_table[wd, ws]
        5. Accumulate:     AEP += P × f × 8760

AEP /= 1e9   # convert Wh → GWh
```

### Physical Interpretation

`P_farm(wd, ws)` is not the sum of N independent turbine powers — it is the result of the full wake model. Turbines in wakes produce less, so `P_farm < N × P_single`. The ratio:

```
Wake efficiency = P_farm / (N × P_single_turbine)
```

is a key performance metric. A well-optimized layout achieves higher wake efficiency.

---

## 6. Layout Optimization

### 6.1 Problem Statement

Find turbine positions (x₁…xₙ, y₁…yₙ) on the site that maximize AEP:

```
maximize:   AEP(x₁, y₁, ..., xₙ, yₙ)
```

Subject to:
```
Boundary:   0 ≤ xᵢ ≤ 5000 m,  0 ≤ yᵢ ≤ 5000 m,  for all i

Spacing:    dist(Tᵢ, Tⱼ) ≥ 2D = 252 m,  for all i ≠ j

where dist(Tᵢ, Tⱼ) = √( (xᵢ-xⱼ)² + (yᵢ-yⱼ)² )
```

**Design variables:** 2N continuous values (x and y of each turbine)
For N=9 turbines: **18 variables**

### 6.2 Optimizer: SciPy SLSQP

**SLSQP (Sequential Least Squares Programming)** is a gradient-based nonlinear optimizer. It iteratively:

1. Approximates the objective function as a quadratic (second-order Taylor expansion)
2. Linearizes the constraints
3. Solves the resulting Quadratic Programming (QP) subproblem to find a search direction
4. Performs a line search along that direction
5. Repeats until convergence

**Settings:**

```python
optOptions = {"maxiter": 100, "ftol": 1e-6}
```

- `maxiter = 100` — stop after 100 iterations even if not converged
- `ftol = 1e-6` — converge when relative AEP change < 0.0001%

### 6.3 Gradient Computation

FLORIS has no analytical gradient. SLSQP uses **finite-difference approximation:**

```
∂AEP/∂xᵢ ≈ [AEP(xᵢ + δ) - AEP(xᵢ)] / δ
```

Each SLSQP iteration requires O(2N+1) FLORIS evaluations (one per variable perturbation + base). For N=9, that is ≈19 evaluations per iteration.

### 6.4 Constraint Enforcement

- **Boundary:** Linear inequality — handled directly by SLSQP
- **Spacing:** Nonlinear inequality — SLSQP uses an **augmented Lagrangian / penalty method** internally; spacing violations incur a large AEP penalty to push turbines apart

### 6.5 Example Result

Starting from a 3×3 grid with 630 m (5D) spacing:

| Stage                 | AEP (GWh) | Change   |
|-----------------------|-----------|----------|
| Baseline (3×3 grid)   | 138.887   | —        |
| Layout optimized      | 140.561   | +1.21%   |

**Optimized coordinates (Script 04 output):**

| Turbine | x (m)   | y (m)   |
|---------|---------|---------|
| T1      | 79.5    | 119.2   |
| T2      | 2418.8  | 398.7   |
| T3      | 4961.1  | 164.7   |
| T4      | 349.7   | 2392.7  |
| T5      | 2709.6  | 2600.0  |
| T6      | 4995.4  | 2425.2  |
| T7      | 151.9   | 4902.9  |
| T8      | 2622.3  | 4650.4  |
| T9      | 4749.7  | 4817.7  |

The optimizer spreads turbines toward site corners/edges, maximizing separation in the dominant westerly wind direction.

---

## 7. Yaw Optimization

### 7.1 Wake Steering Concept

Normally, turbines point directly into the wind to maximize individual power. But if an upstream turbine yaws (rotates slightly), its wake deflects sideways — potentially **missing the downstream turbines entirely**. The upstream turbine produces slightly less power, but the downstream gain can be much larger.

This strategy is called **wake steering** or **coordinated yaw control**.

### 7.2 Physics of Yaw Misalignment

When a turbine yaws by angle γ (positive = clockwise from wind direction):

**Thrust reduction:**
```
Ct(γ) = Ct(0) × cos²(γ)
```
- At γ = 25°: Ct drops to ~cos²(25°) = 0.82 of the aligned value
- Weaker thrust → shallower wake deficit

**Wake deflection:**
The deflected wake centre moves laterally by approximately:
```
δ_y(x) ≈ K × sin(γ) × cos(γ) × x / (1 + x/D)
```
where K is a model-dependent constant. For large downstream separations, the deflection can reach several rotor diameters.

**Power reduction at yawed turbine:**
```
P(γ) ≈ P(0) × cos³(γ)    (approximate; exact value from Cp table)
```
- At γ = 25°: upstream turbine produces ~cos³(25°) ≈ 0.75 of aligned power

### 7.3 Optimization Problem

For each wind direction wd, find per-turbine yaw angles that maximize total farm power:

```
maximize:   P_farm(γ₁, γ₂, ..., γₙ)

subject to: -25° ≤ γᵢ ≤ +25°,  for all i
```

**Design variables:** N continuous yaw angles (N=9 → 9 variables)

**Optimizer:** `YawOptimizationScipy` (SciPy SLSQP) — same algorithm as layout optimization, applied per wind direction at a representative wind speed of 8 m/s.

### 7.4 Optimization Workflow

```
1. Identify top-N most frequent wind directions from the wind rose
   (default N=2 in Script 04)

2. For each selected direction wd:
   a. Set FLORIS: fixed layout, wd, ws=8 m/s
   b. Run YawOptimizationScipy to find γ*(wd)
   c. Store optimal yaw angles in yaw_map[wd]

3. AEP sweep over all (wd, ws) bins:
   a. If wd in yaw_map: use optimized γ*(wd)
   b. Otherwise: γ = 0° for all turbines (aligned)
   c. fm.run() → accumulate AEP
```

### 7.5 Example Result — 270° (Westerly Wind)

In a 3×3 grid, 270° wind aligns directly with the turbine rows. Row T1→T2→T3 is fully wake-affected.

**Yaw angles found by optimizer:**

| Column    | Turbines     | Yaw angle (°) | Role |
|-----------|-------------|----------------|------|
| Upstream  | T1, T4, T7  | +25°           | Maximum deflection |
| Middle    | T2, T5, T8  | +19 to +20°    | Partial deflection |
| Downstream| T3, T6, T9  | 0°             | Full power capture |

**Power comparison at 270°, 8 m/s:**

| Turbine | Baseline (kW) | Yaw-Optimized (kW) | Change |
|---------|--------------|---------------------|--------|
| T1      | 1,753.95     | 1,458.96            | −17%   |
| T3      | 506.8        | 1,018.4             | +101%  |
| **Farm total** | **3,200** | **4,040**       | **+26.3%** |

The upstream sacrifice (~295 kW per turbine) enables each downstream turbine to roughly **double its power output**.

**AEP-level gains across test directions:**

| Wind Dir | Baseline (MW) | Yaw-Opt (MW) | Gain |
|----------|--------------|--------------|------|
| 260°     | 13.80        | 14.46        | +4.74% |
| 270°     | 3.20         | 4.04         | +26.33% |
| 280°     | 13.48        | 14.14        | +4.88% |

> Note: The 270° gain is disproportionately large because it is the exact alignment direction — any westerly offset (260°, 280°) reduces the wake overlap and diminishes the benefit.

---

## 8. Combined Pipeline — Script 04

Script 04 executes the full sequential pipeline and produces a comprehensive AEP report.

### Step-by-Step Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: LOAD INPUTS                                            │
│  • fm = FlorisModel("configs/gch.yaml")                         │
│  • wind_rose = WindRose("data/wind_rose.csv")                   │
│  • initial layout: 3×3 grid, 630 m spacing                     │
└─────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: BASELINE AEP                                           │
│  • fm.set(layout=grid_3x3, wind_data=wind_rose, yaw=0°)         │
│  • fm.run() over 216 wind bins                                  │
│  • AEP_baseline = fm.get_farm_AEP()  → 138.887 GWh             │
└─────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3: LAYOUT OPTIMIZATION                                    │
│  • LayoutOptimizationScipy(fm, boundaries, min_spacing=2D)      │
│  • SLSQP: maxiter=100, ftol=1e-6                                │
│  • Each FLORIS eval integrates over full wind rose              │
│  • layout_opt = result.opt_results                              │
│  • AEP_layout = fm.get_farm_AEP(layout_opt)  → 140.561 GWh     │
└─────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 4: YAW OPTIMIZATION                                       │
│  • Identify top-2 wind directions from freq table               │
│  • For each: YawOptimizationScipy(fm, layout_opt, wd, ws=8)     │
│  • Build yaw_map: {wd: [γ₁, γ₂, ..., γ₉]}                     │
└─────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 5: FINAL AEP WITH YAW MAP                                 │
│  • Loop over all 216 bins                                       │
│  • Apply yaw_map[wd] if available, else γ=0°                    │
│  • fm.run() per bin → accumulate AEP                            │
│  • AEP_final  → 140.574 GWh                                     │
└─────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│  STEP 6: OUTPUT                                                 │
│  • results/layout_optimised_coords.csv                          │
│  • results/yaw_optimised_angles.csv                             │
│  • results/full_analysis_report.csv                             │
│  • Plots: wind rose, layout comparison, wake field, AEP waterfall│
└─────────────────────────────────────────────────────────────────┘
```

### AEP Waterfall

```
138.887 GWh  ──► +1.674 GWh (layout) ──► +0.013 GWh (yaw) ──► 140.574 GWh
    Baseline          +1.21%                  +0.01%              Final
```

> The small yaw gain reflects only 2 directions being optimized. Optimizing all 36 directions would yield a larger contribution (~0.5–2% additional).

---

## 9. Turbine Count Sweep — Script 05

### Purpose

Determine the **economically optimal number of turbines** for the site. Adding turbines increases AEP, but each additional turbine produces less incremental energy (wake losses, limited site area). At some point, the marginal AEP gain no longer justifies the capital cost.

### Method

Brute-force loop over turbine counts N ∈ [4, 20]:

```
for N in range(4, 21):
    1. Build initial N-turbine layout (uniform grid approximation)
    2. Compute baseline AEP
    3. Run LayoutOptimizationScipy(N turbines, 100 iterations)
    4. Record:
       - AEP_opt[N]              → total optimized AEP
       - AEP_opt[N] / N          → AEP per turbine (efficiency metric)
```

### Key Output Metrics

| Metric | Economic Meaning |
|--------|-----------------|
| **Max total AEP** | The count that maximizes gross revenue |
| **Peak AEP/turbine** | The "elbow" — where efficiency begins declining |

The AEP/turbine curve shows **diminishing returns**: each added turbine steals wake from its neighbours, reducing the per-turbine contribution. The optimal count from an NPV perspective is where:

```
(Marginal AEP gain) × (energy price) > Turbine CAPEX
```

Typical "elbow" for a 5 km × 5 km site with 126 m rotors: N ≈ 9–12 turbines.

---

## 10. Results Summary

### AEP Stages (9 turbines)

| Stage                      | AEP (GWh) | Gain vs Baseline |
|---------------------------|-----------|-----------------|
| Baseline (3×3 grid, 0° yaw) | 138.887  | —               |
| + Layout optimization      | 140.561   | +1.21%          |
| + Yaw optimization (2 dirs)| 140.574   | +1.22%          |

### Script-Level Gains

| Script | Optimization | Gain |
|--------|-------------|------|
| 02     | Layout only | ~+1–5% AEP |
| 03     | Yaw only (3 directions) | +4–26% farm power at optimized directions |
| 04     | Layout + Yaw (full pipeline) | ~+1.22% AEP |
| 05     | Turbine count sweep | Economic optimum: N≈9–12 |

### Wake Loss at 270° (Westerly, 8 m/s)

| Row       | Upstream | Middle | Downstream |
|-----------|----------|--------|------------|
| Power (kW)| ~1,754   | ~820   | ~507       |
| vs. free  | 100%     | 47%    | 29%        |

The downstream row loses ~71% of its free-stream power due to wake effects — illustrating why optimization matters.

### Typical Runtimes

| Script | Task | Runtime |
|--------|------|---------|
| 01     | Wake visualization | < 30 s |
| 02     | Layout optimization (9 turbines) | 5–20 min |
| 03     | Yaw optimization (3 directions) | 2–10 min |
| 04     | Full pipeline | 10–30 min |
| 05     | Count sweep (4–20 turbines) | 1–3 hours |

---

## 11. Configuration Reference

### GCH Model (`configs/gch.yaml`) — Key Parameters

```yaml
wake:
  model_strings:
    velocity_model: gauss              # Gaussian velocity deficit
    deflection_model: gauss            # Gaussian wake deflection
    turbulence_model: crespo_hernandez # TI evolution model
    combination_model: sosfs           # Sum-of-squares superposition

  enable_secondary_steering: true      # Vortex-pair deflection (improves yaw accuracy)
  enable_yaw_added_recovery: true      # Faster wake recovery when yawed
  enable_transverse_velocities: true   # Cross-flow velocity components

  wake_velocity_parameters:
    gauss:
      ka: 0.38      # Wake expansion rate (lateral)
      kb: 0.004     # Near-wake correction
      alpha: 0.58   # Near-wake decay angle
      beta: 0.077   # Far-wake decay coefficient
      dm: 1.0       # Deficit magnitude scaling

  wake_turbulence_parameters:
    crespo_hernandez:
      initial: 0.1       # Ambient turbulence intensity
      constant: 0.5      # TI decay constant
      ai: 0.8            # Axial induction exponent
      downstream: -0.32  # Downstream distance exponent
```

### Jensen Model (`configs/jensen.yaml`) — Key Parameters

```yaml
wake:
  model_strings:
    velocity_model: jensen             # Top-hat uniform deficit
    deflection_model: jimenez          # Linear wake cone

  enable_secondary_steering: false
  enable_yaw_added_recovery: false
  enable_transverse_velocities: false

  wake_velocity_parameters:
    jensen:
      we: 0.05     # Wake expansion half-angle coefficient
```

### NREL 5MW Turbine (`configs/turbines/nrel_5mw.yaml`)

```yaml
turbine_type: nrel_5MW
hub_height: 90.0       # m
rotor_diameter: 126.0  # m
TSR: 8.0               # Tip-speed ratio at rated
pP: 1.88               # Yaw power loss exponent
pT: 1.88               # Yaw thrust loss exponent

power_thrust_table:
  wind_speed:          [0, 2.9, 3.0, 4.0, ..., 11.4, ..., 25.0, 25.01, 50.0]
  power:               [0, 0,   40,  177, ..., 5000, ..., 5000, 0,     0   ]  # kW
  thrust_coefficient:  [0, 0,   0.82,0.81,..., 0.48, ..., 0.10, 0,     0   ]
```

The `pP` and `pT` parameters control the yaw-induced power/thrust loss exponents in FLORIS's internal yaw model:

```
P(γ) = P(0) × cos(γ)^pP    (yaw power scaling)
Ct(γ) = Ct(0) × cos(γ)^pT  (yaw thrust scaling)
```

For NREL 5MW with `pP = pT = 1.88`, this closely approximates the `cos²(γ)` relationship used in the analytical derivation above.

---

*Generated from FLORIS v4.6 pipeline — NREL 5MW reference turbine, GCH wake model, SciPy SLSQP optimizer.*
