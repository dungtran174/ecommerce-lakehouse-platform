"""Unit tests for dbt staging models: stg_brands, stg_categories, and stg_payment_methods."""

from __future__ import annotations

import os
import unittest

import yaml


class TestDbtStgMasterData(unittest.TestCase):
    """Test suite validating master data staging models and schema specifications."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate staging models and YAML schema files."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.staging_dir = os.path.join(cls.root_dir, "dbt", "models", "staging")

        cls.brands_sql = os.path.join(cls.staging_dir, "stg_brands.sql")
        cls.brands_yml = os.path.join(cls.staging_dir, "stg_brands.yml")

        cls.categories_sql = os.path.join(cls.staging_dir, "stg_categories.sql")
        cls.categories_yml = os.path.join(cls.staging_dir, "stg_categories.yml")

        cls.payment_methods_sql = os.path.join(
            cls.staging_dir, "stg_payment_methods.sql"
        )
        cls.payment_methods_yml = os.path.join(
            cls.staging_dir, "stg_payment_methods.yml"
        )

    def test_model_files_exist(self) -> None:
        """Verify master data SQL models and YAML schema files exist on disk."""
        self.assertTrue(os.path.exists(self.brands_sql), "stg_brands.sql must exist")
        self.assertTrue(os.path.exists(self.brands_yml), "stg_brands.yml must exist")
        self.assertTrue(
            os.path.exists(self.categories_sql), "stg_categories.sql must exist"
        )
        self.assertTrue(
            os.path.exists(self.categories_yml), "stg_categories.yml must exist"
        )
        self.assertTrue(
            os.path.exists(self.payment_methods_sql),
            "stg_payment_methods.sql must exist",
        )
        self.assertTrue(
            os.path.exists(self.payment_methods_yml),
            "stg_payment_methods.yml must exist",
        )

    def test_brands_model_logic_and_schema(self) -> None:
        """Verify stg_brands SQL source, transformations, and schema assertions."""
        with open(self.brands_sql, "r", encoding="utf-8") as f:
            sql = f.read()

        self.assertIn("source('mysql_oltp', 'brands_snapshot')", sql)
        self.assertIn("trim(cast(brand_id as string)) as brand_id", sql)
        self.assertIn("trim(cast(brand_name as string)) as brand_name", sql)
        self.assertIn("trim(cast(brand_origin as string)) as brand_origin", sql)
        self.assertIn("current_timestamp() as _ingested_at", sql)

        with open(self.brands_yml, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        models = {m.get("name"): m for m in doc.get("models", [])}
        self.assertIn("stg_brands", models)
        cols = {c.get("name"): c for c in models["stg_brands"].get("columns", [])}
        self.assertIn("brand_id", cols)
        self.assertIn("brand_name", cols)
        self.assertIn("brand_origin", cols)
        self.assertIn("unique", cols["brand_id"].get("tests", []))
        self.assertIn("not_null", cols["brand_id"].get("tests", []))

    def test_categories_model_logic_and_schema(self) -> None:
        """Verify stg_categories SQL source, transformations, and schema assertions."""
        with open(self.categories_sql, "r", encoding="utf-8") as f:
            sql = f.read()

        self.assertIn("source('mysql_oltp', 'category_snapshot')", sql)
        self.assertIn("cast(category_id as int) as category_id", sql)
        self.assertIn(
            "trim(cast(category_display_name as string)) as category_display_name",
            sql,
        )
        self.assertIn(
            "trim(cast(category_description as string)) as category_description",
            sql,
        )
        self.assertIn("current_timestamp() as _ingested_at", sql)

        with open(self.categories_yml, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        models = {m.get("name"): m for m in doc.get("models", [])}
        self.assertIn("stg_categories", models)
        cols = {c.get("name"): c for c in models["stg_categories"].get("columns", [])}
        self.assertIn("category_id", cols)
        self.assertIn("category_display_name", cols)
        self.assertIn("unique", cols["category_id"].get("tests", []))
        self.assertIn("not_null", cols["category_id"].get("tests", []))

    def test_payment_methods_model_logic_and_schema(self) -> None:
        """Verify stg_payment_methods SQL source, transformations, and schema assertions."""
        with open(self.payment_methods_sql, "r", encoding="utf-8") as f:
            sql = f.read()

        self.assertIn("source('mysql_oltp', 'payment_method_snapshot')", sql)
        self.assertIn("cast(payment_method_id as int) as payment_method_id", sql)
        self.assertIn("trim(cast(display_name as string)) as display_name", sql)
        self.assertIn("trim(cast(type as string)) as type", sql)
        self.assertIn("trim(cast(provider as string)) as provider", sql)
        self.assertIn("current_timestamp() as _ingested_at", sql)

        with open(self.payment_methods_yml, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        models = {m.get("name"): m for m in doc.get("models", [])}
        self.assertIn("stg_payment_methods", models)
        cols = {
            c.get("name"): c for c in models["stg_payment_methods"].get("columns", [])
        }
        self.assertIn("payment_method_id", cols)
        self.assertIn("display_name", cols)
        self.assertIn("type", cols)
        self.assertIn("unique", cols["payment_method_id"].get("tests", []))
        self.assertIn("not_null", cols["payment_method_id"].get("tests", []))


if __name__ == "__main__":
    unittest.main()
