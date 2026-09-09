"""Unit tests for MinIO bucket provisioning script (scripts/init_minio.sh)."""

from __future__ import annotations

import os
import subprocess
import unittest


class TestInitMinIOScript(unittest.TestCase):
    """Test suite validating MinIO initialization script and bucket hierarchy."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate init_minio.sh script path."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.script_path = os.path.join(cls.root_dir, "scripts", "init_minio.sh")

    def test_script_exists_and_is_executable(self) -> None:
        """Verify scripts/init_minio.sh exists and has execute permissions."""
        self.assertTrue(
            os.path.exists(self.script_path), "scripts/init_minio.sh must exist"
        )
        self.assertTrue(
            os.access(self.script_path, os.X_OK),
            "scripts/init_minio.sh must be executable",
        )

    def test_shell_syntax_is_valid(self) -> None:
        """Verify init_minio.sh contains valid POSIX shell syntax."""
        result = subprocess.run(
            ["/bin/sh", "-n", self.script_path],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"Shell syntax check failed: {result.stderr}",
        )

    def test_script_declares_all_medallion_tiers_and_prefixes(self) -> None:
        """Verify all Medallion and operational storage prefixes are defined."""
        with open(self.script_path, "r", encoding="utf-8") as f:
            content = f.read()

        required_prefixes = [
            "bronze/mysql",
            "bronze/clickstream",
            "silver/ecommerce",
            "gold/sale_mart",
            "gold/ml",
            "logs/airflow",
            "logs/spark",
            "models/churn_prediction",
            "models/sales_forecasting",
            "checkpoints/spark_streaming",
            "checkpoints/dbt",
            "tmp/scratch",
        ]

        for prefix in required_prefixes:
            self.assertIn(
                prefix,
                content,
                f"Prefix '{prefix}' must be declared in init_minio.sh",
            )

    def test_script_contains_connection_and_policy_logic(self) -> None:
        """Verify retry connection loop, bucket creation, and policy configuration."""
        with open(self.script_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Connection and alias
        self.assertIn("alias set", content)
        self.assertIn("MINIO_ENDPOINT", content)
        self.assertIn("MINIO_ROOT_USER", content)
        self.assertIn("MINIO_ROOT_PASSWORD", content)

        # Bucket creation and policy
        self.assertIn("mb --ignore-existing", content)
        self.assertIn("anonymous set download", content)
        self.assertIn("pipe", content)
        self.assertIn(".keep", content)


if __name__ == "__main__":
    unittest.main()
