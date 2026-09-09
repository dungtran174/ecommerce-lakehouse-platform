"""Unit tests for Hive Metastore XML configuration and entrypoint script."""

from __future__ import annotations

import os
import subprocess
import unittest
import xml.etree.ElementTree as ET


class TestHiveMetastoreConfig(unittest.TestCase):
    """Test suite validating metastore-site.xml and entrypoint.sh configurations."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate configuration file paths."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.conf_dir = os.path.join(cls.root_dir, "docker", "hive-metastore", "conf")
        cls.xml_file = os.path.join(cls.conf_dir, "metastore-site.xml")
        cls.entrypoint_file = os.path.join(
            cls.root_dir, "docker", "hive-metastore", "entrypoint.sh"
        )

    def test_metastore_site_xml_valid_and_structured(self) -> None:
        """Verify metastore-site.xml is well-formed XML and contains expected properties."""
        self.assertTrue(os.path.exists(self.xml_file), "metastore-site.xml must exist")

        tree = ET.parse(self.xml_file)
        root = tree.getroot()
        self.assertEqual(root.tag, "configuration")

        # Parse properties into a dictionary
        properties: dict[str, str] = {}
        for prop in root.findall("property"):
            name = prop.find("name")
            value = prop.find("value")
            if name is not None and name.text and value is not None and value.text:
                properties[name.text.strip()] = value.text.strip()

        # Metastore Thrift settings
        self.assertEqual(
            properties.get("metastore.thrift.uris"),
            "thrift://0.0.0.0:9083",
        )
        self.assertIn("s3a://lakehouse", properties.get("metastore.warehouse.dir", ""))

        # MySQL backend properties
        self.assertEqual(
            properties.get("javax.jdo.option.ConnectionDriverName"),
            "com.mysql.cj.jdbc.Driver",
        )
        self.assertIn(
            "jdbc:mysql://", properties.get("javax.jdo.option.ConnectionURL", "")
        )

        # S3A MinIO connector properties
        self.assertEqual(
            properties.get("fs.s3a.impl"),
            "org.apache.hadoop.fs.s3a.S3AFileSystem",
        )
        self.assertEqual(properties.get("fs.s3a.path.style.access"), "true")
        self.assertEqual(properties.get("fs.s3a.connection.ssl.enabled"), "false")
        self.assertIn("9000", properties.get("fs.s3a.endpoint", ""))

        # Auto-creation schema properties
        self.assertEqual(
            properties.get("hive.metastore.schema.verification"),
            "false",
        )
        self.assertEqual(
            properties.get("datanucleus.schema.autoCreateAll"),
            "true",
        )

    def test_entrypoint_script_validity_and_logic(self) -> None:
        """Verify entrypoint.sh exists, is executable, has valid shell syntax, and required logic."""
        self.assertTrue(
            os.path.exists(self.entrypoint_file),
            "entrypoint.sh must exist",
        )
        self.assertTrue(
            os.access(self.entrypoint_file, os.X_OK),
            "entrypoint.sh must be executable",
        )

        # Check shell syntax
        result = subprocess.run(
            ["/bin/sh", "-n", self.entrypoint_file],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"entrypoint.sh shell syntax check failed: {result.stderr}",
        )

        with open(self.entrypoint_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Database readiness check
        self.assertIn("nc -z", content)
        self.assertIn("METASTORE_DB_HOST", content)

        # Dynamic configuration generation
        self.assertIn("metastore-site.xml", content)
        self.assertIn("MINIO_HOST", content)

        # Schema initialization and service start
        self.assertIn("schematool", content)
        self.assertIn("start-metastore", content)


if __name__ == "__main__":
    unittest.main()
