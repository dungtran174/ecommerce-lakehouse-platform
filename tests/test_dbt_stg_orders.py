"""Unit tests for dbt staging models: stg_orders and stg_order_items."""

from __future__ import annotations

import os
import unittest

import yaml


class TestDbtStgOrders(unittest.TestCase):
    """Test suite validating orders and order items staging models and schema specifications."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate staging models and YAML schema files."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.staging_dir = os.path.join(cls.root_dir, "dbt", "models", "staging")

        cls.orders_sql = os.path.join(cls.staging_dir, "stg_orders.sql")
        cls.orders_yml = os.path.join(cls.staging_dir, "stg_orders.yml")

        cls.order_items_sql = os.path.join(cls.staging_dir, "stg_order_items.sql")
        cls.order_items_yml = os.path.join(cls.staging_dir, "stg_order_items.yml")

    def test_model_files_exist(self) -> None:
        """Verify orders and order items SQL models and YAML schema files exist on disk."""
        self.assertTrue(os.path.exists(self.orders_sql), "stg_orders.sql must exist")
        self.assertTrue(os.path.exists(self.orders_yml), "stg_orders.yml must exist")
        self.assertTrue(
            os.path.exists(self.order_items_sql), "stg_order_items.sql must exist"
        )
        self.assertTrue(
            os.path.exists(self.order_items_yml), "stg_order_items.yml must exist"
        )

    def test_orders_model_logic_and_schema(self) -> None:
        """Verify stg_orders SQL source, incremental logic, transformations, and schema assertions."""
        with open(self.orders_sql, "r", encoding="utf-8") as f:
            sql = f.read()

        self.assertIn("source('mysql_oltp', 'orders_snapshot')", sql)
        self.assertIn("cast(order_id as int) as order_id", sql)
        self.assertIn("cast(customer_id as int) as customer_id", sql)
        self.assertIn("cast(order_date as timestamp) as order_timestamp", sql)
        self.assertIn("cast(order_date as date) as order_date", sql)
        self.assertIn("cast(total_amount as double) as total_amount", sql)
        self.assertIn("cast(payment_method_id as int) as payment_method_id", sql)
        self.assertIn("current_timestamp() as _ingested_at", sql)

        # Check incremental logic
        self.assertIn("is_incremental()", sql)
        self.assertIn("updated_at > (select max(updated_at)", sql)

        with open(self.orders_yml, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        models = {m.get("name"): m for m in doc.get("models", [])}
        self.assertIn("stg_orders", models)
        cols = {c.get("name"): c for c in models["stg_orders"].get("columns", [])}
        self.assertIn("order_id", cols)
        self.assertIn("customer_id", cols)
        self.assertIn("order_timestamp", cols)
        self.assertIn("order_date", cols)
        self.assertIn("total_amount", cols)
        self.assertIn("unique", cols["order_id"].get("tests", []))
        self.assertIn("not_null", cols["order_id"].get("tests", []))

    def test_order_items_model_logic_and_schema(self) -> None:
        """Verify stg_order_items SQL source, incremental logic, calculations, and schema assertions."""
        with open(self.order_items_sql, "r", encoding="utf-8") as f:
            sql = f.read()

        self.assertIn("source('mysql_oltp', 'order_items_snapshot')", sql)
        self.assertIn("cast(order_item_id as int) as order_item_id", sql)
        self.assertIn("cast(order_id as int) as order_id", sql)
        self.assertIn("cast(product_id as int) as product_id", sql)
        self.assertIn("cast(quantity as int) as quantity", sql)
        self.assertIn("cast(price as double) as price", sql)
        self.assertIn("coalesce(cast(discount as double), 0.0) as discount", sql)
        self.assertIn("line_total_amount", sql)
        self.assertIn("current_timestamp() as _ingested_at", sql)

        # Check incremental logic
        self.assertIn("is_incremental()", sql)
        self.assertIn("order_item_id > (select max(order_item_id)", sql)

        with open(self.order_items_yml, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        models = {m.get("name"): m for m in doc.get("models", [])}
        self.assertIn("stg_order_items", models)
        cols = {c.get("name"): c for c in models["stg_order_items"].get("columns", [])}
        self.assertIn("order_item_id", cols)
        self.assertIn("order_id", cols)
        self.assertIn("product_id", cols)
        self.assertIn("quantity", cols)
        self.assertIn("line_total_amount", cols)
        self.assertIn("unique", cols["order_item_id"].get("tests", []))
        self.assertIn("not_null", cols["order_item_id"].get("tests", []))


if __name__ == "__main__":
    unittest.main()
