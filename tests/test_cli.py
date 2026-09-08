"""Unit tests for unified CLI data generation suite."""

import os
import shutil
import tempfile
import unittest

from data_generators.cli import (
    SCALE_CONFIGS,
    main,
    run_clickstream_pipeline,
    run_oltp_pipeline,
)
from data_generators.db_connector import DatabaseConnector


class TestDataGeneratorsCLI(unittest.TestCase):
    """Test suite for CLI interfaces, scale configs, and pipeline runners."""

    def setUp(self) -> None:
        """Create temporary test directory."""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self) -> None:
        """Clean up temporary test directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_scale_configurations_present(self) -> None:
        """Verify scale presets (small, medium, full) have defined configuration keys."""
        for scale_name in ["small", "medium", "full"]:
            self.assertIn(scale_name, SCALE_CONFIGS)
            cfg = SCALE_CONFIGS[scale_name]
            self.assertIn("brands", cfg)
            self.assertIn("products", cfg)
            self.assertIn("customers", cfg)
            self.assertIn("orders", cfg)
            self.assertIn("clickstream_days", cfg)

    def test_run_oltp_pipeline_small(self) -> None:
        """Verify running OLTP pipeline exports all 7 entity snapshot files."""
        output_dir = os.path.join(self.test_dir, "mysql")
        result = run_oltp_pipeline(
            scale="small",
            output_dir=output_dir,
            seed_db=False,
        )

        files = result["files"]
        expected_entities = [
            "brands",
            "category",
            "payment_method",
            "products",
            "customers",
            "orders",
            "order_items",
        ]

        for entity in expected_entities:
            self.assertIn(entity, files)
            self.assertTrue(
                os.path.exists(files[entity]),
                f"Snapshot file for {entity} must exist",
            )
            self.assertGreater(os.path.getsize(files[entity]), 0)

    def test_run_oltp_pipeline_with_sqlite_db(self) -> None:
        """Verify OLTP pipeline with database seeding option on SQLite."""
        output_dir = os.path.join(self.test_dir, "mysql_db")
        db_path = os.path.join(self.test_dir, "test_cli.db")
        connector = DatabaseConnector(use_sqlite=True, sqlite_path=db_path)

        result = run_oltp_pipeline(
            scale="small",
            output_dir=output_dir,
            seed_db=True,
            connector=connector,
        )

        self.assertIn("db_stats", result)
        db_stats = result["db_stats"]
        self.assertGreater(db_stats["brands"], 0)
        self.assertGreater(db_stats["orders"], 0)

    def test_run_clickstream_pipeline_small(self) -> None:
        """Verify running clickstream pipeline creates partitioned NDJSON logs."""
        output_dir = os.path.join(self.test_dir, "clickstream")
        result = run_clickstream_pipeline(
            scale="small",
            output_dir=output_dir,
            start_date="2026-09-01",
            parts_per_day=1,
        )

        self.assertEqual(len(result), SCALE_CONFIGS["small"]["clickstream_days"])
        for date_key, files in result.items():
            self.assertGreater(len(files), 0)
            self.assertTrue(os.path.exists(files[0]))
            self.assertIn(f"ingest_date={date_key}", files[0])

    def test_cli_main_entrypoint_execution(self) -> None:
        """Verify main() argument parsing without unhandled exceptions."""
        output_dir = os.path.join(self.test_dir, "cli_output")
        # Run OLTP only via CLI args
        main(
            [
                "--target",
                "oltp",
                "--scale",
                "small",
                "--output-dir",
                output_dir,
            ]
        )
        self.assertTrue(os.path.exists(os.path.join(output_dir, "mysql")))


if __name__ == "__main__":
    unittest.main()
