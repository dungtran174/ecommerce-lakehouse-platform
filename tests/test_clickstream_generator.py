"""Unit tests for ClickstreamGenerator (NDJSON activity logs)."""

import json
import os
import shutil
import tempfile
import unittest
from datetime import datetime

from data_generators.generate_clickstream_logs import ClickstreamGenerator


class TestClickstreamGenerator(unittest.TestCase):
    """Test suite for ClickstreamGenerator session and NDJSON persistence."""

    def setUp(self) -> None:
        """Initialize generator and temporary output folder."""
        self.test_dir = tempfile.mkdtemp()
        self.generator = ClickstreamGenerator(seed=42)
        self.mock_products = [
            {
                "product_id": 101,
                "product_name": "MSI Stealth 14",
                "category_id": 10,
                "price": 3200.0,
            },
            {
                "product_id": 202,
                "product_name": "Vợt cầu lông Yonex",
                "category_id": 7,
                "price": 450.0,
            },
        ]

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_generate_session_schema_and_integrity(self) -> None:
        """Verify session structure, telemetry, actions array, and metrics."""
        session_time = datetime(2026, 9, 2, 14, 30, 0)
        session = self.generator.generate_session(
            timestamp=session_time,
            user_id=100018,
            products=self.mock_products,
        )

        # Core keys check
        required_keys = [
            "event_id",
            "session_id",
            "timestamp",
            "user_id",
            "user_segment",
            "device",
            "location",
            "referrer",
            "referrer_type",
            "source",
            "actions",
            "session_metrics",
            "properties",
        ]
        for key in required_keys:
            self.assertIn(key, session)

        # Device keys check
        for d_key in ["type", "os", "browser", "version"]:
            self.assertIn(d_key, session["device"])

        # Location keys check
        self.assertEqual(session["location"]["country"], "VN")
        self.assertIn("city", session["location"])
        self.assertIn("lat", session["location"]["coordinates"])
        self.assertIn("lon", session["location"]["coordinates"])

        # Properties check
        self.assertEqual(session["properties"]["currency"], "VND")
        self.assertIn(session["properties"]["ab_test"], ["A", "B"])
        self.assertEqual(
            session["properties"]["is_mobile"],
            (session["device"]["type"] == "mobile"),
        )

        # Metrics mathematical verification
        metrics = session["session_metrics"]
        actions = session["actions"]
        self.assertEqual(metrics["actions_count"], len(actions))
        self.assertGreater(metrics["duration_seconds"], 0)

        has_purchase_action = any(a["type"] == "purchase" for a in actions)
        self.assertEqual(metrics["has_purchase"], has_purchase_action)
        if has_purchase_action:
            self.assertGreater(metrics["revenue"], 0)
        else:
            self.assertEqual(metrics["revenue"], 0.0)

    def test_generate_daily_logs_ndjson_files(self) -> None:
        """Verify daily partitioned NDJSON files creation and valid JSON lines."""
        target_date = datetime(2026, 9, 3)
        files = self.generator.generate_daily_logs(
            date=target_date,
            session_count=40,
            output_dir=self.test_dir,
            products=self.mock_products,
            user_ids=[100001, 100002, 100003],
            parts=2,
        )

        self.assertEqual(len(files), 2)
        total_sessions_read = 0

        for path in files:
            self.assertTrue(os.path.exists(path))
            self.assertIn("ingest_date=2026-09-03", path)
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    record = json.loads(line.strip())
                    self.assertIn("session_id", record)
                    self.assertIn("session_metrics", record)
                    total_sessions_read += 1

        self.assertEqual(total_sessions_read, 40)

    def test_generate_multi_day_logs(self) -> None:
        """Verify multi-day partitioned structure."""
        start_date = datetime(2026, 9, 1)
        result = self.generator.generate_multi_day_logs(
            start_date=start_date,
            days=3,
            sessions_per_day=20,
            output_dir=self.test_dir,
            parts_per_day=1,
        )

        self.assertEqual(len(result), 3)
        for date_key, file_list in result.items():
            self.assertEqual(len(file_list), 1)
            self.assertTrue(os.path.exists(file_list[0]))
            self.assertIn(f"ingest_date={date_key}", file_list[0])


if __name__ == "__main__":
    unittest.main()
