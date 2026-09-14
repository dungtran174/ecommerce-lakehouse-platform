"""Unit tests for Trino Coordinator, Worker, JVM, and Catalog configurations."""

from __future__ import annotations

import os
import unittest


class TestTrinoConfig(unittest.TestCase):
    """Test suite validating Trino Coordinator and Worker properties, JVM flags, and catalogs."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate Trino configuration paths."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.trino_etc_dir = os.path.join(cls.root_dir, "docker", "trino", "etc")
        cls.trino_catalog_dir = os.path.join(cls.root_dir, "docker", "trino", "catalog")

        cls.coord_node_file = os.path.join(
            cls.trino_etc_dir, "node-coordinator.properties"
        )
        cls.worker_node_file = os.path.join(cls.trino_etc_dir, "node-worker.properties")
        cls.jvm_file = os.path.join(cls.trino_etc_dir, "jvm.config")
        cls.coord_config_file = os.path.join(cls.trino_etc_dir, "config.properties")
        cls.worker_config_file = os.path.join(
            cls.trino_etc_dir, "config-worker.properties"
        )
        cls.tpch_catalog_file = os.path.join(cls.trino_catalog_dir, "tpch.properties")
        cls.tpcds_catalog_file = os.path.join(cls.trino_catalog_dir, "tpcds.properties")
        cls.delta_catalog_file = os.path.join(cls.trino_catalog_dir, "delta.properties")
        cls.lakehouse_catalog_file = os.path.join(
            cls.trino_catalog_dir, "lakehouse.properties"
        )
        cls.hive_catalog_file = os.path.join(cls.trino_catalog_dir, "hive.properties")
        cls.mysql_catalog_file = os.path.join(cls.trino_catalog_dir, "mysql.properties")

    def _read_properties(self, file_path: str) -> dict[str, str]:
        """Parse simple Java properties file into Python dictionary."""
        props = {}
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    props[k.strip()] = v.strip()
        return props

    def test_trino_config_files_exist(self) -> None:
        """Verify all Trino coordinator, worker, JVM, and catalog files exist."""
        self.assertTrue(
            os.path.exists(self.coord_node_file),
            "node-coordinator.properties must exist",
        )
        self.assertTrue(
            os.path.exists(self.worker_node_file),
            "node-worker.properties must exist",
        )
        self.assertTrue(os.path.exists(self.jvm_file), "jvm.config must exist")
        self.assertTrue(
            os.path.exists(self.coord_config_file), "config.properties must exist"
        )
        self.assertTrue(
            os.path.exists(self.worker_config_file),
            "config-worker.properties must exist",
        )
        self.assertTrue(
            os.path.exists(self.tpch_catalog_file), "tpch.properties must exist"
        )
        self.assertTrue(
            os.path.exists(self.tpcds_catalog_file), "tpcds.properties must exist"
        )
        self.assertTrue(
            os.path.exists(self.delta_catalog_file), "delta.properties must exist"
        )
        self.assertTrue(
            os.path.exists(self.lakehouse_catalog_file),
            "lakehouse.properties must exist",
        )
        self.assertTrue(
            os.path.exists(self.hive_catalog_file), "hive.properties must exist"
        )
        self.assertTrue(
            os.path.exists(self.mysql_catalog_file), "mysql.properties must exist"
        )

    def test_trino_coordinator_config(self) -> None:
        """Verify Trino Coordinator configuration parameters."""
        props = self._read_properties(self.coord_config_file)

        self.assertEqual(props.get("coordinator"), "true")
        self.assertEqual(props.get("node-scheduler.include-coordinator"), "false")
        self.assertEqual(props.get("http-server.http.port"), "8085")
        self.assertEqual(props.get("discovery.uri"), "http://trino-coordinator:8085")
        self.assertEqual(props.get("query.max-memory"), "4GB")
        self.assertEqual(props.get("query.max-memory-per-node"), "1GB")
        self.assertEqual(props.get("query.max-total-memory-per-node"), "2GB")

    def test_trino_worker_config(self) -> None:
        """Verify Trino Worker configuration parameters."""
        props = self._read_properties(self.worker_config_file)

        self.assertEqual(props.get("coordinator"), "false")
        self.assertNotIn("node-scheduler.include-coordinator", props)
        self.assertEqual(props.get("http-server.http.port"), "8085")
        self.assertEqual(props.get("discovery.uri"), "http://trino-coordinator:8085")
        self.assertEqual(props.get("query.max-memory"), "4GB")
        self.assertEqual(props.get("query.max-memory-per-node"), "1GB")

    def test_trino_jvm_config(self) -> None:
        """Verify JVM optimization flags and garbage collection parameters."""
        with open(self.jvm_file, "r", encoding="utf-8") as f:
            jvm_flags = [line.strip() for line in f if line.strip()]

        self.assertIn("-server", jvm_flags)
        self.assertIn("-Xmx2G", jvm_flags)
        self.assertIn("-XX:+UseG1GC", jvm_flags)
        self.assertIn("-XX:G1HeapRegionSize=32M", jvm_flags)
        self.assertIn("-XX:+ExplicitGCInvokesConcurrent", jvm_flags)
        self.assertIn("-XX:+ExitOnOutOfMemoryError", jvm_flags)

    def test_trino_node_properties(self) -> None:
        """Verify node properties for coordinator and worker."""
        coord_props = self._read_properties(self.coord_node_file)
        self.assertEqual(coord_props.get("node.environment"), "production")
        self.assertEqual(coord_props.get("node.id"), "trino-coordinator-01")
        self.assertEqual(coord_props.get("node.data-dir"), "/data/trino")

        worker_props = self._read_properties(self.worker_node_file)
        self.assertEqual(worker_props.get("node.environment"), "production")
        self.assertEqual(worker_props.get("node.id"), "trino-worker-01")
        self.assertEqual(worker_props.get("node.data-dir"), "/data/trino")
        self.assertNotEqual(coord_props["node.id"], worker_props["node.id"])

    def test_trino_catalogs(self) -> None:
        """Verify benchmark, Lakehouse Delta, Hive, and MySQL catalog connectors."""
        tpch_props = self._read_properties(self.tpch_catalog_file)
        self.assertEqual(tpch_props.get("connector.name"), "tpch")

        tpcds_props = self._read_properties(self.tpcds_catalog_file)
        self.assertEqual(tpcds_props.get("connector.name"), "tpcds")

        delta_props = self._read_properties(self.delta_catalog_file)
        self.assertEqual(delta_props.get("connector.name"), "delta-lake")

        lakehouse_props = self._read_properties(self.lakehouse_catalog_file)
        self.assertEqual(lakehouse_props.get("connector.name"), "delta-lake")

        hive_props = self._read_properties(self.hive_catalog_file)
        self.assertEqual(hive_props.get("connector.name"), "hive")

        mysql_props = self._read_properties(self.mysql_catalog_file)
        self.assertEqual(mysql_props.get("connector.name"), "mysql")


if __name__ == "__main__":
    unittest.main()
