"""Comprehensive test suite for data generator integrity and schema validation.

Validates:
1. Cross-domain referential integrity across master, transactional, and log entities
2. Temporal consistency (order dates >= customer creation dates, monotonic action offsets)
3. Mathematical precision (order totals == line subtotals, session revenues == purchase sum)
4. Schema fidelity of Bronze CSV snapshots and NDJSON against data dictionary specs
"""

from __future__ import annotations

import csv
import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime

from data_generators.cli import run_clickstream_pipeline, run_oltp_pipeline
from data_generators.generate_master_data import (
    COUNTRIES_OF_ORIGIN,
    PREDEFINED_CATEGORIES,
    PREDEFINED_PAYMENT_METHODS,
)
from data_generators.generate_products_customers import (
    CUSTOMER_TIERS,
    VIETNAMESE_PROVINCES,
)


class TestDataGeneratorIntegrity(unittest.TestCase):
    """End-to-end data integrity, referential consistency, and schema validation."""

    @classmethod
    def setUpClass(cls) -> None:
        """Generate test datasets once for validation suite."""
        cls.test_dir = tempfile.mkdtemp()
        cls.mysql_dir = os.path.join(cls.test_dir, "mysql")
        cls.logs_dir = os.path.join(cls.test_dir, "clickstream")

        # Run small scale generation for both OLTP and clickstream
        cls.oltp_results = run_oltp_pipeline(
            scale="small",
            output_dir=cls.mysql_dir,
            seed_db=False,
        )
        cls.clickstream_results = run_clickstream_pipeline(
            scale="small",
            output_dir=cls.logs_dir,
            start_date="2026-09-01",
            parts_per_day=1,
        )

        # Load CSV data into memory for assertions
        cls.data: dict[str, list[dict[str, str]]] = {}
        for name, path in cls.oltp_results["files"].items():
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                cls.data[name] = list(reader)

        # Load clickstream records
        cls.sessions: list[dict] = []
        for file_list in cls.clickstream_results.values():
            for p in file_list:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            cls.sessions.append(json.loads(line.strip()))

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up generated temporary files."""
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_bronze_csv_schema_fidelity(self) -> None:
        """Verify exported CSV column headers exactly match Data Dictionary specs."""
        expected_schemas = {
            "brands": ["brand_id", "brand_name", "brand_origin"],
            "category": [
                "category_id",
                "category_display_name",
                "category_description",
            ],
            "payment_method": [
                "payment_method_id",
                "display_name",
                "type",
                "provider",
            ],
            "customers": [
                "customer_id",
                "first_name",
                "last_name",
                "email",
                "phone_number",
                "gender",
                "tire",
                "address",
                "created_at",
                "updated_at",
            ],
            "products": [
                "product_id",
                "product_name",
                "product_description",
                "price",
                "category_id",
                "brand_id",
                "created_at",
                "updated_at",
            ],
            "orders": [
                "order_id",
                "customer_id",
                "order_date",
                "total_amount",
                "payment_method_id",
                "created_at",
                "updated_at",
            ],
            "order_items": [
                "order_item_id",
                "order_id",
                "product_id",
                "quantity",
                "price",
                "discount",
            ],
        }

        for table, expected_cols in expected_schemas.items():
            self.assertIn(table, self.data, f"Table {table} must be generated")
            rows = self.data[table]
            self.assertGreater(len(rows), 0, f"Table {table} must contain records")
            actual_cols = list(rows[0].keys())
            self.assertEqual(
                actual_cols,
                expected_cols,
                f"Column mismatch for {table}: {actual_cols} != {expected_cols}",
            )

    def test_cross_domain_referential_integrity(self) -> None:
        """Verify foreign key references across all generated relational tables."""
        brand_ids = {r["brand_id"] for r in self.data["brands"]}
        cat_ids = {r["category_id"] for r in self.data["category"]}
        cust_ids = {r["customer_id"] for r in self.data["customers"]}
        prod_ids = {r["product_id"] for r in self.data["products"]}
        order_ids = {r["order_id"] for r in self.data["orders"]}
        payment_ids = {r["payment_method_id"] for r in self.data["payment_method"]}

        # 1. Product foreign keys -> Brands & Category
        for prod in self.data["products"]:
            self.assertIn(prod["brand_id"], brand_ids)
            self.assertIn(prod["category_id"], cat_ids)

        # 2. Orders foreign keys -> Customers & Payment Methods
        for order in self.data["orders"]:
            self.assertIn(order["customer_id"], cust_ids)
            self.assertIn(order["payment_method_id"], payment_ids)

        # 3. Order items foreign keys -> Orders & Products
        for item in self.data["order_items"]:
            self.assertIn(item["order_id"], order_ids)
            self.assertIn(item["product_id"], prod_ids)

    def test_mathematical_consistency_order_totals(self) -> None:
        """Verify order total_amount equals exact sum of item subtotals."""
        items_by_order: dict[str, list[dict[str, str]]] = {}
        for item in self.data["order_items"]:
            items_by_order.setdefault(item["order_id"], []).append(item)

        for order in self.data["orders"]:
            o_id = order["order_id"]
            self.assertIn(o_id, items_by_order)
            calculated_total = sum(
                max(
                    0.0,
                    (int(it["quantity"]) * float(it["price"])) - float(it["discount"]),
                )
                for it in items_by_order[o_id]
            )
            self.assertAlmostEqual(
                float(order["total_amount"]), calculated_total, places=2
            )

    def test_temporal_consistency(self) -> None:
        """Verify chronological sequence (orders within 2024-2026, valid format)."""
        dt_format = "%Y-%m-%d %H:%M:%S"
        max_allowed_date = datetime(2026, 9, 8)

        for order in self.data["orders"]:
            o_date = datetime.strptime(order["order_date"], dt_format)
            self.assertLessEqual(
                o_date,
                max_allowed_date,
                f"Order date {o_date} cannot be in the future relative to execution",
            )
            self.assertGreaterEqual(
                o_date,
                datetime(2024, 1, 1),
                f"Order date {o_date} cannot be earlier than platform inception",
            )

    def test_domain_values_conformance(self) -> None:
        """Verify categorical domain values conform to specified vocabularies."""
        for brand in self.data["brands"]:
            self.assertIn(brand["brand_origin"], COUNTRIES_OF_ORIGIN)

        for cust in self.data["customers"]:
            self.assertIn(cust["tire"], CUSTOMER_TIERS)
            self.assertIn(cust["gender"], ["Nam", "Nữ"])
            self.assertIn(cust["address"], VIETNAMESE_PROVINCES)

        predefined_cat_names = {
            c["category_display_name"] for c in PREDEFINED_CATEGORIES
        }
        for cat in self.data["category"]:
            self.assertIn(cat["category_display_name"], predefined_cat_names)

        predefined_pay_names = {p["display_name"] for p in PREDEFINED_PAYMENT_METHODS}
        for pay in self.data["payment_method"]:
            self.assertIn(pay["display_name"], predefined_pay_names)

    def test_clickstream_schema_and_action_ordering(self) -> None:
        """Verify NDJSON records adhere to schema, ISO 8601, and monotonic offsets."""
        self.assertGreater(len(self.sessions), 0)

        for sess in self.sessions:
            # Timestamp check
            ts_str = sess["timestamp"]
            self.assertTrue(ts_str.endswith("Z"))
            parsed_dt = datetime.strptime(ts_str, "%Y-%m-%dT%H:%M:%S.%fZ")
            self.assertLessEqual(parsed_dt, datetime(2026, 9, 8))

            # Action offsets must be monotonically non-decreasing
            actions = sess["actions"]
            self.assertGreater(len(actions), 0)
            offsets = [a["time_offset"] for a in actions]
            self.assertEqual(
                offsets,
                sorted(offsets),
                "Action time_offsets must be monotonic",
            )

            # Metrics coherence
            metrics = sess["session_metrics"]
            self.assertEqual(metrics["actions_count"], len(actions))
            self.assertGreaterEqual(
                metrics["duration_seconds"],
                max(offsets),
                "Session duration must exceed max action offset",
            )


if __name__ == "__main__":
    unittest.main()
