"""Unit tests for Trino Apache Ranger security plugin integration."""

from __future__ import annotations

import os
import unittest
import xml.etree.ElementTree as ET
from typing import Any

from docker.ranger.scripts.ranger_admin_server import RangerStorage


class TestTrinoRangerIntegration(unittest.TestCase):
    """Test suite validating Trino Apache Ranger access control and security configurations."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate Trino configuration paths and Ranger security files."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.trino_etc_dir = os.path.join(cls.root_dir, "docker", "trino", "etc")
        cls.compose_file = os.path.join(cls.root_dir, "docker", "docker-compose.yml")

        cls.access_control_file = os.path.join(
            cls.trino_etc_dir, "access-control.properties"
        )
        cls.ranger_security_file = os.path.join(
            cls.trino_etc_dir, "ranger-trino-security.xml"
        )
        cls.ranger_audit_file = os.path.join(
            cls.trino_etc_dir, "ranger-trino-audit.xml"
        )
        cls.ranger_ssl_file = os.path.join(
            cls.trino_etc_dir, "ranger-trino-policymgr-ssl.xml"
        )

    def _read_properties(self, file_path: str) -> dict[str, str]:
        """Parse Java properties file into Python dictionary."""
        props = {}
        self.assertTrue(os.path.exists(file_path), f"File does not exist: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    props[k.strip()] = v.strip()
        return props

    def _read_xml_properties(self, file_path: str) -> dict[str, str]:
        """Parse Hadoop-style configuration XML into Python dictionary."""
        self.assertTrue(
            os.path.exists(file_path), f"XML file does not exist: {file_path}"
        )
        tree = ET.parse(file_path)
        root = tree.getroot()
        props = {}
        for prop in root.findall("property"):
            name_elem = prop.find("name")
            value_elem = prop.find("value")
            if name_elem is not None and name_elem.text:
                val = (
                    value_elem.text.strip()
                    if value_elem is not None and value_elem.text
                    else ""
                )
                props[name_elem.text.strip()] = val
        return props

    def test_ranger_config_files_exist(self) -> None:
        """Verify all essential Ranger configuration files exist in docker/trino/etc."""
        self.assertTrue(
            os.path.exists(self.access_control_file),
            "access-control.properties must exist",
        )
        self.assertTrue(
            os.path.exists(self.ranger_security_file),
            "ranger-trino-security.xml must exist",
        )
        self.assertTrue(
            os.path.exists(self.ranger_audit_file),
            "ranger-trino-audit.xml must exist",
        )
        self.assertTrue(
            os.path.exists(self.ranger_ssl_file),
            "ranger-trino-policymgr-ssl.xml must exist",
        )

    def test_access_control_properties(self) -> None:
        """Verify system access control configuration parameters for Ranger."""
        props = self._read_properties(self.access_control_file)

        self.assertEqual(props.get("access-control.name"), "ranger")
        self.assertEqual(props.get("ranger.trino-service-name"), "dev_trino")
        self.assertEqual(
            props.get("ranger.policy-cache-dir"), "/data/trino/ranger/cache"
        )
        self.assertEqual(props.get("ranger.poll-interval"), "30s")

    def test_ranger_security_xml_properties(self) -> None:
        """Verify Ranger Trino security XML parameters matching Ranger service repository."""
        props = self._read_xml_properties(self.ranger_security_file)

        self.assertEqual(props.get("ranger.plugin.trino.service.name"), "dev_trino")
        self.assertEqual(
            props.get("ranger.plugin.trino.policy.source.impl"),
            "org.apache.ranger.admin.client.RangerAdminRESTClient",
        )
        self.assertEqual(
            props.get("ranger.plugin.trino.policy.rest.url"),
            "http://ranger-admin:6080",
        )
        self.assertEqual(
            props.get("ranger.plugin.trino.policy.pollIntervalMs"), "30000"
        )
        self.assertEqual(
            props.get("ranger.plugin.trino.policy.cache.dir"),
            "/data/trino/ranger/cache",
        )
        self.assertEqual(
            props.get("ranger.plugin.trino.policy.rest.client.connection.timeoutMs"),
            "120000",
        )
        self.assertEqual(
            props.get("ranger.plugin.trino.policy.rest.client.read.timeoutMs"),
            "30000",
        )

    def test_ranger_audit_xml_properties(self) -> None:
        """Verify Ranger Trino audit XML configuration for log4j and storage."""
        props = self._read_xml_properties(self.ranger_audit_file)

        self.assertEqual(props.get("xasecure.audit.is.enabled"), "true")
        self.assertEqual(props.get("xasecure.audit.destination.log4j"), "true")
        self.assertEqual(props.get("xasecure.audit.destination.solr"), "false")
        self.assertEqual(props.get("xasecure.audit.destination.hdfs"), "false")

    def test_ranger_ssl_xml_properties(self) -> None:
        """Verify Ranger Trino SSL XML contains keystore and truststore property nodes."""
        props = self._read_xml_properties(self.ranger_ssl_file)

        self.assertIn("xasecure.policymgr.clientssl.keystore", props)
        self.assertIn("xasecure.policymgr.clientssl.truststore", props)

    def test_docker_compose_trino_ranger_mounts(self) -> None:
        """Verify docker-compose.yml mounts Ranger configurations in Coordinator & Worker."""
        with open(self.compose_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn(
            "./trino/etc/access-control.properties:/etc/trino/access-control.properties:ro",
            content,
        )
        self.assertIn(
            "./trino/etc/ranger-trino-security.xml:/etc/trino/ranger-trino-security.xml:ro",
            content,
        )
        self.assertIn(
            "./trino/etc/ranger-trino-audit.xml:/etc/trino/ranger-trino-audit.xml:ro",
            content,
        )
        self.assertIn(
            "./trino/etc/ranger-trino-policymgr-ssl.xml:/etc/trino/ranger-trino-policymgr-ssl.xml:ro",
            content,
        )

    def test_ranger_policy_download_compatibility(self) -> None:
        """Verify RangerStorage can serve policies to Trino plugin download endpoint."""
        storage = RangerStorage(use_pg=False)
        test_policy: dict[str, Any] = {
            "name": "test_trino_policy",
            "service": "dev_trino",
            "policyType": 0,
            "resources": {
                "catalog": {"values": ["lakehouse"]},
                "schema": {"values": ["silver"]},
                "table": {"values": ["*"]},
            },
        }
        storage.save_policy(test_policy)

        downloaded_policies = storage.list_policies(service_name="dev_trino")
        self.assertTrue(len(downloaded_policies) > 0)
        found = any(p.get("name") == "test_trino_policy" for p in downloaded_policies)
        self.assertTrue(found, "Saved policy should be retrievable by service_name")


if __name__ == "__main__":
    unittest.main()
