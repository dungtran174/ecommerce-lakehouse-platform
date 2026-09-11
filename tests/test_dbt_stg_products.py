"""Unit tests for dbt staging model stg_products and schema definitions."""

from __future__ import annotations

import os
import unittest

import yaml


class TestDbtStgProducts(unittest.TestCase):
    """Test suite validating stg_products staging model SQL logic and schema documentation."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate stg_products model and YAML schema files."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.staging_dir = os.path.join(cls.root_dir, "dbt", "models", "staging")

        cls.model_sql_file = os.path.join(cls.staging_dir, "stg_products.sql")
        cls.model_yml_file = os.path.join(cls.staging_dir, "stg_products.yml")

    def test_model_files_exist(self) -> None:
        """Verify stg_products SQL and YAML specification files exist on disk."""
        self.assertTrue(
            os.path.exists(self.model_sql_file), "stg_products.sql must exist"
        )
        self.assertTrue(
            os.path.exists(self.model_yml_file), "stg_products.yml must exist"
        )

    def test_model_sql_logic(self) -> None:
        """Verify SQL model references source correctly and applies proper transformations."""
        with open(self.model_sql_file, "r", encoding="utf-8") as f:
            sql = f.read()

        # Check source dependency
        self.assertIn("source('mysql_oltp', 'products_snapshot')", sql)

        # Check column transformations and data types
        self.assertIn("cast(product_id as int)", sql)
        self.assertIn("trim(cast(product_name as string))", sql)
        self.assertIn("trim(cast(product_description as string))", sql)
        self.assertIn("cast(price as double)", sql)
        self.assertIn("cast(category_id as int)", sql)
        self.assertIn("trim(cast(brand_id as string))", sql)
        self.assertIn("cast(created_at as timestamp)", sql)
        self.assertIn("cast(updated_at as timestamp)", sql)
        self.assertIn("current_timestamp() as _ingested_at", sql)

    def test_model_yaml_schema_validity(self) -> None:
        """Verify stg_products.yml is valid YAML and defines expected schema tests."""
        with open(self.model_yml_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        self.assertIsInstance(doc, dict)
        self.assertEqual(doc.get("version"), 2)

        models = {m.get("name"): m for m in doc.get("models", [])}
        self.assertIn("stg_products", models)

        product_model = models["stg_products"]
        columns = {c.get("name"): c for c in product_model.get("columns", [])}

        required_columns = [
            "product_id",
            "product_name",
            "product_description",
            "price",
            "category_id",
            "brand_id",
            "created_at",
            "updated_at",
            "_ingested_at",
        ]
        for col in required_columns:
            self.assertIn(
                col, columns, f"Column '{col}' must be documented in stg_products.yml"
            )

        # Check primary key tests on product_id
        prod_id_tests = columns["product_id"].get("tests", [])
        self.assertIn("unique", prod_id_tests)
        self.assertIn("not_null", prod_id_tests)


if __name__ == "__main__":
    unittest.main()
