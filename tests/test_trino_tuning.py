"""Unit tests for Trino query execution tuning, concurrency, and metadata caching."""

from __future__ import annotations

import os
import unittest


class TestTrinoTuning(unittest.TestCase):
    """Test suite validating performance tuning for Trino Coordinator, Worker, and Catalogs."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate Trino configuration paths and catalog files."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.trino_etc_dir = os.path.join(cls.root_dir, "docker", "trino", "etc")
        cls.trino_catalog_dir = os.path.join(cls.root_dir, "docker", "trino", "catalog")

        cls.coord_config_file = os.path.join(cls.trino_etc_dir, "config.properties")
        cls.worker_config_file = os.path.join(
            cls.trino_etc_dir, "config-worker.properties"
        )
        cls.delta_file = os.path.join(cls.trino_catalog_dir, "delta.properties")
        cls.lakehouse_file = os.path.join(cls.trino_catalog_dir, "lakehouse.properties")
        cls.hive_file = os.path.join(cls.trino_catalog_dir, "hive.properties")

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

    def test_coordinator_performance_tuning(self) -> None:
        """Verify concurrency, thread pool, and CBO optimizer flags on Coordinator."""
        props = self._read_properties(self.coord_config_file)

        # Concurrency and exchange threads
        self.assertEqual(props.get("task.concurrency"), "8")
        self.assertEqual(props.get("task.http-response-threads"), "8")
        self.assertEqual(props.get("task.info-update-interval"), "2s")
        self.assertEqual(props.get("exchange.client-threads"), "8")

        # CBO and Join Optimization
        self.assertEqual(props.get("join-distribution-type"), "AUTOMATIC")
        self.assertEqual(props.get("optimizer.join-reordering-strategy"), "AUTOMATIC")
        self.assertEqual(props.get("optimizer.optimize-metadata-queries"), "true")

    def test_worker_performance_tuning(self) -> None:
        """Verify concurrency and thread pool settings on Worker."""
        props = self._read_properties(self.worker_config_file)

        self.assertEqual(props.get("task.concurrency"), "8")
        self.assertEqual(props.get("task.http-response-threads"), "8")
        self.assertEqual(props.get("task.info-update-interval"), "2s")
        self.assertEqual(props.get("exchange.client-threads"), "8")

    def test_delta_catalog_metadata_cache_tuning(self) -> None:
        """Verify Delta Lake catalog metadata caching and partition batch parameters."""
        props = self._read_properties(self.delta_file)

        self.assertEqual(props.get("delta.metadata.cache-ttl"), "10m")
        self.assertEqual(props.get("delta.metadata.cache-size"), "1000")
        self.assertEqual(props.get("delta.max-partitions-per-writer"), "100")
        self.assertEqual(props.get("hive.metastore-cache-ttl"), "10m")
        self.assertEqual(props.get("hive.metastore-refresh-interval"), "2m")
        self.assertEqual(props.get("hive.metastore-cache-maximum-size"), "5000")
        self.assertEqual(props.get("hive.metastore.partition-batch-size"), "1000")

    def test_lakehouse_catalog_metadata_cache_tuning(self) -> None:
        """Verify Lakehouse Delta catalog matches tuned caching parameters."""
        props = self._read_properties(self.lakehouse_file)

        self.assertEqual(props.get("delta.metadata.cache-ttl"), "10m")
        self.assertEqual(props.get("delta.metadata.cache-size"), "1000")
        self.assertEqual(props.get("delta.max-partitions-per-writer"), "100")
        self.assertEqual(props.get("hive.metastore-cache-ttl"), "10m")
        self.assertEqual(props.get("hive.metastore-refresh-interval"), "2m")
        self.assertEqual(props.get("hive.metastore-cache-maximum-size"), "5000")
        self.assertEqual(props.get("hive.metastore.partition-batch-size"), "1000")

    def test_hive_catalog_performance_tuning(self) -> None:
        """Verify Hive catalog metadata caching and Parquet optimization."""
        props = self._read_properties(self.hive_file)

        self.assertEqual(props.get("hive.metastore-cache-ttl"), "10m")
        self.assertEqual(props.get("hive.metastore-refresh-interval"), "2m")
        self.assertEqual(props.get("hive.metastore-cache-maximum-size"), "5000")
        self.assertEqual(props.get("hive.metastore.partition-batch-size"), "1000")
        self.assertEqual(props.get("hive.parquet.use-column-names"), "true")


if __name__ == "__main__":
    unittest.main()
