"""Unit tests for dbt staging model stg_customers and schema definitions."""

from __future__ import annotations

import os
import unittest

import yaml


class TestDbtStgCustomers(unittest.TestCase):
    """Test suite validating staging model SQL logic and schema documentation."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate stg_customers model and YAML schema files."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.staging_dir = os.path.join(cls.root_dir, "dbt", "models", "staging")

        cls.model_sql_file = os.path.join(cls.staging_dir, "stg_customers.sql")
        cls.model_yml_file = os.path.join(cls.staging_dir, "stg_customers.yml")

    def test_model_files_exist(self) -> None:
        """Verify stg_customers SQL and YAML specification files exist on disk."""
        self.assertTrue(
            os.path.exists(self.model_sql_file), "stg_customers.sql must exist"
        )
        self.assertTrue(
            os.path.exists(self.model_yml_file), "stg_customers.yml must exist"
        )

    def test_model_sql_logic(self) -> None:
        """Verify SQL model references source correctly and applies proper transformations."""
        with open(self.model_sql_file, "r", encoding="utf-8") as f:
            sql = f.read()

        # Check source dependency
        self.assertIn("source('mysql_oltp', 'customers_snapshot')", sql)

        # Check column transformations and data types
        self.assertIn("cast(customer_id as int)", sql)
        self.assertIn("trim(cast(first_name as string))", sql)
        self.assertIn("trim(cast(last_name as string))", sql)
        self.assertIn("lower(trim(cast(email as string)))", sql)
        self.assertIn("trim(cast(phone_number as string))", sql)
        self.assertIn("trim(cast(gender as string))", sql)
        self.assertIn("lower(trim(cast(tire as string)))", sql)
        self.assertIn("trim(cast(address as string))", sql)
        self.assertIn("cast(created_at as timestamp)", sql)
        self.assertIn("cast(updated_at as timestamp)", sql)
        self.assertIn("current_timestamp() as _ingested_at", sql)

    def test_model_yaml_schema_validity(self) -> None:
        """Verify stg_customers.yml is valid YAML and defines expected schema tests."""
        with open(self.model_yml_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        self.assertIsInstance(doc, dict)
        self.assertEqual(doc.get("version"), 2)

        models = {m.get("name"): m for m in doc.get("models", [])}
        self.assertIn("stg_customers", models)

        customer_model = models["stg_customers"]
        columns = {c.get("name"): c for c in customer_model.get("columns", [])}

        required_columns = [
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
            "_ingested_at",
        ]
        for col in required_columns:
            self.assertIn(
                col, columns, f"Column '{col}' must be documented in stg_customers.yml"
            )

        # Check primary key tests on customer_id
        cust_id_tests = columns["customer_id"].get("tests", [])
        self.assertIn("unique", cust_id_tests)
        self.assertIn("not_null", cust_id_tests)


if __name__ == "__main__":
    unittest.main()
