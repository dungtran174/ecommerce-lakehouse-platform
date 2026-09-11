"""Unit tests for Gold dimension tables (dim_customer, dim_product, dim_payment_method)."""

from __future__ import annotations

import os
import unittest

import yaml


class TestDbtGoldDimensions(unittest.TestCase):
    """Test suite validating Gold Kimball Galaxy Schema dimension models and schema assertions."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate Gold dimension models and YAML schema files."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.gold_dir = os.path.join(cls.root_dir, "dbt", "models", "gold", "sale_mart")

        cls.cust_sql = os.path.join(cls.gold_dir, "dim_customer.sql")
        cls.cust_yml = os.path.join(cls.gold_dir, "dim_customer.yml")

        cls.prod_sql = os.path.join(cls.gold_dir, "dim_product.sql")
        cls.prod_yml = os.path.join(cls.gold_dir, "dim_product.yml")

        cls.pay_sql = os.path.join(cls.gold_dir, "dim_payment_method.sql")
        cls.pay_yml = os.path.join(cls.gold_dir, "dim_payment_method.yml")

    def test_model_files_exist(self) -> None:
        """Verify all dimension SQL models and YAML schema files exist on disk."""
        self.assertTrue(os.path.exists(self.cust_sql), "dim_customer.sql must exist")
        self.assertTrue(os.path.exists(self.cust_yml), "dim_customer.yml must exist")
        self.assertTrue(os.path.exists(self.prod_sql), "dim_product.sql must exist")
        self.assertTrue(os.path.exists(self.prod_yml), "dim_product.yml must exist")
        self.assertTrue(
            os.path.exists(self.pay_sql), "dim_payment_method.sql must exist"
        )
        self.assertTrue(
            os.path.exists(self.pay_yml), "dim_payment_method.yml must exist"
        )

    def test_dim_customer_sql_and_schema(self) -> None:
        """Verify dim_customer SQL logic, demographic attributes, and schema assertions."""
        with open(self.cust_sql, "r", encoding="utf-8") as f:
            sql = f.read()

        self.assertIn("ref('silver_customers')", sql)
        self.assertIn("customer_id", sql)
        self.assertIn("first_name", sql)
        self.assertIn("last_name", sql)
        self.assertIn("gender", sql)
        self.assertIn("tire", sql)
        self.assertIn("address", sql)
        self.assertIn("current_timestamp() as _created_at", sql)

        with open(self.cust_yml, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        models = {m.get("name"): m for m in doc.get("models", [])}
        self.assertIn("dim_customer", models)
        cols = {c.get("name"): c for c in models["dim_customer"].get("columns", [])}
        self.assertIn("customer_id", cols)
        self.assertIn("first_name", cols)
        self.assertIn("tire", cols)
        self.assertIn("unique", cols["customer_id"].get("tests", []))
        self.assertIn("not_null", cols["customer_id"].get("tests", []))
        self.assertIn("not_null", cols["first_name"].get("tests", []))
        self.assertIn("not_null", cols["tire"].get("tests", []))
        self.assertIn("not_null", cols["_created_at"].get("tests", []))

    def test_dim_product_sql_and_schema(self) -> None:
        """Verify dim_product denormalization joins, unit price, and schema assertions."""
        with open(self.prod_sql, "r", encoding="utf-8") as f:
            sql = f.read()

        self.assertIn("ref('silver_products')", sql)
        self.assertIn("ref('silver_categories')", sql)
        self.assertIn("ref('silver_brands')", sql)
        self.assertIn("unit_price", sql)
        self.assertIn("category", sql)
        self.assertIn("brand_name", sql)
        self.assertIn("brand_origin", sql)
        self.assertIn("current_timestamp() as _created_at", sql)

        with open(self.prod_yml, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        models = {m.get("name"): m for m in doc.get("models", [])}
        self.assertIn("dim_product", models)
        cols = {c.get("name"): c for c in models["dim_product"].get("columns", [])}
        self.assertIn("product_id", cols)
        self.assertIn("product_name", cols)
        self.assertIn("unit_price", cols)
        self.assertIn("category", cols)
        self.assertIn("brand_name", cols)
        self.assertIn("unique", cols["product_id"].get("tests", []))
        self.assertIn("not_null", cols["product_id"].get("tests", []))
        self.assertIn("not_null", cols["product_name"].get("tests", []))
        self.assertIn("not_null", cols["unit_price"].get("tests", []))
        self.assertIn("not_null", cols["category"].get("tests", []))
        self.assertIn("not_null", cols["brand_name"].get("tests", []))
        self.assertIn("not_null", cols["_created_at"].get("tests", []))

    def test_dim_payment_method_sql_and_schema(self) -> None:
        """Verify dim_payment_method SCD Type 2 tracking fields and schema assertions."""
        with open(self.pay_sql, "r", encoding="utf-8") as f:
            sql = f.read()

        self.assertIn("ref('silver_payment_methods')", sql)
        self.assertIn("effective_start_date", sql)
        self.assertIn("effective_end_date", sql)
        self.assertIn("is_current", sql)
        self.assertIn("current_timestamp() as _created_at", sql)

        with open(self.pay_yml, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        models = {m.get("name"): m for m in doc.get("models", [])}
        self.assertIn("dim_payment_method", models)
        cols = {
            c.get("name"): c for c in models["dim_payment_method"].get("columns", [])
        }
        self.assertIn("payment_method_id", cols)
        self.assertIn("display_name", cols)
        self.assertIn("type", cols)
        self.assertIn("effective_start_date", cols)
        self.assertIn("is_current", cols)
        self.assertIn("unique", cols["payment_method_id"].get("tests", []))
        self.assertIn("not_null", cols["payment_method_id"].get("tests", []))
        self.assertIn("not_null", cols["display_name"].get("tests", []))
        self.assertIn("not_null", cols["effective_start_date"].get("tests", []))
        self.assertIn("not_null", cols["is_current"].get("tests", []))
        self.assertIn("not_null", cols["_created_at"].get("tests", []))


if __name__ == "__main__":
    unittest.main()
