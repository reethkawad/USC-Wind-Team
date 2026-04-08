"""
count.py
========
Sweep over candidate turbine counts (N_MIN to N_MAX) and run layout
optimisation for each, to find the number of turbines that maximises
total AEP — and the "elbow" point where adding turbines stops paying off
(peak AEP-per-turbine).

Outputs (saved to outputs/):
  - turbine_count_aep.png          : total AEP vs turbine count
  - turbine_count_aep_per_unit.png : AEP per turbine vs count
  - turbine_count_best_layout.png  : optimised layout for best-AEP count
  - turbine_count_results.csv      : full numerical results table
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

_PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from wind_farm.config import (
    CONFIG_GCH as CONFIG_PATH, WIND_ROSE_CSV, OUTPUT_DIR, ROTOR_DIAMETER,
    SITE_SIZE_M, MIN_SPACING_D,
)
from wind_farm.wind_data import load_wind_rose
from wind_farm.layouts import build_rowmajor_layout
from wind_farm.optimization import load_floris_model, compute_aep, run_layout_optimization

# ---------------------------------------------------------------------------
# Parameters  ← edit these
# ---------------------------------------------------------------------------
N_MIN: int = 4
N_MAX: int = 20
MAXITER: int = 100

BOUNDARIES: list[tuple[float, float]] = [
    (0.0, 0.0),
    (SITE_SIZE_M, 0.0),
    (SITE_SIZE_M, SITE_SIZE_M),
    (0.0, SITE_SIZE_M),
]


def plot_aep_vs_count(results: pd.DataFrame, output_path: Path) -> None:
    """Total AEP (GWh) vs turbine count, with baseline and optimised lines."""
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(results["n_turbines"], results["aep_init_gwh"], "o--",
            color="steelblue", label="Initial grid layout", linewidth=1.5)
    ax.plot(results["n_turbines"], results["aep_opt_gwh"], "s-",
            color="tomato", label="Optimised layout", linewidth=2)

    best_idx = results["aep_opt_gwh"].idxmax()
    best_n = results.loc[best_idx, "n_turbines"]
    best_aep = results.loc[best_idx, "aep_opt_gwh"]
    ax.axvline(best_n, color="tomato", linestyle=":", alpha=0.6)
    ax.annotate(
        f"Max AEP\nN={best_n}, {best_aep:.1f} GWh",
        xy=(best_n, best_aep),
        xytext=(best_n + 0.4, best_aep * 0.97),
        fontsize=9,
        color="darkred",
    )

    ax.set_xlabel("Number of turbines", fontsize=11)
    ax.set_ylabel("Annual energy production (GWh)", fontsize=11)
    ax.set_title("Total AEP vs Turbine Count", fontsize=13)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {output_path}")


def plot_aep_per_turbine(results: pd.DataFrame, output_path: Path) -> None:
    """AEP per turbine (GWh) vs turbine count — shows diminishing returns."""
    aep_per = results["aep_opt_gwh"] / results["n_turbines"]

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(results["n_turbines"], aep_per, "D-", color="darkorange", linewidth=2)

    best_idx = aep_per.idxmax()
    best_n = results.loc[best_idx, "n_turbines"]
    ax.axvline(best_n, color="darkorange", linestyle=":", alpha=0.6)
    ax.annotate(
        f"Best efficiency\nN={best_n}",
        xy=(best_n, aep_per[best_idx]),
        xytext=(best_n + 0.4, aep_per[best_idx]),
        fontsize=9,
        color="saddlebrown",
    )

    ax.set_xlabel("Number of turbines", fontsize=11)
    ax.set_ylabel("AEP per turbine (GWh / turbine)", fontsize=11)
    ax.set_title("AEP per Turbine vs Count — Diminishing Returns", fontsize=13)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {output_path}")


def plot_best_layout(
    layout_x: list,
    layout_y: list,
    n: int,
    aep: float,
    output_path: Path,
) -> None:
    """Scatter plot of the optimised layout for the best turbine count."""
    fig, ax = plt.subplots(figsize=(7, 7))

    ax.add_patch(plt.Polygon(
        [(0, 0), (SITE_SIZE_M, 0), (SITE_SIZE_M, SITE_SIZE_M), (0, SITE_SIZE_M)],
        fill=False, edgecolor="black", linewidth=2, linestyle="--",
    ))

    for x, y in zip(layout_x, layout_y):
        ax.add_patch(plt.Circle((x, y), ROTOR_DIAMETER / 2, color="tomato", alpha=0.4))
    ax.scatter(layout_x, layout_y, color="tomato", s=40, zorder=5)

    ax.set_xlim(-200, SITE_SIZE_M + 200)
    ax.set_ylim(-200, SITE_SIZE_M + 200)
    ax.set_aspect("equal")
    ax.set_xlabel("x (m)", fontsize=11)
    ax.set_ylabel("y (m)", fontsize=11)
    ax.set_title(f"Optimised Layout — {n} Turbines\nAEP = {aep:.2f} GWh", fontsize=13)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {output_path}")


def run() -> None:
    print("=" * 60)
    print("Turbine Count Optimisation")
    print(f"  Sweeping N = {N_MIN} … {N_MAX}")
    print(f"  Site: {SITE_SIZE_M/1000:.1f} km × {SITE_SIZE_M/1000:.1f} km")
    print(f"  Min spacing: {MIN_SPACING_D:.0f}D = {MIN_SPACING_D * ROTOR_DIAMETER:.0f} m")
    print("=" * 60)

    print("\nLoading wind rose …")
    wind_rose = load_wind_rose(WIND_ROSE_CSV)[0]

    counts = list(range(N_MIN, N_MAX + 1))
    rows = []
    best_layout = None

    # Create one base model reused across all N — saves 16 unnecessary instantiations
    fm_base = load_floris_model(CONFIG_PATH)

    for n in counts:
        t0 = time.perf_counter()
        print(f"\n  N={n:2d}  optimising …", end="", flush=True)

        layout_x, layout_y = build_rowmajor_layout(n, site_size=SITE_SIZE_M, rotor_diameter=ROTOR_DIAMETER)

        aep_init = compute_aep(fm_base, wind_rose, layout_x, layout_y)

        opt_x, opt_y = run_layout_optimization(
            fm_base, wind_rose, layout_x, layout_y, BOUNDARIES,
            min_spacing_d=MIN_SPACING_D, rotor_diameter=ROTOR_DIAMETER, maxiter=MAXITER,
        )

        # Fresh model for clean AEP eval (optimizer mutates fm_base state)
        fm_eval = load_floris_model(CONFIG_PATH)
        aep_opt = compute_aep(fm_eval, wind_rose, opt_x, opt_y)

        elapsed = time.perf_counter() - t0
        gain = (aep_opt / aep_init - 1) * 100 if aep_init > 0 else 0.0
        print(f"  init={aep_init:.2f} GWh  opt={aep_opt:.2f} GWh  gain={gain:+.1f}%  [{elapsed:.0f}s]")

        rows.append({
            "n_turbines": n,
            "aep_init_gwh": round(aep_init, 4),
            "aep_opt_gwh": round(aep_opt, 4),
            "aep_per_turbine_gwh": round(aep_opt / n, 4),
            "gain_pct": round(gain, 2),
            "elapsed_s": round(elapsed, 1),
        })

        if best_layout is None or aep_opt > max(r["aep_opt_gwh"] for r in rows[:-1] or [{"aep_opt_gwh": 0}]):
            best_layout = (opt_x, opt_y, n, aep_opt)

    results = pd.DataFrame(rows)

    print("\n\nResults summary:")
    print(results[["n_turbines", "aep_init_gwh", "aep_opt_gwh", "aep_per_turbine_gwh", "gain_pct"]].to_string(index=False))

    best_row = results.loc[results["aep_opt_gwh"].idxmax()]
    eff_row = results.loc[(results["aep_opt_gwh"] / results["n_turbines"]).idxmax()]
    print(f"\n  → Highest total AEP : N={int(best_row['n_turbines'])}  ({best_row['aep_opt_gwh']:.2f} GWh)")
    print(f"  → Best AEP/turbine  : N={int(eff_row['n_turbines'])}  ({eff_row['aep_per_turbine_gwh']:.4f} GWh/turbine)")

    print("\nSaving outputs …")
    plot_aep_vs_count(results, OUTPUT_DIR / "turbine_count_aep.png")
    plot_aep_per_turbine(results, OUTPUT_DIR / "turbine_count_aep_per_unit.png")

    if best_layout is not None:
        opt_x, opt_y, best_n, best_aep = best_layout
        plot_best_layout(opt_x, opt_y, best_n, best_aep,
                         OUTPUT_DIR / "turbine_count_best_layout.png")

    csv_path = OUTPUT_DIR / "turbine_count_results.csv"
    results.to_csv(csv_path, index=False)
    print(f"  Saved: {csv_path}")

    print("\nDone. Outputs written to:", OUTPUT_DIR)


if __name__ == "__main__":
    run()
