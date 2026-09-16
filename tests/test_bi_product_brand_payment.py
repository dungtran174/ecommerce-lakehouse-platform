"""Unit tests for Metabase product catalog, brand origin, and payment share dashboards."""

from __future__ import annotations

import json
import os
import unittest


class TestBiProductBrandPayment(unittest.TestCase):
    """Test suite validating Product, Brand Origin, and Payment Channel SQL & JSON definitions."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate dashboard files and load contents."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.dashboards_dir = os.path.join(cls.root_dir, "bi", "metabase", "dashboards")
        cls.products_sql_file = os.path.join(cls.dashboards_dir, "products_brands.sql")
        cls.payments_sql_file = os.path.join(
            cls.dashboards_dir, "payment_distribution.sql"
        )
        cls.json_file = os.path.join(cls.dashboards_dir, "product_brand_payment.json")
        cls.readme_file = os.path.join(cls.dashboards_dir, "README.md")

    def test_dashboard_files_exist(self) -> None:
        """Verify that SQL recipes, JSON dashboard, and documentation exist."""
        self.assertTrue(
            os.path.exists(self.products_sql_file), "products_brands.sql must exist"
        )
        self.assertTrue(
            os.path.exists(self.payments_sql_file),
            "payment_distribution.sql must exist",
        )
        self.assertTrue(
            os.path.exists(self.json_file), "product_brand_payment.json must exist"
        )
        self.assertTrue(
            os.path.exists(self.readme_file), "dashboards/README.md must exist"
        )

    def test_products_brands_sql_schema_and_queries(self) -> None:
        """Verify product ranking, category share, and MySQL federated brand join."""
        with open(self.products_sql_file, "r", encoding="utf-8") as f:
            sql = f.read()

        # Delta Lake table and join assertions
        self.assertIn("lakehouse.gold_sale_mart.fact_order_items", sql)
        self.assertIn("lakehouse.gold_sale_mart.dim_product", sql)
        self.assertIn("foi.product_key = p.product_id", sql)

        # MySQL federated join assertions
        self.assertIn("mysql.ecommerce_oltp.brands", sql)
        self.assertIn("p.brand_name = b.brand_name", sql)

        # Ranking and market share assertions
        self.assertIn("LIMIT 10", sql)
        self.assertIn("ORDER BY", sql)
        self.assertIn("total_net_revenue DESC", sql)
        self.assertIn("category_revenue_share_pct", sql)
        self.assertIn("OVER ()", sql)

    def test_payment_distribution_sql_schema_and_queries(self) -> None:
        """Verify payment method share, channel breakdown, and monthly adoption trend."""
        with open(self.payments_sql_file, "r", encoding="utf-8") as f:
            sql = f.read()

        # Delta Lake tables and join assertions
        self.assertIn("lakehouse.gold_sale_mart.fact_order", sql)
        self.assertIn("lakehouse.gold_sale_mart.dim_payment_method", sql)
        self.assertIn("f.payment_method_key = pm.payment_method_id", sql)
        self.assertIn("lakehouse.gold_sale_mart.dim_date", sql)
        self.assertIn("f.date_key = d.date_key", sql)

        # Market share and channel metrics
        self.assertIn("transaction_volume_share_pct", sql)
        self.assertIn("revenue_market_share_pct", sql)
        self.assertIn("payment_channel_type", sql)
        self.assertIn("monthly_revenue_share_pct", sql)
        self.assertIn("OVER (PARTITION BY year, month)", sql)

    def test_product_brand_payment_json_structure(self) -> None:
        """Verify JSON metadata schema, parameters, and grid card configurations."""
        with open(self.json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Top-level properties
        self.assertIn("name", data)
        self.assertIn("description", data)
        self.assertIn("parameters", data)
        self.assertIn("cards", data)
        self.assertGreaterEqual(len(data["cards"]), 6)

        # Verify card IDs
        card_ids = [c["id"] for c in data["cards"]]
        for expected_id in [201, 202, 203, 204, 205, 206]:
            self.assertIn(expected_id, card_ids)

        for card in data["cards"]:
            self.assertIn("name", card)
            self.assertIn("display", card)
            self.assertIn("dataset_query", card)
            self.assertIn("grid", card)

            # Grid coordinate bounds
            grid = card["grid"]
            self.assertIn("col", grid)
            self.assertIn("row", grid)
            self.assertIn("size_x", grid)
            self.assertIn("size_y", grid)
            self.assertGreaterEqual(grid["col"], 0)
            self.assertLessEqual(grid["col"] + grid["size_x"], 12)

    def test_trino_sql_dialect_cleanliness(self) -> None:
        """Verify absence of incompatible legacy SQL syntax across SQL files."""
        for file_path in [self.products_sql_file, self.payments_sql_file]:
            with open(file_path, "r", encoding="utf-8") as f:
                sql = f.read().upper()

            self.assertNotIn("NVL(", sql)
            self.assertNotIn("IFNULL(", sql)


if __name__ == "__main__":
    unittest.main()
