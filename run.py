"""
run.py
======
Unified CLI entry point for the wind farm optimization pipeline.

Usage
-----
    python run.py <command> [<command> ...]
    python run.py optimal --n <N>

Commands (run in the order given):
    wake    Wake field visualization (3×3 grid)
    layout  Layout optimization (turbine positions → max AEP)
    yaw     Yaw angle optimization (wake steering)
    full    Full end-to-end analysis pipeline
    count   Turbine count sweep (find optimal turbine count)
    optimal Full pipeline for a specified turbine count N

Examples
--------
    python run.py wake
    python run.py layout
    python run.py count layout wake     # runs: count → layout → wake
    python run.py full
    python run.py wake layout yaw full  # all four in sequence
    python run.py optimal --n 12        # full pipeline for N=12 turbines
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure the project root is on sys.path so wind_farm/ and scripts/ are importable
_PROJECT_DIR = Path(__file__).resolve().parent
if str(_PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(_PROJECT_DIR))

COMMANDS: dict[str, str] = {
    "wake":    "Wake field visualization (3×3 grid)",
    "layout":  "Layout optimization (turbine positions)",
    "yaw":     "Yaw angle optimization (wake steering)",
    "full":    "Full end-to-end analysis pipeline",
    "count":   "Turbine count sweep (find optimal count)",
    "optimal": "Full pipeline for specified N (use --n to set count)",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="Wind Farm Optimization CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(f"  {k:8s}  {v}" for k, v in COMMANDS.items()),
    )
    parser.add_argument(
        "commands",
        nargs="+",
        choices=list(COMMANDS.keys()),
        metavar="COMMAND",
        help=f"One or more commands to run in order. Choices: {list(COMMANDS)}",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=9,
        metavar="N",
        help="Number of turbines for the 'optimal' command (default: 9)",
    )
    args = parser.parse_args()

    for cmd in args.commands:
        if cmd == "wake":
            from scripts.wake import run
        elif cmd == "layout":
            from scripts.layout import run
        elif cmd == "yaw":
            from scripts.yaw import run
        elif cmd == "full":
            from scripts.full import run
        elif cmd == "count":
            from scripts.count import run
        elif cmd == "optimal":
            from scripts.optimal import run as _run
            _run(n_turbines=args.n)
            continue
        run()


if __name__ == "__main__":
    main()
