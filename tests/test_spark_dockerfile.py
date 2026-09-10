"""Unit tests for customized Apache Spark Dockerfile directives and library dependencies."""

from __future__ import annotations

import os
import unittest


class TestSparkDockerfile(unittest.TestCase):
    """Test suite validating Dockerfile directives for Apache Spark 3.3.3 image."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate Spark Dockerfile path."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.dockerfile_path = os.path.join(
            cls.root_dir, "docker", "spark", "Dockerfile"
        )

    def test_dockerfile_exists(self) -> None:
        """Verify docker/spark/Dockerfile is present."""
        self.assertTrue(
            os.path.exists(self.dockerfile_path),
            "docker/spark/Dockerfile must exist",
        )

    def test_base_image_and_arguments(self) -> None:
        """Verify base image is Spark 3.3.3 and required ARGs are configured."""
        with open(self.dockerfile_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("FROM apache/spark:3.3.3", content)
        self.assertIn("ARG DELTA_VERSION=2.2.0", content)
        self.assertIn("ARG SCALA_VERSION=2.12", content)
        self.assertIn("ARG HADOOP_AWS_VERSION=3.3.3", content)
        self.assertIn("ARG AWS_SDK_VERSION=1.12.367", content)

    def test_delta_lake_and_s3a_libraries(self) -> None:
        """Verify Delta Lake, Hadoop AWS, and AWS SDK bundle JARs are downloaded."""
        with open(self.dockerfile_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Delta Lake jars
        self.assertIn("delta-core_${SCALA_VERSION}-${DELTA_VERSION}.jar", content)
        self.assertIn("delta-storage-${DELTA_VERSION}.jar", content)

        # Hadoop AWS & AWS Java SDK bundle
        self.assertIn("hadoop-aws-${HADOOP_AWS_VERSION}.jar", content)
        self.assertIn("aws-java-sdk-bundle-${AWS_SDK_VERSION}.jar", content)

        # MySQL JDBC Driver
        self.assertIn("mysql-connector-j-8.0.33.jar", content)

    def test_ports_user_and_cmd(self) -> None:
        """Verify exposed Thrift and UI ports, unprivileged user, and default command."""
        with open(self.dockerfile_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("EXPOSE 10000 4040", content)
        self.assertIn("USER 185", content)
        self.assertIn("start-thriftserver.sh", content)


if __name__ == "__main__":
    unittest.main()
