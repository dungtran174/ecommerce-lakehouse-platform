"""Unit tests for dbt staging model: stg_clickstream_events."""

from __future__ import annotations

import os
import unittest

import yaml


class TestDbtStgClickstream(unittest.TestCase):
    """Test suite validating clickstream staging model, JSON extraction, and schema assertions."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate staging models and YAML schema files."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.staging_dir = os.path.join(cls.root_dir, "dbt", "models", "staging")

        cls.clickstream_sql = os.path.join(
            cls.staging_dir, "stg_clickstream_events.sql"
        )
        cls.clickstream_yml = os.path.join(
            cls.staging_dir, "stg_clickstream_events.yml"
        )

    def test_model_files_exist(self) -> None:
        """Verify clickstream SQL model and YAML schema files exist on disk."""
        self.assertTrue(
            os.path.exists(self.clickstream_sql),
            "stg_clickstream_events.sql must exist",
        )
        self.assertTrue(
            os.path.exists(self.clickstream_yml),
            "stg_clickstream_events.yml must exist",
        )

    def test_clickstream_model_sql_logic(self) -> None:
        """Verify stg_clickstream_events SQL source, JSON parsing, incremental logic, and columns."""
        with open(self.clickstream_sql, "r", encoding="utf-8") as f:
            sql = f.read()

        # Source reference
        self.assertIn("source('clickstream', 'clickstream_events')", sql)

        # Base identity and timestamp casting
        self.assertIn("cast(event_id as string) as event_id", sql)
        self.assertIn("cast(session_id as string) as session_id", sql)
        self.assertIn("cast(timestamp as timestamp) as event_timestamp", sql)
        self.assertIn("cast(timestamp as date) as event_date", sql)
        self.assertIn("cast(user_id as bigint) as user_id", sql)
        self.assertIn("cast(user_segment as string) as user_segment", sql)

        # Device telemetry parsing
        self.assertIn(
            "get_json_object(cast(device as string), '$.type') as device_type", sql
        )
        self.assertIn(
            "get_json_object(cast(device as string), '$.os') as device_os", sql
        )
        self.assertIn(
            "get_json_object(cast(device as string), '$.browser') as device_browser",
            sql,
        )
        self.assertIn(
            "get_json_object(cast(device as string), '$.version') as device_version",
            sql,
        )

        # Geographic coordinates parsing
        self.assertIn(
            "get_json_object(cast(location as string), '$.city') as city", sql
        )
        self.assertIn(
            "get_json_object(cast(location as string), '$.country') as country",
            sql,
        )
        self.assertIn("coordinates.lat", sql)
        self.assertIn("coordinates.lon", sql)

        # Traffic & attribution
        self.assertIn("cast(referrer as string) as referrer", sql)
        self.assertIn("cast(referrer_type as string) as referrer_type", sql)
        self.assertIn("cast(source as string) as utm_source", sql)
        self.assertIn("cast(campaign as string) as utm_campaign", sql)

        # Session engagement metrics
        self.assertIn("duration_seconds", sql)
        self.assertIn("page_views", sql)
        self.assertIn("actions_count", sql)
        self.assertIn("has_purchase", sql)
        self.assertIn("revenue", sql)

        # Properties & actions
        self.assertIn("is_mobile", sql)
        self.assertIn("language", sql)
        self.assertIn("ab_test", sql)
        self.assertIn("cast(actions as string) as actions", sql)

        # Ingestion & audit metadata
        self.assertIn("current_timestamp() as _ingested_at", sql)

        # Incremental filter
        self.assertIn("is_incremental()", sql)
        self.assertIn("select max(event_timestamp)", sql)

    def test_clickstream_model_yaml_schema(self) -> None:
        """Verify stg_clickstream_events YAML documentation and schema test assertions."""
        with open(self.clickstream_yml, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        self.assertIsInstance(doc, dict)
        self.assertEqual(doc.get("version"), 2)

        models = {m.get("name"): m for m in doc.get("models", [])}
        self.assertIn("stg_clickstream_events", models)

        cols = {
            c.get("name"): c
            for c in models["stg_clickstream_events"].get("columns", [])
        }

        # Check column presence
        expected_columns = [
            "event_id",
            "session_id",
            "event_timestamp",
            "event_date",
            "user_id",
            "user_segment",
            "device_type",
            "device_os",
            "device_browser",
            "device_version",
            "city",
            "country",
            "latitude",
            "longitude",
            "referrer",
            "referrer_type",
            "utm_source",
            "utm_campaign",
            "duration_seconds",
            "page_views",
            "actions_count",
            "has_purchase",
            "revenue",
            "is_mobile",
            "language",
            "ab_test",
            "actions",
            "ingest_date",
            "_ingested_at",
        ]
        for col_name in expected_columns:
            self.assertIn(
                col_name,
                cols,
                f"Column '{col_name}' must be documented in stg_clickstream_events.yml",
            )

        # Check key tests
        self.assertIn("unique", cols["event_id"].get("tests", []))
        self.assertIn("not_null", cols["event_id"].get("tests", []))
        self.assertIn("not_null", cols["session_id"].get("tests", []))
        self.assertIn("not_null", cols["event_timestamp"].get("tests", []))
        self.assertIn("not_null", cols["event_date"].get("tests", []))
        self.assertIn("not_null", cols["city"].get("tests", []))
        self.assertIn("not_null", cols["duration_seconds"].get("tests", []))
        self.assertIn("not_null", cols["actions"].get("tests", []))
        self.assertIn("not_null", cols["_ingested_at"].get("tests", []))

        # Check accepted_values
        device_tests = cols["device_type"].get("tests", [])
        accepted_device = next(
            (
                t.get("accepted_values", {}).get("values")
                for t in device_tests
                if isinstance(t, dict) and "accepted_values" in t
            ),
            None,
        )
        self.assertEqual(accepted_device, ["desktop", "mobile", "tablet"])

        segment_tests = cols["user_segment"].get("tests", [])
        accepted_segment = next(
            (
                t.get("accepted_values", {}).get("values")
                for t in segment_tests
                if isinstance(t, dict) and "accepted_values" in t
            ),
            None,
        )
        self.assertEqual(accepted_segment, ["new", "returning", "loyal", "churn_risk"])


if __name__ == "__main__":
    unittest.main()
