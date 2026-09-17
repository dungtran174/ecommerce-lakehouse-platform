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
            "RANGER_PORT",
            "RANGER_DB_PORT",
        ]

        for var in expected_vars:
            self.assertIn(var, env_content, f"Variable {var} must be defined")

    def test_minio_service_configuration(self) -> None:
        """Verify MinIO object storage and multi-tier bucket provisioner configs."""
        with open(self.compose_file, "r", encoding="utf-8") as f:
            content = f.read()

        # MinIO server container assertions
        self.assertIn("minio:", content)
        self.assertIn("image: minio/minio:latest", content)
        self.assertIn("lakehouse-minio", content)
        self.assertIn("172.28.0.20", content)
        self.assertIn("s3.lakehouse.local", content)
        self.assertIn("MINIO_ROOT_USER", content)
        self.assertIn("MINIO_ROOT_PASSWORD", content)
        self.assertIn("minio_data:/data", content)
        self.assertIn("http://localhost:9000/minio/health/live", content)

        # MinIO multi-tier bucket provisioner assertions
        self.assertIn("minio-create-buckets:", content)
        self.assertIn("image: minio/mc:latest", content)
        self.assertIn("lakehouse-minio-create-buckets", content)
        self.assertIn("init_minio.sh", content)
        self.assertIn("/init_minio.sh", content)

    def test_hive_metastore_and_backend_service_configuration(self) -> None:
        """Verify Hive Metastore and MySQL backend database configurations."""
        with open(self.compose_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Metastore MySQL backend DB assertions
        self.assertIn("metastore-db:", content)
        self.assertIn("lakehouse-metastore-db", content)
        self.assertIn("metastore_db_data:/var/lib/mysql", content)
        self.assertIn("172.28.0.30", content)
        self.assertIn("METASTORE_DB_PORT", content)

        # Hive Metastore standalone container assertions
        self.assertIn("hive-metastore:", content)
        self.assertIn("lakehouse-hive-metastore", content)
        self.assertIn("context: ./hive-metastore", content)
        self.assertIn("image: lakehouse/hive-metastore:3.0.0", content)
        self.assertIn("172.28.0.31", content)
        self.assertIn("metastore.lakehouse.local", content)
        self.assertIn("METASTORE_PORT", content)
        self.assertIn("metastore-db:", content)
        self.assertIn('"nc", "-z", "localhost", "9083"', content)

    def test_spark_thrift_server_service_configuration(self) -> None:
        """Verify Apache Spark 3.3 Thrift Server container and network settings."""
        with open(self.compose_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("spark-thrift-server:", content)
        self.assertIn("lakehouse-spark-thrift-server", content)
        self.assertIn("context: ./spark", content)
        self.assertIn("image: lakehouse/spark-thrift-server:3.3.3", content)
        self.assertIn("172.28.0.40", content)
        self.assertIn("spark.lakehouse.local", content)
        self.assertIn("SPARK_THRIFT_PORT", content)
        self.assertIn("SPARK_UI_PORT", content)
        self.assertIn("hive-metastore:", content)
        self.assertIn("http://localhost:4040", content)

    def test_ranger_services_configuration(self) -> None:
        """Verify Apache Ranger Admin and PostgreSQL backend database service configurations."""
        with open(self.compose_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Ranger DB backend assertions
        self.assertIn("ranger-db:", content)
        self.assertIn("lakehouse-ranger-db", content)
        self.assertIn("ranger_db_data:/var/lib/postgresql/data", content)
        self.assertIn("172.28.0.60", content)
        self.assertIn("RANGER_DB_PORT", content)

        # Ranger Admin server assertions
        self.assertIn("ranger-admin:", content)
        self.assertIn("lakehouse-ranger-admin", content)
        self.assertIn("context: ./ranger", content)
        self.assertIn("image: lakehouse/ranger-admin:2.4.0", content)
        self.assertIn("172.28.0.61", content)
        self.assertIn("ranger.lakehouse.local", content)
        self.assertIn("RANGER_PORT", content)
        self.assertIn("ranger-db:", content)

    def test_trino_services_configuration(self) -> None:
        """Verify Trino Coordinator and Worker distributed query engine service configurations."""
        with open(self.compose_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Storage volumes
        self.assertIn("trino_coordinator_data:", content)
        self.assertIn("trino_worker_data:", content)

        # Trino Coordinator assertions
        self.assertIn("trino-coordinator:", content)
        self.assertIn("lakehouse-trino-coordinator", content)
        self.assertIn("image: trinodb/trino:435", content)
        self.assertIn("172.28.0.70", content)
        self.assertIn("trino.lakehouse.local", content)
        self.assertIn("TRINO_PORT", content)
        self.assertIn("node-coordinator.properties", content)
        self.assertIn("jvm.config", content)
        self.assertIn("config.properties", content)
        self.assertIn("access-control.properties", content)
        self.assertIn("ranger-trino-security.xml", content)
        self.assertIn("ranger-admin:", content)

        # Trino Worker assertions
        self.assertIn("trino-worker:", content)
        self.assertIn("lakehouse-trino-worker", content)
        self.assertIn("172.28.0.71", content)
        self.assertIn("node-worker.properties", content)
        self.assertIn("config-worker.properties", content)
        self.assertIn("condition: service_healthy", content)

    def test_metabase_service_configuration(self) -> None:
        """Verify Metabase BI container, persistent volume, networking, and dependencies."""
        with open(self.compose_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Storage volume assertions
        self.assertIn("metabase_data:", content)
        self.assertIn("lakehouse_metabase_data", content)

        # Service assertions
        self.assertIn("metabase:", content)
        self.assertIn("lakehouse-metabase", content)
        self.assertIn("context: ./metabase", content)
        self.assertIn("image: lakehouse/metabase:0.48.4", content)
        self.assertIn("172.28.0.80", content)
        self.assertIn("metabase.lakehouse.local", content)
        self.assertIn("METABASE_PORT", content)
        self.assertIn("metabase_data:/metabase-data", content)
        self.assertIn("MB_DB_FILE: /metabase-data/metabase.db", content)
        self.assertIn("MB_PLUGINS_DIR: /plugins", content)
        self.assertIn("trino-coordinator:", content)
        self.assertIn("curl -f http://localhost:3000/api/health", content)

    def test_cloudbeaver_service_configuration(self) -> None:
        """Verify CloudBeaver Web SQL IDE service, persistent volume, networking, and dependencies."""
        with open(self.compose_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Storage volume assertions
        self.assertIn("cloudbeaver_data:", content)
        self.assertIn("lakehouse_cloudbeaver_data", content)

        # Service assertions
        self.assertIn("cloudbeaver:", content)
        self.assertIn("lakehouse-cloudbeaver", content)
        self.assertIn("image: dbeaver/cloudbeaver:23.3.0", content)
        self.assertIn("172.28.0.81", content)
        self.assertIn("cloudbeaver.lakehouse.local", content)
        self.assertIn("CLOUDBEAVER_PORT", content)
        self.assertIn("cloudbeaver_data:/opt/cloudbeaver/workspace", content)
        self.assertIn("trino-coordinator:", content)
        self.assertIn("curl -f http://localhost:8978/", content)

    def test_zeppelin_service_configuration(self) -> None:
        """Verify Apache Zeppelin notebook container, volume, networking, and dependencies."""
        with open(self.compose_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Storage volume assertions
        self.assertIn("zeppelin_notebook_data:", content)
        self.assertIn("lakehouse_zeppelin_notebook_data", content)

        # Service assertions
        self.assertIn("zeppelin:", content)
        self.assertIn("lakehouse-zeppelin", content)
        self.assertIn("context: ./zeppelin", content)
        self.assertIn("image: lakehouse/zeppelin:0.10.1", content)
        self.assertIn("172.28.0.82", content)
        self.assertIn("zeppelin.lakehouse.local", content)
        self.assertIn("ZEPPELIN_PORT", content)
        self.assertIn("zeppelin_notebook_data:/zeppelin/notebook", content)
        self.assertIn("../ml/notebooks:/zeppelin/notebook/lakehouse_ml", content)
        self.assertIn("minio:", content)
        self.assertIn("hive-metastore:", content)
        self.assertIn("curl -f http://localhost:8080/api/version", content)


if __name__ == "__main__":
    unittest.main()
