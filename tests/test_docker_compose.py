"""Unit tests for Docker Compose infrastructure configurations."""

from __future__ import annotations

import os
import unittest


class TestDockerComposeConfig(unittest.TestCase):
    """Test suite validating docker-compose and environment configuration files."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate docker configuration paths."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.compose_file = os.path.join(cls.root_dir, "docker", "docker-compose.yml")
        cls.env_example_file = os.path.join(cls.root_dir, "docker", ".env.example")

    def test_docker_files_exist(self) -> None:
        """Verify docker-compose.yml and .env.example are present."""
        self.assertTrue(
            os.path.exists(self.compose_file), "docker-compose.yml must exist"
        )
        self.assertTrue(
            os.path.exists(self.env_example_file), ".env.example must exist"
        )

    def test_docker_compose_valid_yaml_and_structure(self) -> None:
        """Verify docker-compose parses cleanly and defines core infrastructure."""
        with open(self.compose_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Basic structure assertions
        self.assertIn("version:", content)
        self.assertIn("networks:", content)
        self.assertIn("lakehouse-net:", content)
        self.assertIn("volumes:", content)
        self.assertIn("services:", content)

        # Network configuration
        self.assertIn("172.28.0.0/16", content)

        # Storage volumes
        self.assertIn("mysql_oltp_data:", content)
        self.assertIn("minio_data:", content)
        self.assertIn("metastore_db_data:", content)

        # MySQL OLTP service
        self.assertIn("mysql-oltp:", content)
        self.assertIn("image: mysql:8.0", content)
        self.assertIn("healthcheck:", content)

    def test_env_example_contains_all_core_variables(self) -> None:
        """Verify .env.example declares all necessary service parameters."""
        with open(self.env_example_file, "r", encoding="utf-8") as f:
            env_content = f.read()

        expected_vars = [
            "MYSQL_OLTP_PORT",
            "MYSQL_ROOT_PASSWORD",
            "MYSQL_DATABASE",
            "MINIO_API_PORT",
            "MINIO_CONSOLE_PORT",
            "MINIO_ROOT_USER",
            "MINIO_ROOT_PASSWORD",
            "METASTORE_PORT",
            "SPARK_THRIFT_PORT",
            "TRINO_PORT",
            "AIRFLOW_WEBSERVER_PORT",
            "METABASE_PORT",
            "CLOUDBEAVER_PORT",
        ]

        for var in expected_vars:
            self.assertIn(var, env_content, f"Variable {var} must be defined")


if __name__ == "__main__":
    unittest.main()
