"""Unit tests for Spark default configuration and Hive client site XML."""

from __future__ import annotations

import os
import unittest
import xml.etree.ElementTree as ET


class TestSparkConfig(unittest.TestCase):
    """Test suite validating spark-defaults.conf and hive-site.xml configurations."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate Spark configuration paths."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.conf_dir = os.path.join(cls.root_dir, "docker", "spark", "conf")
        cls.spark_defaults_file = os.path.join(cls.conf_dir, "spark-defaults.conf")
        cls.hive_site_file = os.path.join(cls.conf_dir, "hive-site.xml")

    def test_config_files_exist(self) -> None:
        """Verify spark-defaults.conf and hive-site.xml exist on disk."""
        self.assertTrue(
            os.path.exists(self.spark_defaults_file),
            "spark-defaults.conf must exist",
        )
        self.assertTrue(os.path.exists(self.hive_site_file), "hive-site.xml must exist")

    def test_spark_defaults_delta_and_s3a_properties(self) -> None:
        """Verify Delta Lake, MinIO S3A, and Hive Metastore properties in spark-defaults."""
        with open(self.spark_defaults_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        properties: dict[str, str] = {}
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split(None, 1)
                if len(parts) == 2:
                    properties[parts[0]] = parts[1]

        # Delta Lake extensions
        self.assertEqual(
            properties.get("spark.sql.extensions"),
            "io.delta.sql.DeltaSparkSessionExtension",
        )
        self.assertEqual(
            properties.get("spark.sql.catalog.spark_catalog"),
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        self.assertEqual(properties.get("spark.sql.sources.default"), "delta")

        # S3A MinIO configuration
        self.assertEqual(
            properties.get("spark.hadoop.fs.s3a.impl"),
            "org.apache.hadoop.fs.s3a.S3AFileSystem",
        )
        self.assertIn("minio:9000", properties.get("spark.hadoop.fs.s3a.endpoint", ""))
        self.assertEqual(
            properties.get("spark.hadoop.fs.s3a.path.style.access"), "true"
        )
        self.assertEqual(
            properties.get("spark.hadoop.fs.s3a.connection.ssl.enabled"),
            "false",
        )

        # Hive Metastore integration
        self.assertEqual(
            properties.get("spark.hadoop.hive.metastore.uris"),
            "thrift://hive-metastore:9083",
        )
        self.assertEqual(
            properties.get("spark.sql.warehouse.dir"),
            "s3a://lakehouse/warehouse",
        )

        # Adaptive Query Execution & Thrift
        self.assertEqual(properties.get("spark.sql.adaptive.enabled"), "true")
        self.assertEqual(properties.get("spark.thriftserver.transportMode"), "binary")

    def test_hive_site_xml_structure_and_values(self) -> None:
        """Verify hive-site.xml is well-formed XML and contains expected catalog properties."""
        tree = ET.parse(self.hive_site_file)
        root = tree.getroot()
        self.assertEqual(root.tag, "configuration")

        properties: dict[str, str] = {}
        for prop in root.findall("property"):
            name = prop.find("name")
            value = prop.find("value")
            if name is not None and name.text and value is not None and value.text:
                properties[name.text.strip()] = value.text.strip()

        self.assertEqual(
            properties.get("hive.metastore.uris"),
            "thrift://hive-metastore:9083",
        )
        self.assertEqual(
            properties.get("hive.metastore.warehouse.dir"),
            "s3a://lakehouse/warehouse",
        )
        self.assertEqual(
            properties.get("fs.s3a.impl"),
            "org.apache.hadoop.fs.s3a.S3AFileSystem",
        )
        self.assertEqual(properties.get("fs.s3a.path.style.access"), "true")


if __name__ == "__main__":
    unittest.main()
