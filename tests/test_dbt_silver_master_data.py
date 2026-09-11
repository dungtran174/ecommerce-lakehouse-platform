"""Unit tests for conformed Silver master data dbt models (brands, categories, payment methods)."""

from __future__ import annotations

import os
import unittest

import yaml


class TestDbtSilverMasterData(unittest.TestCase):
    """Test suite validating silver_brands, silver_categories, and silver_payment_methods."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate silver models and YAML schema files."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.silver_dir = os.path.join(cls.root_dir, "dbt", "models", "silver")

        cls.brands_sql = os.path.join(cls.silver_dir, "silver_brands.sql")
        cls.brands_yml = os.path.join(cls.silver_dir, "silver_brands.yml")

        cls.categories_sql = os.path.join(cls.silver_dir, "silver_categories.sql")
        cls.categories_yml = os.path.join(cls.silver_dir, "silver_categories.yml")

        cls.payments_sql = os.path.join(cls.silver_dir, "silver_payment_methods.sql")
        cls.payments_yml = os.path.join(cls.silver_dir, "silver_payment_methods.yml")

    def test_model_files_exist(self) -> None:
        """Verify all SQL models and YAML schema files exist on disk."""
        self.assertTrue(os.path.exists(self.brands_sql), "silver_brands.sql must exist")
        self.assertTrue(os.path.exists(self.brands_yml), "silver_brands.yml must exist")
        self.assertTrue(
            os.path.exists(self.categories_sql),
            "silver_categories.sql must exist",
        )
        self.assertTrue(
            os.path.exists(self.categories_yml),
            "silver_categories.yml must exist",
        )
        self.assertTrue(
            os.path.exists(self.payments_sql),
            "silver_payment_methods.sql must exist",
        )
        self.assertTrue(
            os.path.exists(self.payments_yml),
            "silver_payment_methods.yml must exist",
        )

    def test_silver_brands_sql_and_schema(self) -> None:
        """Verify silver_brands SQL logic, deduplication window, trimming, and schema assertions."""
        with open(self.brands_sql, "r", encoding="utf-8") as f:
            sql = f.read()

        self.assertIn("ref('stg_brands')", sql)
        self.assertIn("alias='brands'", sql)
        self.assertIn("partition by brand_id", sql)
        self.assertIn("where row_num = 1", sql)
        self.assertIn("coalesce(trim(brand_origin), 'Unknown')", sql)
        self.assertIn("current_timestamp() as _transformed_at", sql)

        with open(self.brands_yml, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        models = {m.get("name"): m for m in doc.get("models", [])}
        self.assertIn("silver_brands", models)
        cols = {c.get("name"): c for c in models["silver_brands"].get("columns", [])}
        self.assertIn("brand_id", cols)
        self.assertIn("brand_name", cols)
        self.assertIn("brand_origin", cols)
        self.assertIn("unique", cols["brand_id"].get("tests", []))
        self.assertIn("not_null", cols["brand_id"].get("tests", []))
        self.assertIn("not_null", cols["brand_name"].get("tests", []))
        self.assertIn("not_null", cols["brand_origin"].get("tests", []))
        self.assertIn("not_null", cols["_transformed_at"].get("tests", []))

    def test_silver_categories_sql_and_schema(self) -> None:
        """Verify silver_categories SQL logic, deduplication, trimming, and schema assertions."""
        with open(self.categories_sql, "r", encoding="utf-8") as f:
            sql = f.read()

        self.assertIn("ref('stg_categories')", sql)
        self.assertIn("alias='category'", sql)
        self.assertIn("partition by category_id", sql)
        self.assertIn("where row_num = 1", sql)
        self.assertIn("current_timestamp() as _transformed_at", sql)

        with open(self.categories_yml, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        models = {m.get("name"): m for m in doc.get("models", [])}
        self.assertIn("silver_categories", models)
        cols = {
            c.get("name"): c for c in models["silver_categories"].get("columns", [])
        }
        self.assertIn("category_id", cols)
        self.assertIn("category_display_name", cols)
        self.assertIn("unique", cols["category_id"].get("tests", []))
        self.assertIn("not_null", cols["category_id"].get("tests", []))
        self.assertIn("not_null", cols["category_display_name"].get("tests", []))
        self.assertIn("not_null", cols["_transformed_at"].get("tests", []))

    def test_silver_payment_methods_sql_and_schema(self) -> None:
        """Verify silver_payment_methods SQL logic, deduplication, and schema assertions."""
        with open(self.payments_sql, "r", encoding="utf-8") as f:
            sql = f.read()

        self.assertIn("ref('stg_payment_methods')", sql)
        self.assertIn("alias='payment_method'", sql)
        self.assertIn("partition by payment_method_id", sql)
        self.assertIn("where row_num = 1", sql)
        self.assertIn("current_timestamp() as _transformed_at", sql)

        with open(self.payments_yml, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        models = {m.get("name"): m for m in doc.get("models", [])}
        self.assertIn("silver_payment_methods", models)
        cols = {
            c.get("name"): c
            for c in models["silver_payment_methods"].get("columns", [])
        }
        self.assertIn("payment_method_id", cols)
        self.assertIn("display_name", cols)
        self.assertIn("type", cols)
        self.assertIn("unique", cols["payment_method_id"].get("tests", []))
        self.assertIn("not_null", cols["payment_method_id"].get("tests", []))
        self.assertIn("not_null", cols["display_name"].get("tests", []))
        self.assertIn("not_null", cols["type"].get("tests", []))
        self.assertIn("not_null", cols["_transformed_at"].get("tests", []))


if __name__ == "__main__":
    unittest.main()
