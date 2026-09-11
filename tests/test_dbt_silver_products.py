"""Unit tests for conformed Silver products catalog dbt model."""

from __future__ import annotations

import os
import unittest

import yaml


class TestDbtSilverProducts(unittest.TestCase):
    """Test suite validating silver_products SQL transformations, price validation, and schema assertions."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate silver model and YAML schema files."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.silver_dir = os.path.join(cls.root_dir, "dbt", "models", "silver")

        cls.products_sql = os.path.join(cls.silver_dir, "silver_products.sql")
        cls.products_yml = os.path.join(cls.silver_dir, "silver_products.yml")

    def test_model_files_exist(self) -> None:
        """Verify silver_products SQL model and YAML schema files exist on disk."""
        self.assertTrue(
            os.path.exists(self.products_sql), "silver_products.sql must exist"
        )
        self.assertTrue(
            os.path.exists(self.products_yml), "silver_products.yml must exist"
        )

    def test_silver_products_sql_logic(self) -> None:
        """Verify stg_products reference, deduplication window, price filter, and trimming."""
        with open(self.products_sql, "r", encoding="utf-8") as f:
            sql = f.read()

        # Upstream lineage reference
        self.assertIn("ref('stg_products')", sql)

        # Delta table alias
        self.assertIn("alias='products'", sql)

        # Deduplication logic
        self.assertIn("partition by product_id", sql)
        self.assertIn("order by updated_at desc, created_at desc", sql)
        self.assertIn("where row_num = 1", sql)

        # Price validation filter
        self.assertIn("price > 0", sql)

        # String cleaning
        self.assertIn("trim(product_name) as product_name", sql)
        self.assertIn("trim(brand_id) as brand_id", sql)

        # Transformation audit column
        self.assertIn("current_timestamp() as _transformed_at", sql)

    def test_silver_products_yaml_schema(self) -> None:
        """Verify silver_products schema assertions, primary key constraints, and foreign key relationships."""
        with open(self.products_yml, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        self.assertIsInstance(doc, dict)
        self.assertEqual(doc.get("version"), 2)

        models = {m.get("name"): m for m in doc.get("models", [])}
        self.assertIn("silver_products", models)

        cols = {c.get("name"): c for c in models["silver_products"].get("columns", [])}

        # Expected columns check
        expected_cols = [
            "product_id",
            "product_name",
            "product_description",
            "price",
            "category_id",
            "brand_id",
            "created_at",
            "updated_at",
            "_transformed_at",
        ]
        for col_name in expected_cols:
            self.assertIn(
                col_name,
                cols,
                f"Column '{col_name}' must be defined in silver_products.yml",
            )

        # Primary key tests
        self.assertIn("unique", cols["product_id"].get("tests", []))
        self.assertIn("not_null", cols["product_id"].get("tests", []))

        # Not null tests
        self.assertIn("not_null", cols["product_name"].get("tests", []))
        self.assertIn("not_null", cols["price"].get("tests", []))
        self.assertIn("not_null", cols["category_id"].get("tests", []))
        self.assertIn("not_null", cols["brand_id"].get("tests", []))
        self.assertIn("not_null", cols["created_at"].get("tests", []))
        self.assertIn("not_null", cols["_transformed_at"].get("tests", []))

        # Relationship tests
        cat_rel = next(
            (
                t.get("relationships", {})
                for t in cols["category_id"].get("tests", [])
                if isinstance(t, dict) and "relationships" in t
            ),
            None,
        )
        self.assertIsNotNone(cat_rel)
        self.assertIn("stg_categories", str(cat_rel.get("to", "")))

        brand_rel = next(
            (
                t.get("relationships", {})
                for t in cols["brand_id"].get("tests", [])
                if isinstance(t, dict) and "relationships" in t
            ),
            None,
        )
        self.assertIsNotNone(brand_rel)
        self.assertIn("stg_brands", str(brand_rel.get("to", "")))


if __name__ == "__main__":
    unittest.main()
