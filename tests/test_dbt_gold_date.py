"""Unit tests for Gold date dimension table (dim_date)."""

from __future__ import annotations

import os
import unittest

import yaml


class TestDbtGoldDate(unittest.TestCase):
    """Test suite validating Gold Kimball Galaxy Schema date dimension model and assertions."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate Gold date dimension model and YAML schema files."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.gold_dir = os.path.join(cls.root_dir, "dbt", "models", "gold", "sale_mart")

        cls.date_sql = os.path.join(cls.gold_dir, "dim_date.sql")
        cls.date_yml = os.path.join(cls.gold_dir, "dim_date.yml")

    def test_model_files_exist(self) -> None:
        """Verify dim_date SQL model and YAML schema file exist on disk."""
        self.assertTrue(os.path.exists(self.date_sql), "dim_date.sql must exist")
        self.assertTrue(os.path.exists(self.date_yml), "dim_date.yml must exist")

    def test_dim_date_sql_logic(self) -> None:
        """Verify dim_date date sequence generation and calendar attributes."""
        with open(self.date_sql, "r", encoding="utf-8") as f:
            sql = f.read()

        self.assertIn("sequence(", sql)
        self.assertIn("explode(", sql)
        self.assertIn("date_key", sql)
        self.assertIn("calendar_date", sql)
        self.assertIn("year(calendar_date)", sql)
        self.assertIn("month(calendar_date)", sql)
        self.assertIn("month_year", sql)
        self.assertIn("quarter(calendar_date)", sql)
        self.assertIn("quarter_name", sql)
        self.assertIn("quarter_year", sql)
        self.assertIn("month_name", sql)
        self.assertIn("day_name", sql)
        self.assertIn("is_weekend", sql)
        self.assertIn("is_weekday", sql)
        self.assertIn("current_timestamp() as _created_at", sql)

    def test_dim_date_yaml_schema(self) -> None:
        """Verify dim_date column definitions and schema validation constraints."""
        with open(self.date_yml, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        models = {m.get("name"): m for m in doc.get("models", [])}
        self.assertIn("dim_date", models)
        cols = {c.get("name"): c for c in models["dim_date"].get("columns", [])}

        expected_columns = [
            "date_key",
            "calendar_date",
            "year",
            "month",
            "month_year",
            "quarter",
            "quarter_name",
            "quarter_year",
            "month_name",
            "day_name",
            "is_weekend",
            "is_weekday",
            "_created_at",
        ]

        for col_name in expected_columns:
            self.assertIn(col_name, cols, f"Column {col_name} must be documented")

        # Check unique & not_null on primary key
        self.assertIn("unique", cols["date_key"].get("tests", []))
        self.assertIn("not_null", cols["date_key"].get("tests", []))
        self.assertIn("unique", cols["calendar_date"].get("tests", []))
        self.assertIn("not_null", cols["calendar_date"].get("tests", []))

        # Check accepted values on flags
        weekend_tests = cols["is_weekend"].get("tests", [])
        has_weekend_accepted = any(
            isinstance(t, dict) and "accepted_values" in t for t in weekend_tests
        )
        self.assertTrue(
            has_weekend_accepted, "is_weekend must have accepted_values test"
        )

        weekday_tests = cols["is_weekday"].get("tests", [])
        has_weekday_accepted = any(
            isinstance(t, dict) and "accepted_values" in t for t in weekday_tests
        )
        self.assertTrue(
            has_weekday_accepted, "is_weekday must have accepted_values test"
        )


if __name__ == "__main__":
    unittest.main()
