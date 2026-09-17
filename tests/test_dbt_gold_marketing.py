"""Unit tests for dbt Gold marketing campaign model and schema validation."""

from __future__ import annotations

import os
import unittest

import yaml


class TestDbtGoldMarketing(unittest.TestCase):
    """Test suite validating Gold marketing SQL logic, YAML configuration, and schema tests."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate marketing model and schema definition files."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.marketing_sql = os.path.join(
            cls.root_dir,
            "dbt",
            "models",
            "gold",
            "marketing",
            "high_value_purchase_campaign.sql",
        )
        cls.marketing_yml = os.path.join(
            cls.root_dir,
            "dbt",
            "models",
            "gold",
            "marketing",
            "high_value_purchase_campaign.yml",
        )

    def test_marketing_files_exist(self) -> None:
        """Verify SQL and YAML files exist in gold marketing directory."""
        self.assertTrue(
            os.path.exists(self.marketing_sql),
            "high_value_purchase_campaign.sql must exist",
        )
        self.assertTrue(
            os.path.exists(self.marketing_yml),
            "high_value_purchase_campaign.yml must exist",
        )

    def test_marketing_sql_logic(self) -> None:
        """Verify SQL references ML features and customer master tables."""
        with open(self.marketing_sql, "r", encoding="utf-8") as f:
            sql = f.read()

        # Upstream model references
        self.assertIn("ref('ml_user_behavior_3d_agg_feature')", sql)
        self.assertIn("ref('silver_customers')", sql)

        # Delta configuration
        self.assertIn("materialized='incremental'", sql)
        self.assertIn("file_format='delta'", sql)
        self.assertIn("incremental_strategy='merge'", sql)

        # Propensity tiering and touchpoints
        self.assertIn("Hot Lead", sql)
        self.assertIn("Medium Intent", sql)
        self.assertIn("Low Intent", sql)
        self.assertIn("Send Premium Offer SMS", sql)
        self.assertIn("Personalized Email Recommendation", sql)
        self.assertIn("Retargeting Display Ad", sql)
        self.assertIn("SMS_AND_PUSH", sql)
        self.assertIn("EMAIL", sql)
        self.assertIn("DISPLAY_ADS", sql)

        # Partition keys
        self.assertIn("year", sql)
        self.assertIn("month", sql)
        self.assertIn("day", sql)

    def test_marketing_yaml_schema_and_tests(self) -> None:
        """Verify YAML declaration has proper column tests and accepted values."""
        with open(self.marketing_yml, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        self.assertIn("models", data)
        model = data["models"][0]
        self.assertEqual(model["name"], "high_value_purchase_campaign")

        col_dict = {col["name"]: col for col in model.get("columns", [])}

        # Check required columns
        required_cols = [
            "customer_id",
            "campaign_date",
            "purchase_probability",
            "customer_segment",
            "campaign_action",
            "campaign_channel",
            "first_name",
            "last_name",
            "email",
            "phone",
            "predicted_at",
            "created_at",
            "year",
            "month",
            "day",
        ]
        for c in required_cols:
            self.assertIn(c, col_dict, f"Column {c} must be declared in YAML")

        # Check accepted_values test for customer_segment
        segment_tests = col_dict["customer_segment"].get("tests", [])
        has_accepted = any(
            isinstance(t, dict) and "accepted_values" in t for t in segment_tests
        )
        self.assertTrue(has_accepted, "customer_segment must test accepted_values")

        # Check accepted_values test for campaign_channel
        channel_tests = col_dict["campaign_channel"].get("tests", [])
        has_channel_accepted = any(
            isinstance(t, dict) and "accepted_values" in t for t in channel_tests
        )
        self.assertTrue(
            has_channel_accepted, "campaign_channel must test accepted_values"
        )


if __name__ == "__main__":
    unittest.main()
