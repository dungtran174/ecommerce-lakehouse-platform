"""Unified Command Line Interface for Data Generation & Batch Seeding.

Coordinates the synthetic data generation pipeline across all e-commerce domains:
1. Master entities (brands, categories, payment methods)
2. Catalog and Customer profiles (products, customers)
3. Transactional orders and line items (orders, order_items)
4. Semi-structured web clickstream interaction logs

Provides presets:
- small: For fast local testing and CI/CD validation
- medium: For staging and demo exploration
- full: Matches report volume (2,000 brands, 1,000 products, 100k users, 500k orders)
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from typing import Any

from data_generators.db_connector import DatabaseConnector
from data_generators.generate_clickstream_logs import ClickstreamGenerator
from data_generators.generate_master_data import MasterDataGenerator
from data_generators.generate_products_customers import ProductCustomerGenerator
from data_generators.generate_transactions import TransactionGenerator

logger = logging.getLogger("data_generators.cli")

SCALE_CONFIGS: dict[str, dict[str, Any]] = {
    "small": {
        "brands": 50,
        "products": 50,
        "customers": 100,
        "orders": 200,
        "clickstream_days": 2,
        "sessions_per_day": 100,
    },
    "medium": {
        "brands": 500,
        "products": 500,
        "customers": 5000,
        "orders": 15000,
        "clickstream_days": 3,
        "sessions_per_day": 1000,
    },
    "full": {
        "brands": 2000,
        "products": 1000,
        "customers": 100000,
        "orders": 500000,
        "clickstream_days": 7,
        "sessions_per_day": 10000,
    },
}


def run_oltp_pipeline(
    scale: str = "small",
    output_dir: str = "data_generators/output/mysql",
    seed_db: bool = False,
    connector: DatabaseConnector | None = None,
) -> dict[str, Any]:
    """Execute OLTP relational generation pipeline.

    Args:
        scale: Scale preset (small, medium, full).
        output_dir: Destination folder for Bronze CSV snapshots.
        seed_db: Whether to seed relational database.
        connector: Optional active DatabaseConnector instance.

    Returns:
        Dictionary of generated files and database statistics.
    """
    cfg = SCALE_CONFIGS.get(scale, SCALE_CONFIGS["small"])
    logger.info("Starting OLTP data generation with '%s' scale preset...", scale)
    os.makedirs(output_dir, exist_ok=True)

    master_gen = MasterDataGenerator()
    prod_cust_gen = ProductCustomerGenerator()
    tx_gen = TransactionGenerator()

    # 1. Master entities
    logger.info("Generating master entities (brands, categories, payment methods)...")
    master_files = master_gen.export_to_csv(
        output_dir=output_dir, brand_count=cfg["brands"]
    )
    brands = master_gen.generate_brands(count=cfg["brands"])
    brand_ids = [b["brand_id"] for b in brands]

    # 2. Products and Customers
    logger.info(
        "Generating products (%d) and customers (%d)...",
        cfg["products"],
        cfg["customers"],
    )
    prod_cust_files = prod_cust_gen.export_to_csv(
        output_dir=output_dir,
        brand_ids=brand_ids,
        product_count=cfg["products"],
        customer_count=cfg["customers"],
    )
    products = prod_cust_gen.generate_products(
        brand_ids=brand_ids, count=cfg["products"]
    )
    customers = prod_cust_gen.generate_customers(count=cfg["customers"])
    customer_ids = [c["customer_id"] for c in customers]

    # 3. Transactions
    logger.info("Generating orders (%d) and line items...", cfg["orders"])
    tx_files = tx_gen.export_to_csv(
        output_dir=output_dir,
        customer_ids=customer_ids,
        products=products,
        order_count=cfg["orders"],
    )

    all_files = {**master_files, **prod_cust_files, **tx_files}

    db_stats: dict[str, int] = {}
    if seed_db:
        conn = connector or DatabaseConnector()
        with conn:
            conn.init_schema()
            s1 = master_gen.seed_to_database(connector=conn, brand_count=cfg["brands"])
            db_brands = conn.execute_query("SELECT brand_id FROM brands")
            actual_brand_ids = [r["brand_id"] for r in db_brands]

            s2 = prod_cust_gen.seed_to_database(
                connector=conn,
                brand_ids=actual_brand_ids,
                product_count=cfg["products"],
                customer_count=min(cfg["customers"], 5000),
            )

            db_customers = conn.execute_query("SELECT customer_id FROM customers")
            actual_cust_ids = [r["customer_id"] for r in db_customers]
            db_prods = conn.execute_query("SELECT product_id, price FROM products")

            s3 = tx_gen.seed_to_database(
                connector=conn,
                customer_ids=actual_cust_ids,
                products=db_prods,
                order_count=min(cfg["orders"], 5000),
            )
            db_stats = {**s1, **s2, **s3}

    logger.info("OLTP pipeline finished. Output files: %s", list(all_files.keys()))
    return {"files": all_files, "db_stats": db_stats}


def run_clickstream_pipeline(
    scale: str = "small",
    output_dir: str = "data_generators/output/clickstream",
    start_date: str = "2026-09-01",
    parts_per_day: int = 2,
) -> dict[str, list[str]]:
    """Execute clickstream log generation pipeline.

    Args:
        scale: Scale preset.
        output_dir: Destination folder for partitioned NDJSON.
        start_date: Starting calendar date YYYY-MM-DD.
        parts_per_day: Number of part files per date folder.

    Returns:
        Dictionary mapping partition dates to generated part files.
    """
    cfg = SCALE_CONFIGS.get(scale, SCALE_CONFIGS["small"])
    logger.info("Starting Clickstream generation (%s scale)...", scale)

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    click_gen = ClickstreamGenerator()

    # Create small pool of products for realistic session actions
    master_gen = MasterDataGenerator()
    brands = master_gen.generate_brands(count=50)
    brand_ids = [b["brand_id"] for b in brands]
    prod_gen = ProductCustomerGenerator()
    products = prod_gen.generate_products(brand_ids=brand_ids, count=100)

    log_files = click_gen.generate_multi_day_logs(
        start_date=start_dt,
        days=cfg["clickstream_days"],
        sessions_per_day=cfg["sessions_per_day"],
        output_dir=output_dir,
        products=products,
        parts_per_day=parts_per_day,
    )

    total_files = sum(len(f) for f in log_files.values())
    logger.info(
        "Clickstream finished. Generated %d files across %d days.",
        total_files,
        len(log_files),
    )
    return log_files


def main(args_list: list[str] | None = None) -> None:
    """CLI entrypoint for running data generation pipelines."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    parser = argparse.ArgumentParser(
        prog="python -m data_generators",
        description="E-Commerce Lakehouse Platform - Data Generation Suite",
    )
    parser.add_argument(
        "--target",
        choices=["all", "oltp", "clickstream"],
        default="all",
        help="Target data domain to generate (default: all)",
    )
    parser.add_argument(
        "--scale",
        choices=["small", "medium", "full"],
        default="small",
        help="Volume scale preset (default: small)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data_generators/output",
        help="Base directory for generated datasets",
    )
    parser.add_argument(
        "--seed-db",
        action="store_true",
        help="Whether to insert records directly into relational database",
    )
    parser.add_argument(
        "--clickstream-days",
        type=int,
        default=None,
        help="Override days for clickstream logs",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        default="2026-09-01",
        help="Start date YYYY-MM-DD for clickstream logs (default: 2026-09-01)",
    )

    args = parser.parse_args(args_list)

    if args.target in ("all", "oltp"):
        oltp_out = os.path.join(args.output_dir, "mysql")
        run_oltp_pipeline(
            scale=args.scale,
            output_dir=oltp_out,
            seed_db=args.seed_db,
        )

    if args.target in ("all", "clickstream"):
        click_out = os.path.join(args.output_dir, "clickstream")
        run_clickstream_pipeline(
            scale=args.scale,
            output_dir=click_out,
            start_date=args.start_date,
        )


if __name__ == "__main__":
    main(sys.argv[1:])
