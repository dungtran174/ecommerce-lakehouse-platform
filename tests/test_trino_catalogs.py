"""Unit tests for Trino catalog connectors (Delta Lake, Hive, MySQL, TPCH, TPCDS)."""

from __future__ import annotations

import os
import unittest


class TestTrinoCatalogs(unittest.TestCase):
    """Test suite validating Trino catalog connector configurations."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate Trino catalog directory and file paths."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.catalog_dir = os.path.join(cls.root_dir, "docker", "trino", "catalog")

        cls.delta_file = os.path.join(cls.catalog_dir, "delta.properties")
        cls.lakehouse_file = os.path.join(cls.catalog_dir, "lakehouse.properties")
        cls.hive_file = os.path.join(cls.catalog_dir, "hive.properties")
        cls.mysql_file = os.path.join(cls.catalog_dir, "mysql.properties")
        cls.tpch_file = os.path.join(cls.catalog_dir, "tpch.properties")
        cls.tpcds_file = os.path.join(cls.catalog_dir, "tpcds.properties")

    def _read_properties(self, file_path: str) -> dict[str, str]:
        """Parse Java properties file into a Python dictionary."""
        props = {}
        self.assertTrue(os.path.exists(file_path), f"File does not exist: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    props[k.strip()] = v.strip()
        return props

    def test_catalog_files_exist(self) -> None:
        """Verify all essential Trino catalog files exist in docker/trino/catalog."""
        expected_files = [
            self.delta_file,
            self.lakehouse_file,
            self.hive_file,
            self.mysql_file,
            self.tpch_file,
            self.tpcds_file,
        ]
        for f in expected_files:
            self.assertTrue(os.path.exists(f), f"Expected catalog file missing: {f}")

    def test_delta_catalog_configuration(self) -> None:
        """Verify Delta Lake catalog properties for MinIO storage and HMS."""
        props = self._read_properties(self.delta_file)

        self.assertEqual(props.get("connector.name"), "delta-lake")
        self.assertEqual(
            props.get("hive.metastore.uri"), "thrift://hive-metastore:9083"
        )
        self.assertEqual(props.get("fs.native-s3.enabled"), "true")
        self.assertEqual(props.get("s3.endpoint"), "http://minio:9000")
        self.assertEqual(props.get("s3.region"), "us-east-1")
        self.assertEqual(props.get("s3.path-style-access"), "true")
        self.assertEqual(props.get("s3.aws-access-key"), "minioadmin")
        self.assertEqual(props.get("s3.aws-secret-key"), "minioadmin")
        self.assertEqual(props.get("s3.ssl.enabled"), "false")
        self.assertEqual(props.get("delta.register-table-procedure.enabled"), "true")
        self.assertEqual(props.get("delta.metadata.cache-ttl"), "10m")

    def test_lakehouse_catalog_configuration(self) -> None:
        """Verify Lakehouse catalog configuration matches Delta Lake for Ranger policies."""
        delta_props = self._read_properties(self.delta_file)
        lakehouse_props = self._read_properties(self.lakehouse_file)

        self.assertEqual(lakehouse_props.get("connector.name"), "delta-lake")
        self.assertEqual(
            lakehouse_props.get("hive.metastore.uri"),
            delta_props.get("hive.metastore.uri"),
        )
        self.assertEqual(
            lakehouse_props.get("s3.endpoint"), delta_props.get("s3.endpoint")
        )
        self.assertEqual(
            lakehouse_props.get("s3.path-style-access"),
            delta_props.get("s3.path-style-access"),
        )
        self.assertEqual(
            lakehouse_props.get("s3.aws-access-key"),
            delta_props.get("s3.aws-access-key"),
        )
        self.assertEqual(
            lakehouse_props.get("s3.aws-secret-key"),
            delta_props.get("s3.aws-secret-key"),
        )

    def test_hive_catalog_configuration(self) -> None:
        """Verify Hive catalog properties for MinIO storage and HMS."""
        props = self._read_properties(self.hive_file)

        self.assertEqual(props.get("connector.name"), "hive")
        self.assertEqual(
            props.get("hive.metastore.uri"), "thrift://hive-metastore:9083"
        )
        self.assertEqual(props.get("s3.endpoint"), "http://minio:9000")
        self.assertEqual(props.get("s3.path-style-access"), "true")
        self.assertEqual(props.get("s3.aws-access-key"), "minioadmin")
        self.assertEqual(props.get("s3.aws-secret-key"), "minioadmin")
        self.assertEqual(props.get("s3.ssl.enabled"), "false")
        self.assertEqual(props.get("hive.s3.endpoint"), "http://minio:9000")
        self.assertEqual(props.get("hive.storage-format"), "PARQUET")

    def test_mysql_catalog_configuration(self) -> None:
        """Verify MySQL catalog connector properties for OLTP federation."""
        props = self._read_properties(self.mysql_file)

        self.assertEqual(props.get("connector.name"), "mysql")
        self.assertEqual(
            props.get("connection-url"),
            "jdbc:mysql://mysql-oltp:3306/ecommerce_oltp",
        )
        self.assertEqual(props.get("connection-user"), "lakehouse_user")
        self.assertEqual(props.get("connection-password"), "lakehouse_password")

    def test_benchmark_catalogs_configuration(self) -> None:
        """Verify TPCH and TPCDS benchmark catalog connectors."""
        tpch_props = self._read_properties(self.tpch_file)
        self.assertEqual(tpch_props.get("connector.name"), "tpch")

        tpcds_props = self._read_properties(self.tpcds_file)
        self.assertEqual(tpcds_props.get("connector.name"), "tpcds")


if __name__ == "__main__":
    unittest.main()
