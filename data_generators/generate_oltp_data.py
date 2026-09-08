"""OLTP Data Generation Script Entrypoint.

Directly executed by Makefile (`make seed-data`) or standalone CLI:
python data_generators/generate_oltp_data.py --scale small
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

# Ensure repository root is on sys.path for direct script execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from data_generators.cli import run_oltp_pipeline  # noqa: E402


def main() -> None:
    """CLI entrypoint for OLTP generation."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(
        description="Generate E-Commerce OLTP Relational Data"
    )
    parser.add_argument(
        "--scale",
        choices=["small", "medium", "full"],
        default="small",
        help="Data scale preset (default: small)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data_generators/output/mysql",
        help="Destination directory for snapshot CSV files",
    )
    parser.add_argument(
        "--seed-db",
        action="store_true",
        help="Seed generated data directly into relational database",
    )

    args = parser.parse_args()
    results = run_oltp_pipeline(
        scale=args.scale,
        output_dir=args.output_dir,
        seed_db=args.seed_db,
    )
    print(f"Generated {len(results['files'])} OLTP snapshot files in {args.output_dir}")


if __name__ == "__main__":
    main()
