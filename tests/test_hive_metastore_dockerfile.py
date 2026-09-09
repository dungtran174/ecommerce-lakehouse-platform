"""Unit tests for Hive Metastore custom Dockerfile configuration."""

from __future__ import annotations

import os
import unittest


class TestHiveMetastoreDockerfile(unittest.TestCase):
    """Test suite validating Dockerfile directives for Hive Metastore 3.0."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate Dockerfile path."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.dockerfile_path = os.path.join(
            cls.root_dir, "docker", "hive-metastore", "Dockerfile"
        )

    def test_dockerfile_exists(self) -> None:
        """Verify docker/hive-metastore/Dockerfile is present."""
        self.assertTrue(
            os.path.exists(self.dockerfile_path),
            "docker/hive-metastore/Dockerfile must exist",
        )

    def test_base_image_and_components(self) -> None:
        """Verify base image is Java 8 and required tools are installed."""
        with open(self.dockerfile_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("FROM eclipse-temurin:8-jre", content)
        self.assertIn("ARG HADOOP_VERSION=3.2.0", content)
        self.assertIn("ARG HIVE_METASTORE_VERSION=3.0.0", content)
        self.assertIn("ARG MYSQL_CONNECTOR_VERSION=8.0.33", content)

    def test_s3a_and_mysql_integrations(self) -> None:
        """Verify S3A object store connectors and MySQL JDBC driver are present."""
        with open(self.dockerfile_path, "r", encoding="utf-8") as f:
            content = f.read()

        # MySQL JDBC Driver
        self.assertIn("mysql-connector-j", content)

        # Hadoop AWS & AWS Java SDK bundle for MinIO S3A
        self.assertIn("hadoop-aws-", content)
        self.assertIn("aws-java-sdk-bundle", content)

        # Guava dependency conflict fix
        self.assertIn("guava-19.0.jar", content)
        self.assertIn("guava-", content)

    def test_security_and_networking(self) -> None:
        """Verify non-root hive user execution and Thrift port exposure."""
        with open(self.dockerfile_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("useradd -r -g hive", content)
        self.assertIn("USER hive", content)
        self.assertIn("EXPOSE 9083", content)
        self.assertIn("start-metastore", content)


if __name__ == "__main__":
    unittest.main()
