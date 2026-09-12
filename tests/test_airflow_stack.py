"""Unit tests for Apache Airflow service stack and configuration."""

from __future__ import annotations

import configparser
import os
import unittest

import yaml


class TestAirflowStack(unittest.TestCase):
    """Test suite validating Airflow docker-compose services and airflow.cfg configuration."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate Airflow configuration and docker-compose files."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.compose_file = os.path.join(cls.root_dir, "docker", "docker-compose.yml")
        cls.airflow_cfg_file = os.path.join(
            cls.root_dir, "airflow", "config", "airflow.cfg"
        )
        cls.env_example_file = os.path.join(cls.root_dir, "docker", ".env.example")

    def test_airflow_files_exist(self) -> None:
        """Verify airflow.cfg, dags folder, and plugins folder exist on disk."""
        self.assertTrue(os.path.exists(self.airflow_cfg_file), "airflow.cfg must exist")
        self.assertTrue(
            os.path.isdir(os.path.join(self.root_dir, "airflow", "dags")),
            "airflow/dags directory must exist",
        )
        self.assertTrue(
            os.path.isdir(os.path.join(self.root_dir, "airflow", "plugins")),
            "airflow/plugins directory must exist",
        )

    def test_airflow_cfg_structure_and_settings(self) -> None:
        """Verify airflow.cfg contains required sections, LocalExecutor, and Postgres connection."""
        config = configparser.ConfigParser()
        with open(self.airflow_cfg_file, "r", encoding="utf-8") as f:
            config.read_file(f)

        required_sections = [
            "core",
            "database",
            "logging",
            "webserver",
            "scheduler",
            "api",
        ]
        for section in required_sections:
            self.assertIn(
                section, config.sections(), f"Section [{section}] must be present"
            )

        # Core section assertions
        self.assertEqual(config.get("core", "executor"), "LocalExecutor")
        self.assertEqual(config.get("core", "dags_are_paused_at_creation"), "True")
        self.assertEqual(config.get("core", "load_examples"), "False")
        self.assertEqual(config.get("core", "load_default_connections"), "False")
        self.assertIn("postgresql+psycopg2://", config.get("core", "sql_alchemy_conn"))
        self.assertTrue(config.has_option("core", "fernet_key"))

        # Database section assertions
        self.assertIn(
            "postgresql+psycopg2://", config.get("database", "sql_alchemy_conn")
        )
        self.assertEqual(config.get("database", "sql_alchemy_pool_size"), "10")

        # Webserver section assertions
        self.assertEqual(config.get("webserver", "web_server_port"), "8080")
        self.assertEqual(config.get("webserver", "rbac"), "True")
        self.assertTrue(config.has_option("webserver", "secret_key"))

        # Scheduler section assertions
        self.assertEqual(config.get("scheduler", "job_heartbeat_sec"), "5")
        self.assertEqual(config.get("scheduler", "scheduler_heartbeat_sec"), "5")

    def test_docker_compose_airflow_services_configuration(self) -> None:
        """Verify docker-compose.yml defines airflow-postgres, init, webserver, and scheduler."""
        with open(self.compose_file, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)

        services = doc.get("services", {})
        volumes = doc.get("volumes", {})

        # Assert volumes
        self.assertIn("airflow_postgres_data", volumes)
        self.assertIn("airflow_logs", volumes)

        # Assert services present
        self.assertIn("airflow-postgres", services)
        self.assertIn("airflow-init", services)
        self.assertIn("airflow-webserver", services)
        self.assertIn("airflow-scheduler", services)

        # Assert postgres backend
        pg = services["airflow-postgres"]
        self.assertEqual(pg.get("image"), "postgres:14")
        self.assertEqual(pg.get("container_name"), "lakehouse-airflow-postgres")
        self.assertEqual(
            pg["networks"]["lakehouse-net"].get("ipv4_address"), "172.28.0.50"
        )
        self.assertIn("healthcheck", pg)

        # Assert webserver
        ws = services["airflow-webserver"]
        self.assertIn("apache/airflow:2.7.3", ws.get("image", ""))
        self.assertEqual(ws.get("container_name"), "lakehouse-airflow-webserver")
        self.assertEqual(
            ws["networks"]["lakehouse-net"].get("ipv4_address"), "172.28.0.52"
        )
        self.assertIn(
            "airflow.lakehouse.local",
            ws["networks"]["lakehouse-net"].get("aliases", []),
        )
        self.assertEqual(
            ws["environment"].get("AIRFLOW__CORE__EXECUTOR"), "LocalExecutor"
        )
        self.assertIn("service_healthy", str(ws.get("depends_on", {})))

        # Assert scheduler
        sch = services["airflow-scheduler"]
        self.assertIn("apache/airflow:2.7.3", sch.get("image", ""))
        self.assertEqual(sch.get("container_name"), "lakehouse-airflow-scheduler")
        self.assertEqual(
            sch["networks"]["lakehouse-net"].get("ipv4_address"), "172.28.0.53"
        )
        self.assertEqual(
            sch["environment"].get("AIRFLOW__CORE__EXECUTOR"), "LocalExecutor"
        )
        self.assertEqual(sch.get("command"), "scheduler")

        # Assert dbt directory mount and configuration
        self.assertIn("../dbt:/opt/airflow/dbt", ws.get("volumes", []))
        self.assertIn("../dbt:/opt/airflow/dbt", sch.get("volumes", []))
        self.assertEqual(ws["environment"].get("DBT_PROJECT_DIR"), "/opt/airflow/dbt")
        self.assertEqual(sch["environment"].get("DBT_PROJECT_DIR"), "/opt/airflow/dbt")

    def test_env_example_airflow_variables(self) -> None:
        """Verify .env.example declares Airflow ports, credentials, and encryption keys."""
        with open(self.env_example_file, "r", encoding="utf-8") as f:
            env_content = f.read()

        required_vars = [
            "AIRFLOW_UID",
            "AIRFLOW_WEBSERVER_PORT",
            "AIRFLOW_METASTORE_PORT",
            "AIRFLOW_DB_NAME",
            "AIRFLOW_DB_USER",
            "AIRFLOW_DB_PASSWORD",
            "_AIRFLOW_WWW_USER_USERNAME",
            "_AIRFLOW_WWW_USER_PASSWORD",
            "AIRFLOW_FERNET_KEY",
            "AIRFLOW_SECRET_KEY",
        ]
        for var in required_vars:
            self.assertIn(
                var, env_content, f"Variable {var} must be declared in .env.example"
            )


if __name__ == "__main__":
    unittest.main()
