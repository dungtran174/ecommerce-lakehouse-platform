"""Unit tests for conformed Silver transactional models (silver_orders, silver_order_items)."""

from __future__ import annotations

import os
import unittest

import yaml


class TestDbtSilverOrders(unittest.TestCase):
    """Test suite validating silver_orders and silver_order_items models and schema assertions."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate silver models and YAML schema files."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.silver_dir = os.path.join(cls.root_dir, "dbt", "models", "silver")

        cls.orders_sql = os.path.join(cls.silver_dir, "silver_orders.sql")
        cls.orders_yml = os.path.join(cls.silver_dir, "silver_orders.yml")

        cls.order_items_sql = os.path.join(cls.silver_dir, "silver_order_items.sql")
        cls.order_items_yml = os.path.join(cls.silver_dir, "silver_order_items.yml")

    def test_model_files_exist(self) -> None:
        """Verify silver_orders and silver_order_items files exist on disk."""
        self.assertTrue(os.path.exists(self.orders_sql), "silver_orders.sql must exist")
        self.assertTrue(os.path.exists(self.orders_yml), "silver_orders.yml must exist")
        self.assertTrue(
            os.path.exists(self.order_items_sql),
            "silver_order_items.sql must exist",
        )
        self.assertTrue(
            os.path.exists(self.order_items_yml),
            "silver_order_items.yml must exist",
        )

    def test_silver_orders_sql_and_schema(self) -> None:
        """Verify silver_orders SQL logic, deduplication, financial validation, and schema assertions."""
        with open(self.orders_sql, "r", encoding="utf-8") as f:
            sql = f.read()

        self.assertIn("ref('stg_orders')", sql)
        self.assertIn("alias='orders'", sql)
        self.assertIn("partition by order_id", sql)
        self.assertIn("where row_num = 1", sql)
        self.assertIn("total_amount >= 0", sql)
        self.assertIn("current_timestamp() as _transformed_at", sql)

        with open(self.orders_yml, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        models = {m.get("name"): m for m in doc.get("models", [])}
        self.assertIn("silver_orders", models)
        cols = {c.get("name"): c for c in models["silver_orders"].get("columns", [])}
        self.assertIn("order_id", cols)
        self.assertIn("customer_id", cols)
        self.assertIn("order_date", cols)
        self.assertIn("total_amount", cols)
        self.assertIn("payment_method_id", cols)
        self.assertIn("unique", cols["order_id"].get("tests", []))
        self.assertIn("not_null", cols["order_id"].get("tests", []))
        self.assertIn("not_null", cols["customer_id"].get("tests", []))
        self.assertIn("not_null", cols["total_amount"].get("tests", []))
        self.assertIn("not_null", cols["_transformed_at"].get("tests", []))

        # Foreign key relationships
        cust_rel = next(
            (
                t.get("relationships", {})
                for t in cols["customer_id"].get("tests", [])
                if isinstance(t, dict) and "relationships" in t
            ),
            None,
        )
        self.assertIsNotNone(cust_rel)
        self.assertIn("silver_customers", str(cust_rel.get("to", "")))

        pm_rel = next(
            (
                t.get("relationships", {})
                for t in cols["payment_method_id"].get("tests", [])
                if isinstance(t, dict) and "relationships" in t
            ),
            None,
        )
        self.assertIsNotNone(pm_rel)
        self.assertIn("silver_payment_methods", str(pm_rel.get("to", "")))

    def test_silver_order_items_sql_and_schema(self) -> None:
        """Verify silver_order_items SQL calculations, quantity validation, and schema assertions."""
        with open(self.order_items_sql, "r", encoding="utf-8") as f:
            sql = f.read()

        self.assertIn("ref('stg_order_items')", sql)
        self.assertIn("alias='order_items'", sql)
        self.assertIn("partition by order_item_id", sql)
        self.assertIn("where row_num = 1", sql)
        self.assertIn("line_total_amount", sql)
        self.assertIn("quantity > 0", sql)
        self.assertIn("current_timestamp() as _transformed_at", sql)

        with open(self.order_items_yml, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        models = {m.get("name"): m for m in doc.get("models", [])}
        self.assertIn("silver_order_items", models)
        cols = {
            c.get("name"): c for c in models["silver_order_items"].get("columns", [])
        }
        self.assertIn("order_item_id", cols)
        self.assertIn("order_id", cols)
        self.assertIn("product_id", cols)
        self.assertIn("quantity", cols)
        self.assertIn("line_total_amount", cols)
        self.assertIn("unique", cols["order_item_id"].get("tests", []))
        self.assertIn("not_null", cols["order_item_id"].get("tests", []))
        self.assertIn("not_null", cols["quantity"].get("tests", []))
        self.assertIn("not_null", cols["line_total_amount"].get("tests", []))
        self.assertIn("not_null", cols["_transformed_at"].get("tests", []))

        # Foreign key relationships
        ord_rel = next(
            (
                t.get("relationships", {})
                for t in cols["order_id"].get("tests", [])
                if isinstance(t, dict) and "relationships" in t
            ),
            None,
        )
        self.assertIsNotNone(ord_rel)
        self.assertIn("silver_orders", str(ord_rel.get("to", "")))

        prod_rel = next(
            (
                t.get("relationships", {})
                for t in cols["product_id"].get("tests", [])
                if isinstance(t, dict) and "relationships" in t
            ),
            None,
        )
        self.assertIsNotNone(prod_rel)
        self.assertIn("silver_products", str(prod_rel.get("to", "")))


if __name__ == "__main__":
    unittest.main()
