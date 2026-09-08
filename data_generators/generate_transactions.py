"""Transactional orders and order items generator for E-Commerce OLTP.

Generates:
- Orders: Transactions with customer references, timestamps, payment methods,
  and calculated gross totals.
- Order Items: Granular purchased line items linking orders to product SKUs
  with quantities, unit prices, and promotional discounts.

Maintains relational consistency where order total_amount equals the sum of
its item line subtotals. Supports monthly/batch CSV exports and direct DB seeding.
"""

from __future__ import annotations

import argparse
import csv
import logging
import os
import random
from datetime import datetime, timedelta
from typing import Any, Sequence

from data_generators.db_connector import DatabaseConnector
from data_generators.generate_master_data import (
    PREDEFINED_PAYMENT_METHODS,
    MasterDataGenerator,
)
from data_generators.generate_products_customers import ProductCustomerGenerator

logger = logging.getLogger(__name__)

# Payment method weights matching e-commerce adoption in Vietnam
# Momo (45%), ZaloPay (25%), ShopeePay (15%), VNPay (10%), Apple Pay (5%)
PAYMENT_METHOD_IDS = [p["payment_method_id"] for p in PREDEFINED_PAYMENT_METHODS]
PAYMENT_METHOD_WEIGHTS = [
    0.35,  # Momo
    0.20,  # ZaloPay
    0.15,  # ShopeePay
    0.10,  # VNPay
    0.04,  # Apple Pay
    0.02,  # Google Pay
    0.04,  # Visa
    0.03,  # Mastercard
    0.01,  # JCB
    0.02,  # NAPAS
    0.01,  # PayPal
    0.01,  # Stripe
    0.005,  # Amazon Pay
    0.01,  # COD
    0.005,  # Bank Transfer
]


class TransactionGenerator:
    """Generates transactional orders and granular line items."""

    def __init__(self, seed: int = 42) -> None:
        """Initialize generator with reproducible seed."""
        self.seed = seed
        self.rng = random.Random(seed)

    def generate_transactions(
        self,
        customer_ids: Sequence[int],
        products: Sequence[dict[str, Any]],
        order_count: int = 500000,
        start_order_id: int = 1,
        start_item_id: int = 1,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Generate synchronized orders and order item records.

        Args:
            customer_ids: Available customer IDs.
            products: List of product dictionaries with product_id and price.
            order_count: Total orders to generate.
            start_order_id: Starting primary key for orders.
            start_item_id: Starting primary key for order items.
            start_date: Earliest transaction date.
            end_date: Latest transaction date.

        Returns:
            Tuple of (orders_list, order_items_list).
        """
        if not customer_ids:
            raise ValueError("customer_ids must not be empty.")
        if not products:
            raise ValueError("products must not be empty.")

        s_date = start_date or datetime(2024, 1, 1)
        e_date = end_date or datetime(2026, 9, 1)
        date_range_days = max(1, (e_date - s_date).days)

        orders: list[dict[str, Any]] = []
        order_items: list[dict[str, Any]] = []

        item_id_counter = start_item_id
        product_pool = list(products)

        # Quantity weights: 1 item (60%), 2 items (25%), 3 (10%), 4 (3%), 5 (2%)
        quantities = [1, 2, 3, 4, 5]
        qty_weights = [0.60, 0.25, 0.10, 0.03, 0.02]

        for i in range(order_count):
            order_id = start_order_id + i
            customer_id = self.rng.choice(customer_ids)

            order_timestamp = s_date + timedelta(
                days=self.rng.randint(0, date_range_days),
                seconds=self.rng.randint(0, 86400),
            )
            order_date_str = order_timestamp.strftime("%Y-%m-%d %H:%M:%S")

            payment_method_id = self.rng.choices(
                PAYMENT_METHOD_IDS, weights=PAYMENT_METHOD_WEIGHTS, k=1
            )[0]

            # Determine number of line items for this order (1 to 4 items)
            num_items = self.rng.choices(
                [1, 2, 3, 4], weights=[0.70, 0.20, 0.07, 0.03]
            )[0]
            chosen_products = self.rng.sample(
                product_pool, min(num_items, len(product_pool))
            )

            order_total = 0.0

            for prod in chosen_products:
                qty = self.rng.choices(quantities, weights=qty_weights)[0]
                unit_price = float(prod["price"])

                # 20% probability of promotional discount
                has_discount = self.rng.random() < 0.20
                discount_amt = (
                    round(self.rng.uniform(5.0, min(100.0, unit_price * 0.3)), 2)
                    if has_discount
                    else 0.00
                )

                subtotal = max(0.0, (qty * unit_price) - discount_amt)
                order_total += subtotal

                order_items.append(
                    {
                        "order_item_id": item_id_counter,
                        "order_id": order_id,
                        "product_id": prod["product_id"],
                        "quantity": qty,
                        "price": unit_price,
                        "discount": discount_amt,
                    }
                )
                item_id_counter += 1

            orders.append(
                {
                    "order_id": order_id,
                    "customer_id": customer_id,
                    "order_date": order_date_str,
                    "total_amount": round(order_total, 2),
                    "payment_method_id": payment_method_id,
                    "created_at": order_date_str,
                    "updated_at": order_date_str,
                }
            )

        logger.info(
            "Generated %d orders with %d order items.",
            len(orders),
            len(order_items),
        )
        return orders, order_items

    def export_to_csv(
        self,
        output_dir: str,
        customer_ids: Sequence[int],
        products: Sequence[dict[str, Any]],
        order_count: int = 500000,
        chunk_size: int = 50000,
        date_str: str | None = None,
    ) -> dict[str, str]:
        """Export transactions to CSV files chunk by chunk for minimal RAM usage.

        Args:
            output_dir: Target destination directory.
            customer_ids: List of available customer primary keys.
            products: List of product records.
            order_count: Total orders to export.
            chunk_size: Number of orders per batch.
            date_str: Date suffix for files (e.g. YYYYMMDD).

        Returns:
            Dictionary of exported file paths.
        """
        os.makedirs(output_dir, exist_ok=True)
        suffix = f"_{date_str}" if date_str else "_snapshot"

        orders_filename = f"orders{suffix}.csv"
        items_filename = f"order_items{suffix}.csv"

        orders_path = os.path.join(output_dir, orders_filename)
        items_path = os.path.join(output_dir, items_filename)

        with open(orders_path, "w", newline="", encoding="utf-8") as f_ord, open(
            items_path, "w", newline="", encoding="utf-8"
        ) as f_itm:
            ord_writer = csv.DictWriter(
                f_ord,
                fieldnames=[
                    "order_id",
                    "customer_id",
                    "order_date",
                    "total_amount",
                    "payment_method_id",
                    "created_at",
                    "updated_at",
                ],
            )
            ord_writer.writeheader()

            itm_writer = csv.DictWriter(
                f_itm,
                fieldnames=[
                    "order_item_id",
                    "order_id",
                    "product_id",
                    "quantity",
                    "price",
                    "discount",
                ],
            )
            itm_writer.writeheader()

            item_id_counter = 1
            total_orders_written = 0
            total_items_written = 0

            for start_idx in range(0, order_count, chunk_size):
                current_chunk = min(chunk_size, order_count - start_idx)
                batch_orders, batch_items = self.generate_transactions(
                    customer_ids=customer_ids,
                    products=products,
                    order_count=current_chunk,
                    start_order_id=1 + start_idx,
                    start_item_id=item_id_counter,
                )

                ord_writer.writerows(batch_orders)
                itm_writer.writerows(batch_items)

                item_id_counter += len(batch_items)
                total_orders_written += len(batch_orders)
                total_items_written += len(batch_items)

        logger.info(
            "Exported %d orders to %s and %d items to %s",
            total_orders_written,
            orders_path,
            total_items_written,
            items_path,
        )
        return {"orders": orders_path, "order_items": items_path}

    def seed_to_database(
        self,
        connector: DatabaseConnector,
        customer_ids: Sequence[int],
        products: Sequence[dict[str, Any]],
        order_count: int = 5000,
    ) -> dict[str, int]:
        """Directly insert orders and order_items into the database.

        Args:
            connector: Active DatabaseConnector instance.
            customer_ids: List of available customer IDs.
            products: List of product records.
            order_count: Total orders to insert.

        Returns:
            Dictionary with counts of inserted rows.
        """
        connector.init_schema()

        orders, items = self.generate_transactions(
            customer_ids=customer_ids,
            products=products,
            order_count=order_count,
        )

        order_rows = [
            (
                o["order_id"],
                o["customer_id"],
                o["order_date"],
                o["total_amount"],
                o["payment_method_id"],
                o["created_at"],
                o["updated_at"],
            )
            for o in orders
        ]
        inserted_orders = connector.bulk_insert(
            table="orders",
            columns=[
                "order_id",
                "customer_id",
                "order_date",
                "total_amount",
                "payment_method_id",
                "created_at",
                "updated_at",
            ],
            records=order_rows,
        )

        item_rows = [
            (
                it["order_item_id"],
                it["order_id"],
                it["product_id"],
                it["quantity"],
                it["price"],
                it["discount"],
            )
            for it in items
        ]
        inserted_items = connector.bulk_insert(
            table="order_items",
            columns=[
                "order_item_id",
                "order_id",
                "product_id",
                "quantity",
                "price",
                "discount",
            ],
            records=item_rows,
        )

        return {"orders": inserted_orders, "order_items": inserted_items}


def main() -> None:
    """CLI execution for transaction generator."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(
        description="Generate orders and order items for E-Commerce Platform"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data_generators/output",
        help="Directory to save transaction CSV files",
    )
    parser.add_argument(
        "--order-count",
        type=int,
        default=500000,
        help="Number of orders to generate (default: 500000)",
    )
    parser.add_argument(
        "--date-suffix",
        type=str,
        default=None,
        help="Optional date suffix like 20251130 for file naming",
    )
    parser.add_argument(
        "--seed-db",
        action="store_true",
        help="Whether to seed into the relational database",
    )

    args = parser.parse_args()

    # Pre-generate prerequisite entities
    master_gen = MasterDataGenerator()
    brands = master_gen.generate_brands(count=2000)
    brand_ids = [b["brand_id"] for b in brands]

    prod_cust_gen = ProductCustomerGenerator()
    products = prod_cust_gen.generate_products(brand_ids=brand_ids, count=1000)
    customers = prod_cust_gen.generate_customers(count=10000)
    customer_ids = [c["customer_id"] for c in customers]

    tx_gen = TransactionGenerator()
    paths = tx_gen.export_to_csv(
        output_dir=args.output_dir,
        customer_ids=customer_ids,
        products=products,
        order_count=args.order_count,
        date_str=args.date_suffix,
    )
    for name, path in paths.items():
        print(f"Created {name}: {path}")

    if args.seed_db:
        connector = DatabaseConnector()
        with connector:
            master_gen.seed_to_database(connector=connector, brand_count=2000)
            prod_cust_gen.seed_to_database(
                connector=connector,
                brand_ids=brand_ids,
                product_count=1000,
                customer_count=10000,
            )
            stats = tx_gen.seed_to_database(
                connector=connector,
                customer_ids=customer_ids,
                products=products,
                order_count=min(args.order_count, 10000),
            )
            print(f"Database seeded successfully: {stats}")


if __name__ == "__main__":
    main()
