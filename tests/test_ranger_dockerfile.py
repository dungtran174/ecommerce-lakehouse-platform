"""Unit tests for Apache Ranger Admin Dockerfile, entrypoint script, and configuration."""

from __future__ import annotations

import os
import unittest

from docker.ranger.scripts.ranger_admin_server import RangerStorage


class TestRangerDockerfileAndConfig(unittest.TestCase):
    """Test suite validating Dockerfile directives, entrypoint logic, and Ranger storage."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate Ranger configuration and Dockerfile paths."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.ranger_dir = os.path.join(cls.root_dir, "docker", "ranger")
        cls.dockerfile_path = os.path.join(cls.ranger_dir, "Dockerfile")
        cls.entrypoint_path = os.path.join(cls.ranger_dir, "entrypoint.sh")
        cls.properties_path = os.path.join(cls.ranger_dir, "conf", "install.properties")
        cls.server_script_path = os.path.join(
            cls.ranger_dir, "scripts", "ranger_admin_server.py"
        )

    def test_ranger_files_exist(self) -> None:
        """Verify all Apache Ranger service files are present on disk."""
        self.assertTrue(
            os.path.exists(self.dockerfile_path),
            "docker/ranger/Dockerfile must exist",
        )
        self.assertTrue(
            os.path.exists(self.entrypoint_path),
            "docker/ranger/entrypoint.sh must exist",
        )
        self.assertTrue(
            os.path.exists(self.properties_path),
            "docker/ranger/conf/install.properties must exist",
        )
        self.assertTrue(
            os.path.exists(self.server_script_path),
            "docker/ranger/scripts/ranger_admin_server.py must exist",
        )

    def test_dockerfile_base_image_and_directives(self) -> None:
        """Verify Ranger Dockerfile directives, Java base image, and user isolation."""
        with open(self.dockerfile_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("FROM eclipse-temurin:8-jre", content)
        self.assertIn("ARG RANGER_VERSION=2.4.0", content)
        self.assertIn("ARG POSTGRES_CONNECTOR_VERSION=42.6.0", content)
        self.assertIn("postgresql-client", content)
        self.assertIn("postgresql-${POSTGRES_CONNECTOR_VERSION}.jar", content)
        self.assertIn("EXPOSE 6080", content)
        self.assertIn("useradd -r -g ranger", content)
        self.assertIn("USER ranger", content)
        self.assertIn('ENTRYPOINT ["/opt/ranger-admin/entrypoint.sh"]', content)
        self.assertIn('CMD ["ranger-admin"]', content)

    def test_install_properties_configuration(self) -> None:
        """Verify install.properties defines database connections and HTTP port."""
        with open(self.properties_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("DB_FLAVOR=POSTGRES", content)
        self.assertIn("db_host=ranger-db", content)
        self.assertIn("db_port=5432", content)
        self.assertIn("db_name=ranger", content)
        self.assertIn("db_user=rangeradmin", content)
        self.assertIn("ranger_server_http_port=6080", content)

    def test_entrypoint_script_structure(self) -> None:
        """Verify entrypoint script checks database readiness and executes server."""
        with open(self.entrypoint_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("#!/usr/bin/env bash", content)
        self.assertIn("set -eo pipefail", content)
        self.assertIn("nc -z", content)
        self.assertIn("ranger_admin_server.py", content)
        self.assertIn('exec "$@"', content)

    def test_ranger_storage_service_and_policy_operations(self) -> None:
        """Verify in-memory/DB storage operations for service definitions and policies."""
        storage = RangerStorage()

        # Service Definition
        trino_def = storage.get_service_def("trino")
        self.assertIsNotNone(trino_def)
        self.assertEqual(trino_def.get("name"), "trino")

        # Create Service
        svc_payload = {
            "name": "dev_trino",
            "type": "trino",
            "isEnabled": True,
            "configs": {"jdbc.driverClassName": "io.trino.jdbc.TrinoDriver"},
        }
        created_svc = storage.create_service(svc_payload)
        self.assertEqual(created_svc["name"], "dev_trino")
        self.assertIsNotNone(created_svc.get("id"))

        # Lookup Service
        fetched_svc = storage.get_service("dev_trino")
        self.assertIsNotNone(fetched_svc)
        self.assertEqual(fetched_svc["name"], "dev_trino")

        # Create Policy
        policy_payload = {
            "service": "dev_trino",
            "name": "allow_all_marketing",
            "policyType": 0,
            "isEnabled": True,
            "resources": {
                "catalog": {"values": ["lakehouse"]},
                "schema": {"values": ["marketing"]},
            },
        }
        saved_policy = storage.save_policy(policy_payload)
        self.assertEqual(saved_policy["name"], "allow_all_marketing")
        policy_id = saved_policy.get("id")
        self.assertIsNotNone(policy_id)

        # List Policies
        policies = storage.list_policies(service_name="dev_trino")
        self.assertEqual(len(policies), 1)
        self.assertEqual(policies[0]["name"], "allow_all_marketing")

        # Delete Policy
        deleted = storage.delete_policy(policy_id)
        self.assertTrue(deleted)
        self.assertEqual(len(storage.list_policies(service_name="dev_trino")), 0)

        # Delete Service
        deleted_svc = storage.delete_service("dev_trino")
        self.assertTrue(deleted_svc)


if __name__ == "__main__":
    unittest.main()
