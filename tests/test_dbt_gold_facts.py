"""Unit tests for Gold fact tables (fact_order, fact_order_items)."""

from __future__ import annotations

import os
import unittest

import yaml


class TestDbtGoldFacts(unittest.TestCase):
    """Test suite validating Gold Kimball Galaxy Schema fact models and schema assertions."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate Gold fact models and YAML schema files."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.gold_dir = os.path.join(cls.root_dir, "dbt", "models", "gold", "sale_mart")

        cls.order_sql = os.path.join(cls.gold_dir, "fact_order.sql")
        cls.order_yml = os.path.join(cls.gold_dir, "fact_order.yml")

        cls.items_sql = os.path.join(cls.gold_dir, "fact_order_items.sql")
        cls.items_yml = os.path.join(cls.gold_dir, "fact_order_items.yml")

    def test_model_files_exist(self) -> None:
        """Verify all fact SQL models and YAML schema files exist on disk."""
        self.assertTrue(os.path.exists(self.order_sql), "fact_order.sql must exist")
        self.assertTrue(os.path.exists(self.order_yml), "fact_order.yml must exist")
        self.assertTrue(
            os.path.exists(self.items_sql), "fact_order_items.sql must exist"
        )
        self.assertTrue(
            os.path.exists(self.items_yml), "fact_order_items.yml must exist"
        )

    def test_fact_order_sql_and_schema(self) -> None:
        """Verify fact_order SQL aggregation logic and YAML schema assertions."""
        with open(self.order_sql, "r", encoding="utf-8") as f:
            sql = f.read()

        self.assertIn("ref('silver_orders')", sql)
        self.assertIn("ref('silver_order_items')", sql)
        self.assertIn("order_id", sql)
        self.assertIn("customer_key", sql)
        self.assertIn("payment_method_key", sql)
        self.assertIn("date_key", sql)
        self.assertIn("quantity", sql)
        self.assertIn("price", sql)
        self.assertIn("discount_amt", sql)
        self.assertIn("sub_total", sql)
        self.assertIn("current_timestamp() as _created_at", sql)

        with open(self.order_yml, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        models = {m.get("name"): m for m in doc.get("models", [])}
        self.assertIn("fact_order", models)
        cols = {c.get("name"): c for c in models["fact_order"].get("columns", [])}

        expected_cols = [
            "order_id",
            "customer_key",
            "payment_method_key",
            "date_key",
            "quantity",
            "price",
            "discount_amt",
            "sub_total",
            "_created_at",
        ]
        for col_name in expected_cols:
            self.assertIn(col_name, cols)

        self.assertIn("unique", cols["order_id"].get("tests", []))
        self.assertIn("not_null", cols["order_id"].get("tests", []))
        self.assertIn("not_null", cols["customer_key"].get("tests", []))
        self.assertIn("not_null", cols["sub_total"].get("tests", []))

        # Check relationships test
        has_cust_rel = any(
            isinstance(t, dict) and "relationships" in t
            for t in cols["customer_key"].get("tests", [])
        )
        self.assertTrue(has_cust_rel, "customer_key must have relationships test")

        has_date_rel = any(
            isinstance(t, dict) and "relationships" in t
            for t in cols["date_key"].get("tests", [])
        )
        self.assertTrue(has_date_rel, "date_key must have relationships test")

    def test_fact_order_items_sql_and_schema(self) -> None:
        """Verify fact_order_items SQL line-grain joins and YAML schema assertions."""
        with open(self.items_sql, "r", encoding="utf-8") as f:
            sql = f.read()

        self.assertIn("ref('silver_order_items')", sql)
        self.assertIn("ref('silver_orders')", sql)
        self.assertIn("order_item_id", sql)
        self.assertIn("order_id", sql)
        self.assertIn("customer_key", sql)
        self.assertIn("product_key", sql)
        self.assertIn("payment_method_key", sql)
        self.assertIn("order_date_key", sql)
        self.assertIn("quantity", sql)
        self.assertIn("price", sql)
        self.assertIn("discount_amt", sql)
        self.assertIn("sub_total", sql)
        self.assertIn("current_timestamp() as _created_at", sql)

        with open(self.items_yml, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        models = {m.get("name"): m for m in doc.get("models", [])}
        self.assertIn("fact_order_items", models)
        cols = {c.get("name"): c for c in models["fact_order_items"].get("columns", [])}

        expected_cols = [
            "order_item_id",
            "order_id",
            "customer_key",
            "product_key",
            "payment_method_key",
            "order_date_key",
            "quantity",
            "price",
            "discount_amt",
            "sub_total",
            "_created_at",
        ]
        for col_name in expected_cols:
            self.assertIn(col_name, cols)

        self.assertIn("unique", cols["order_item_id"].get("tests", []))
        self.assertIn("not_null", cols["order_item_id"].get("tests", []))
        self.assertIn("not_null", cols["order_id"].get("tests", []))
        self.assertIn("not_null", cols["product_key"].get("tests", []))
        self.assertIn("not_null", cols["sub_total"].get("tests", []))

        # Check relationships tests
        has_prod_rel = any(
            isinstance(t, dict) and "relationships" in t
            for t in cols["product_key"].get("tests", [])
        )
        self.assertTrue(has_prod_rel, "product_key must have relationships test")

        has_order_rel = any(
            isinstance(t, dict) and "relationships" in t
            for t in cols["order_id"].get("tests", [])
        )
        self.assertTrue(has_order_rel, "order_id must have relationships test")


if __name__ == "__main__":
    unittest.main()
