"""Unit tests for conformed Silver customer profiles dbt model."""

from __future__ import annotations

import os
import unittest

import yaml


class TestDbtSilverCustomers(unittest.TestCase):
    """Test suite validating silver_customers SQL transformations, PII sanitization, and schema assertions."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate silver model and YAML schema files."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.silver_dir = os.path.join(cls.root_dir, "dbt", "models", "silver")

        cls.customers_sql = os.path.join(cls.silver_dir, "silver_customers.sql")
        cls.customers_yml = os.path.join(cls.silver_dir, "silver_customers.yml")

    def test_model_files_exist(self) -> None:
        """Verify silver_customers SQL model and YAML schema files exist on disk."""
        self.assertTrue(
            os.path.exists(self.customers_sql), "silver_customers.sql must exist"
        )
        self.assertTrue(
            os.path.exists(self.customers_yml), "silver_customers.yml must exist"
        )

    def test_silver_customers_sql_logic(self) -> None:
        """Verify stg_customers reference, deduplication window, PII sanitization, and tier normalization."""
        with open(self.customers_sql, "r", encoding="utf-8") as f:
            sql = f.read()

        # Upstream lineage reference
        self.assertIn("ref('stg_customers')", sql)

        # Delta table alias
        self.assertIn("alias='customer'", sql)

        # Deduplication logic
        self.assertIn("partition by customer_id", sql)
        self.assertIn("order by updated_at desc, created_at desc", sql)
        self.assertIn("where row_num = 1", sql)

        # PII Sanitization
        self.assertIn("lower(email) as email", sql)
        self.assertIn("regexp_replace(phone_number, '[^0-9]', '')", sql)

        # Standardized gender
        self.assertIn("'Nam'", sql)
        self.assertIn("'Nu'", sql)
        self.assertIn("'Other'", sql)

        # Standardized loyalty tier
        self.assertIn("'bronze'", sql)
        self.assertIn("'silver'", sql)
        self.assertIn("'gold'", sql)
        self.assertIn("'platinum'", sql)

        # Transformation audit column
        self.assertIn("current_timestamp() as _transformed_at", sql)

    def test_silver_customers_yaml_schema(self) -> None:
        """Verify silver_customers schema assertions, primary key constraints, and accepted values."""
        with open(self.customers_yml, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        self.assertIsInstance(doc, dict)
        self.assertEqual(doc.get("version"), 2)

        models = {m.get("name"): m for m in doc.get("models", [])}
        self.assertIn("silver_customers", models)

        cols = {c.get("name"): c for c in models["silver_customers"].get("columns", [])}

        # Expected columns check
        expected_cols = [
            "customer_id",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "gender",
            "tire",
            "address",
            "created_at",
            "updated_at",
            "_transformed_at",
        ]
        for col_name in expected_cols:
            self.assertIn(
                col_name,
                cols,
                f"Column '{col_name}' must be defined in silver_customers.yml",
            )

        # Primary key tests
        self.assertIn("unique", cols["customer_id"].get("tests", []))
        self.assertIn("not_null", cols["customer_id"].get("tests", []))

        # Not null tests
        self.assertIn("not_null", cols["first_name"].get("tests", []))
        self.assertIn("not_null", cols["last_name"].get("tests", []))
        self.assertIn("not_null", cols["tire"].get("tests", []))
        self.assertIn("not_null", cols["created_at"].get("tests", []))
        self.assertIn("not_null", cols["_transformed_at"].get("tests", []))

        # Accepted values tests
        gender_tests = cols["gender"].get("tests", [])
        accepted_gender = next(
            (
                t.get("accepted_values", {}).get("values")
                for t in gender_tests
                if isinstance(t, dict) and "accepted_values" in t
            ),
            None,
        )
        self.assertEqual(accepted_gender, ["Nam", "Nu", "Other"])

        tier_tests = cols["tire"].get("tests", [])
        accepted_tier = next(
            (
                t.get("accepted_values", {}).get("values")
                for t in tier_tests
                if isinstance(t, dict) and "accepted_values" in t
            ),
            None,
        )
        self.assertEqual(accepted_tier, ["bronze", "silver", "gold", "platinum"])


if __name__ == "__main__":
    unittest.main()
