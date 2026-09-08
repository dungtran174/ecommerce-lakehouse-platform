"""Unit tests for TransactionGenerator (orders and order items)."""

import csv
import os
import shutil
import tempfile
import unittest
from datetime import datetime

from data_generators.db_connector import DatabaseConnector
from data_generators.generate_master_data import (
    PREDEFINED_PAYMENT_METHODS,
    MasterDataGenerator,
)
from data_generators.generate_products_customers import ProductCustomerGenerator
from data_generators.generate_transactions import TransactionGenerator


class TestTransactionGenerator(unittest.TestCase):
    """Test suite for transactional orders and line items generation."""

    def setUp(self) -> None:
        """Initialize mock prerequisites, generator, and temp directory."""
        self.test_dir = tempfile.mkdtemp()
        self.tx_gen = TransactionGenerator(seed=42)

        self.master_gen = MasterDataGenerator(seed=42)
        self.brands = self.master_gen.generate_brands(count=20)
        self.brand_ids = [b["brand_id"] for b in self.brands]

        self.prod_cust_gen = ProductCustomerGenerator(seed=42)
        self.products = self.prod_cust_gen.generate_products(
            brand_ids=self.brand_ids, count=30
        )
        self.customers = self.prod_cust_gen.generate_customers(count=50)
        self.customer_ids = [c["customer_id"] for c in self.customers]

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_generate_transactions_integrity_and_totals(self) -> None:
        """Verify order-to-item relationship, line sums, and foreign keys."""
        order_count = 50
        orders, items = self.tx_gen.generate_transactions(
            customer_ids=self.customer_ids,
            products=self.products,
            order_count=order_count,
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 31),
        )

        self.assertEqual(len(orders), order_count)
        self.assertGreaterEqual(len(items), order_count)

        # Group items by order_id
        items_by_order: dict[int, list[dict]] = {}
        for item in items:
            items_by_order.setdefault(item["order_id"], []).append(item)

        valid_product_ids = {p["product_id"] for p in self.products}
        valid_payment_ids = {p["payment_method_id"] for p in PREDEFINED_PAYMENT_METHODS}

        for order in orders:
            o_id = order["order_id"]
            self.assertIn(o_id, items_by_order)
            self.assertIn(order["customer_id"], self.customer_ids)
            self.assertIn(order["payment_method_id"], valid_payment_ids)

            # Check total_amount matches line items sum
            expected_total = sum(
                max(0.0, (it["quantity"] * it["price"]) - it["discount"])
                for it in items_by_order[o_id]
            )
            self.assertAlmostEqual(order["total_amount"], expected_total, places=2)

        for item in items:
            self.assertIn(item["product_id"], valid_product_ids)
            self.assertGreater(item["quantity"], 0)
            self.assertGreater(item["price"], 0)
            self.assertGreaterEqual(item["discount"], 0)

    def test_export_to_csv(self) -> None:
        """Verify chunked CSV export creates valid orders and order items files."""
        files = self.tx_gen.export_to_csv(
            output_dir=self.test_dir,
            customer_ids=self.customer_ids,
            products=self.products,
            order_count=60,
            chunk_size=30,
            date_str="20251130",
        )

        self.assertIn("orders", files)
        self.assertIn("order_items", files)

        for _name, path in files.items():
            self.assertTrue(os.path.exists(path))
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                rows = list(reader)
                self.assertGreater(len(rows), 1)

    def test_seed_to_database(self) -> None:
        """Verify database seeding into SQLite with active foreign keys."""
        db_path = os.path.join(self.test_dir, "test_tx.db")
        connector = DatabaseConnector(use_sqlite=True, sqlite_path=db_path)

        with connector:
            # Seed master entities
            self.master_gen.seed_to_database(connector=connector, brand_count=20)
            db_brands = connector.execute_query("SELECT brand_id FROM brands")
            actual_brand_ids = [r["brand_id"] for r in db_brands]

            # Seed products & customers
            self.prod_cust_gen.seed_to_database(
                connector=connector,
                brand_ids=actual_brand_ids,
                product_count=25,
                customer_count=30,
            )
            db_customers = connector.execute_query("SELECT customer_id FROM customers")
            actual_customer_ids = [r["customer_id"] for r in db_customers]

            db_products = connector.execute_query(
                "SELECT product_id, price FROM products"
            )

            # Seed transactions
            stats = self.tx_gen.seed_to_database(
                connector=connector,
                customer_ids=actual_customer_ids,
                products=db_products,
                order_count=40,
            )

            self.assertEqual(stats["orders"], 40)
            self.assertGreaterEqual(stats["order_items"], 40)
            self.assertEqual(connector.count_rows("orders"), 40)
            self.assertEqual(connector.count_rows("order_items"), stats["order_items"])


if __name__ == "__main__":
    unittest.main()
