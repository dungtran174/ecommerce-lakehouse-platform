"""Unit tests for dbt source configurations defining raw Bronze Lakehouse inputs."""

from __future__ import annotations

import os
import unittest

import yaml


class TestDbtSources(unittest.TestCase):
    """Test suite validating dbt source definitions for MySQL and Clickstream."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate sources.yml configuration file."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.sources_file = os.path.join(
            cls.root_dir, "dbt", "models", "staging", "sources.yml"
        )

    def test_sources_file_exists(self) -> None:
        """Verify sources.yml file exists on disk."""
        self.assertTrue(os.path.exists(self.sources_file), "sources.yml must exist")

    def test_sources_yaml_validity(self) -> None:
        """Verify sources.yml parses as valid YAML and version is 2."""
        with open(self.sources_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        self.assertIsInstance(doc, dict)
        self.assertEqual(doc.get("version"), 2)
        self.assertIn("sources", doc)
        self.assertIsInstance(doc["sources"], list)

    def test_mysql_oltp_source_definition(self) -> None:
        """Verify mysql_oltp source configuration, tables, and column metadata."""
        with open(self.sources_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        sources_by_name = {s.get("name"): s for s in doc.get("sources", [])}
        self.assertIn("mysql_oltp", sources_by_name)

        mysql_source = sources_by_name["mysql_oltp"]
        self.assertEqual(mysql_source.get("schema"), "bronze")
        self.assertEqual(mysql_source.get("database"), "lakehouse")

        tables = {t.get("name"): t for t in mysql_source.get("tables", [])}
        required_tables = [
            "customers_snapshot",
            "products_snapshot",
            "brands_snapshot",
            "category_snapshot",
            "payment_method_snapshot",
            "orders_snapshot",
            "orders",
            "order_items_snapshot",
            "order_items",
        ]
        for tbl in required_tables:
            self.assertIn(tbl, tables, f"Table '{tbl}' must exist in mysql_oltp source")

        # Column assertions for customers
        cust_cols = [
            c.get("name") for c in tables["customers_snapshot"].get("columns", [])
        ]
        self.assertIn("customer_id", cust_cols)
        self.assertIn("email", cust_cols)
        self.assertIn("tire", cust_cols)
        self.assertIn("created_at", cust_cols)

        # Column assertions for products
        prod_cols = [
            c.get("name") for c in tables["products_snapshot"].get("columns", [])
        ]
        self.assertIn("product_id", prod_cols)
        self.assertIn("price", prod_cols)
        self.assertIn("category_id", prod_cols)
        self.assertIn("brand_id", prod_cols)

        # Column assertions for orders
        order_cols = [
            c.get("name") for c in tables["orders_snapshot"].get("columns", [])
        ]
        self.assertIn("order_id", order_cols)
        self.assertIn("customer_id", order_cols)
        self.assertIn("total_amount", order_cols)

        # Column assertions for order_items
        item_cols = [
            c.get("name") for c in tables["order_items_snapshot"].get("columns", [])
        ]
        self.assertIn("order_item_id", item_cols)
        self.assertIn("quantity", item_cols)
        self.assertIn("price", item_cols)

    def test_clickstream_source_definition(self) -> None:
        """Verify clickstream source configuration, event tables, and JSON columns."""
        with open(self.sources_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        sources_by_name = {s.get("name"): s for s in doc.get("sources", [])}
        self.assertIn("clickstream", sources_by_name)

        clickstream_source = sources_by_name["clickstream"]
        self.assertEqual(clickstream_source.get("schema"), "bronze")
        self.assertEqual(clickstream_source.get("database"), "lakehouse")

        tables = {t.get("name"): t for t in clickstream_source.get("tables", [])}
        self.assertIn("clickstream_events", tables)
        self.assertIn("events", tables)

        event_cols = [
            c.get("name") for c in tables["clickstream_events"].get("columns", [])
        ]
        required_event_cols = [
            "event_id",
            "timestamp",
            "user_id",
            "user_segment",
            "device",
            "location",
            "actions",
            "session_metrics",
            "ingest_date",
        ]
        for col in required_event_cols:
            self.assertIn(
                col, event_cols, f"Column '{col}' must exist in clickstream_events"
            )


if __name__ == "__main__":
    unittest.main()
