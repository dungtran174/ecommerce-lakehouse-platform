"""Unit tests for Gold ML feature store, singular tests, and dbt lineage."""

from __future__ import annotations

import os
import unittest

import yaml


class TestDbtGoldML(unittest.TestCase):
    """Test suite validating Gold ML feature store, singular test assertions, and documentation."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate project files for ML feature store and data testing."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.ml_sql = os.path.join(
            cls.root_dir,
            "dbt",
            "models",
            "gold",
            "ml",
            "ml_user_behavior_3d_agg_feature.sql",
        )
        cls.ml_yml = os.path.join(
            cls.root_dir,
            "dbt",
            "models",
            "gold",
            "ml",
            "ml_user_behavior_3d_agg_feature.yml",
        )
        cls.singular_test = os.path.join(
            cls.root_dir, "dbt", "tests", "assert_positive_revenue.sql"
        )
        cls.lineage_doc = os.path.join(cls.root_dir, "docs", "setup", "dbt_lineage.md")

    def test_model_files_exist(self) -> None:
        """Verify ML feature store, singular test, and lineage doc exist on disk."""
        self.assertTrue(
            os.path.exists(self.ml_sql),
            "ml_user_behavior_3d_agg_feature.sql must exist",
        )
        self.assertTrue(
            os.path.exists(self.ml_yml),
            "ml_user_behavior_3d_agg_feature.yml must exist",
        )
        self.assertTrue(
            os.path.exists(self.singular_test),
            "assert_positive_revenue.sql must exist",
        )
        self.assertTrue(os.path.exists(self.lineage_doc), "dbt_lineage.md must exist")

    def test_ml_feature_store_sql_logic(self) -> None:
        """Verify ML feature store references Silver models and computes rolling features."""
        with open(self.ml_sql, "r", encoding="utf-8") as f:
            sql = f.read()

        self.assertIn("ref('silver_user_sessions')", sql)
        self.assertIn("ref('silver_session_actions')", sql)
        self.assertIn("user_id", sql)
        self.assertIn("prediction_date", sql)
        self.assertIn("label_purchase_tomorrow", sql)
        self.assertIn("sessions_3d", sql)
        self.assertIn("total_duration_3d", sql)
        self.assertIn("avg_session_duration_3d", sql)
        self.assertIn("total_page_views_3d", sql)
        self.assertIn("total_actions_3d", sql)
        self.assertIn("cart_conversion_rate_3d", sql)
        self.assertIn("purchase_conversion_rate_3d", sql)
        self.assertIn("actions_per_session_3d", sql)
        self.assertIn("purchase_session_rate_3d", sql)
        self.assertIn("current_timestamp() as _created_at", sql)

    def test_ml_feature_store_yaml_schema(self) -> None:
        """Verify ML feature store YAML documentation and test constraints."""
        with open(self.ml_yml, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        models = {m.get("name"): m for m in doc.get("models", [])}
        self.assertIn("ml_user_behavior_3d_agg_feature", models)
        cols = {
            c.get("name"): c
            for c in models["ml_user_behavior_3d_agg_feature"].get("columns", [])
        }

        expected_columns = [
            "user_id",
            "prediction_date",
            "label_purchase_tomorrow",
            "sessions_3d",
            "total_duration_3d",
            "avg_session_duration_3d",
            "total_page_views_3d",
            "total_actions_3d",
            "purchase_sessions_3d",
            "total_revenue_3d",
            "view_count_3d",
            "add_to_cart_count_3d",
            "purchase_count_3d",
            "search_count_3d",
            "wishlist_count_3d",
            "checkout_view_count_3d",
            "distinct_products_3d",
            "avg_product_price_3d",
            "cart_conversion_rate_3d",
            "purchase_conversion_rate_3d",
            "actions_per_session_3d",
            "purchase_session_rate_3d",
            "_created_at",
        ]

        for col_name in expected_columns:
            self.assertIn(col_name, cols)
            self.assertIn("not_null", cols[col_name].get("tests", []))

        # Test accepted_values on label_purchase_tomorrow
        label_tests = cols["label_purchase_tomorrow"].get("tests", [])
        has_accepted = any(
            isinstance(t, dict) and "accepted_values" in t for t in label_tests
        )
        self.assertTrue(
            has_accepted,
            "label_purchase_tomorrow must enforce accepted_values: [0, 1]",
        )

    def test_singular_assert_positive_revenue_test(self) -> None:
        """Verify singular data test assertions on revenue non-negativity."""
        with open(self.singular_test, "r", encoding="utf-8") as f:
            sql = f.read()

        self.assertIn("ref('fact_order')", sql)
        self.assertIn("ref('fact_order_items')", sql)
        self.assertIn("sub_total < 0", sql)
        self.assertIn("price < 0", sql)

    def test_dbt_lineage_doc_content(self) -> None:
        """Verify lineage markdown contains Mermaid DAG and operational commands."""
        with open(self.lineage_doc, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("```mermaid", content)
        self.assertIn("flowchart LR", content)
        self.assertIn("Staging Layer", content)
        self.assertIn("Silver Tier", content)
        self.assertIn("Gold Tier", content)
        self.assertIn("dbt run", content)
        self.assertIn("dbt test", content)


if __name__ == "__main__":
    unittest.main()
