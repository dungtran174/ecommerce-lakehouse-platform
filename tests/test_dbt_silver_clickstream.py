"""Unit tests for conformed Silver clickstream models (silver_user_sessions, silver_session_actions)."""

from __future__ import annotations

import os
import unittest

import yaml


class TestDbtSilverClickstream(unittest.TestCase):
    """Test suite validating user sessions and exploded session actions models and schema assertions."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate silver models and YAML schema files."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.silver_dir = os.path.join(cls.root_dir, "dbt", "models", "silver")

        cls.sessions_sql = os.path.join(cls.silver_dir, "silver_user_sessions.sql")
        cls.sessions_yml = os.path.join(cls.silver_dir, "silver_user_sessions.yml")

        cls.actions_sql = os.path.join(cls.silver_dir, "silver_session_actions.sql")
        cls.actions_yml = os.path.join(cls.silver_dir, "silver_session_actions.yml")

    def test_model_files_exist(self) -> None:
        """Verify sessions and actions SQL models and YAML schema files exist on disk."""
        self.assertTrue(
            os.path.exists(self.sessions_sql),
            "silver_user_sessions.sql must exist",
        )
        self.assertTrue(
            os.path.exists(self.sessions_yml),
            "silver_user_sessions.yml must exist",
        )
        self.assertTrue(
            os.path.exists(self.actions_sql),
            "silver_session_actions.sql must exist",
        )
        self.assertTrue(
            os.path.exists(self.actions_yml),
            "silver_session_actions.yml must exist",
        )

    def test_silver_user_sessions_sql_and_schema(self) -> None:
        """Verify silver_user_sessions SQL logic, deduplication, date partitioning, and schema assertions."""
        with open(self.sessions_sql, "r", encoding="utf-8") as f:
            sql = f.read()

        self.assertIn("ref('stg_clickstream_events')", sql)
        self.assertIn("alias='user_sessions'", sql)
        self.assertIn("partition_by=['year', 'month', 'day']", sql)
        self.assertIn("partition by session_id", sql)
        self.assertIn("where row_num = 1", sql)
        self.assertIn("year(event_timestamp) as year", sql)
        self.assertIn("month(event_timestamp) as month", sql)
        self.assertIn("day(event_timestamp) as day", sql)
        self.assertIn("current_timestamp() as _transformed_at", sql)

        with open(self.sessions_yml, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        models = {m.get("name"): m for m in doc.get("models", [])}
        self.assertIn("silver_user_sessions", models)
        cols = {
            c.get("name"): c for c in models["silver_user_sessions"].get("columns", [])
        }
        self.assertIn("session_id", cols)
        self.assertIn("timestamp", cols)
        self.assertIn("duration_seconds", cols)
        self.assertIn("has_purchase", cols)
        self.assertIn("year", cols)
        self.assertIn("month", cols)
        self.assertIn("day", cols)
        self.assertIn("unique", cols["session_id"].get("tests", []))
        self.assertIn("not_null", cols["session_id"].get("tests", []))
        self.assertIn("not_null", cols["timestamp"].get("tests", []))
        self.assertIn("not_null", cols["year"].get("tests", []))
        self.assertIn("not_null", cols["_transformed_at"].get("tests", []))

    def test_silver_session_actions_sql_and_schema(self) -> None:
        """Verify silver_session_actions exploding logic, indicator flags, surrogate key, and schema assertions."""
        with open(self.actions_sql, "r", encoding="utf-8") as f:
            sql = f.read()

        self.assertIn("ref('stg_clickstream_events')", sql)
        self.assertIn("alias='session_actions'", sql)
        self.assertIn("partition_by=['year', 'month', 'day']", sql)
        self.assertIn("explode(", sql)
        self.assertIn("from_json(", sql)
        self.assertIn("concat(", sql)
        self.assertIn("-act-", sql)
        self.assertIn("is_view", sql)
        self.assertIn("is_add_to_cart", sql)
        self.assertIn("is_purchase", sql)
        self.assertIn("is_search", sql)
        self.assertIn("current_timestamp() as _transformed_at", sql)

        with open(self.actions_yml, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        models = {m.get("name"): m for m in doc.get("models", [])}
        self.assertIn("silver_session_actions", models)
        cols = {
            c.get("name"): c
            for c in models["silver_session_actions"].get("columns", [])
        }
        self.assertIn("action_id", cols)
        self.assertIn("session_id", cols)
        self.assertIn("action_timestamp", cols)
        self.assertIn("action_type", cols)
        self.assertIn("is_view", cols)
        self.assertIn("is_purchase", cols)
        self.assertIn("year", cols)
        self.assertIn("unique", cols["action_id"].get("tests", []))
        self.assertIn("not_null", cols["action_id"].get("tests", []))
        self.assertIn("not_null", cols["session_id"].get("tests", []))
        self.assertIn("not_null", cols["action_timestamp"].get("tests", []))
        self.assertIn("not_null", cols["_transformed_at"].get("tests", []))

        # Foreign key relationship to silver_user_sessions
        session_rel = next(
            (
                t.get("relationships", {})
                for t in cols["session_id"].get("tests", [])
                if isinstance(t, dict) and "relationships" in t
            ),
            None,
        )
        self.assertIsNotNone(session_rel)
        self.assertIn("silver_user_sessions", str(session_rel.get("to", "")))


if __name__ == "__main__":
    unittest.main()
