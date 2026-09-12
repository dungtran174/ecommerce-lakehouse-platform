"""Unit tests for web clickstream ingestion Airflow DAG (user_activity_logs_pipeline)."""

from __future__ import annotations

import os
import py_compile
import unittest
from unittest.mock import MagicMock, patch

from airflow.dags.user_activity_logs_pipeline import (
    FILE_PATTERN,
    MINIO_CONN_ID,
    S3_BUCKET,
    SFTP_CONN_ID,
    SFTP_REMOTE_DIR,
    dag,
    scan_remote_sftp_logs,
    transfer_clickstream_to_minio,
    verify_bronze_landing,
)


class TestAirflowClickstreamDag(unittest.TestCase):
    """Test suite validating the structure, tasks, and logic of user_activity_logs_pipeline DAG."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate DAG file."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.dag_file = os.path.join(
            cls.root_dir, "airflow", "dags", "user_activity_logs_pipeline.py"
        )

    def test_dag_file_exists_and_compiles(self) -> None:
        """Verify DAG file exists on disk and has valid Python syntax."""
        self.assertTrue(os.path.exists(self.dag_file), "DAG file must exist")
        compiled = py_compile.compile(self.dag_file, doraise=True)
        self.assertTrue(os.path.exists(compiled))

    def test_dag_metadata_and_properties(self) -> None:
        """Verify DAG identifier, schedule, tags, and execution constraints."""
        self.assertEqual(dag.dag_id, "user_activity_logs_pipeline")
        self.assertEqual(dag.schedule_interval, "@hourly")
        self.assertFalse(dag.catchup)
        self.assertIn("lakehouse", dag.tags)
        self.assertIn("clickstream", dag.tags)
        self.assertIn("sftp", dag.tags)
        self.assertIn("bronze", dag.tags)
        self.assertIn("ingestion", dag.tags)

    def test_configuration_constants(self) -> None:
        """Verify default configuration constants for SFTP and MinIO connections."""
        self.assertEqual(SFTP_CONN_ID, "sftp_default")
        self.assertEqual(MINIO_CONN_ID, "minio_default")
        self.assertEqual(S3_BUCKET, "lakehouse")
        self.assertEqual(SFTP_REMOTE_DIR, "/var/log/ecommerce/clickstream")
        self.assertEqual(FILE_PATTERN, "*.json")

    def test_task_pipeline_dependencies(self) -> None:
        """Verify upstream/downstream task flow relationships."""
        tasks_by_id = {}
        if hasattr(dag, "task_dict") and dag.task_dict:
            tasks_by_id = dag.task_dict
        elif hasattr(dag, "tasks") and dag.tasks:
            tasks_by_id = {t.task_id: t for t in dag.tasks}
        else:
            import airflow.dags.user_activity_logs_pipeline as module

            for attr_name in dir(module):
                val = getattr(module, attr_name)
                if hasattr(val, "task_id"):
                    tasks_by_id[val.task_id] = val

        expected_task_ids = [
            "start_pipeline",
            "scan_sftp_logs",
            "transfer_clickstream_to_minio",
            "verify_bronze_landing",
            "end_pipeline",
        ]
        for task_id in expected_task_ids:
            self.assertIn(task_id, tasks_by_id)

        start_task = tasks_by_id["start_pipeline"]
        scan_task = tasks_by_id["scan_sftp_logs"]
        transfer_task = tasks_by_id["transfer_clickstream_to_minio"]
        verify_task = tasks_by_id["verify_bronze_landing"]
        end_task = tasks_by_id["end_pipeline"]

        # start_pipeline >> scan_sftp_logs
        self.assertIn("scan_sftp_logs", [t.task_id for t in start_task.downstream_list])
        self.assertIn("start_pipeline", [t.task_id for t in scan_task.upstream_list])

        # scan_sftp_logs >> transfer_clickstream_to_minio
        self.assertIn(
            "transfer_clickstream_to_minio",
            [t.task_id for t in scan_task.downstream_list],
        )
        self.assertIn(
            "scan_sftp_logs", [t.task_id for t in transfer_task.upstream_list]
        )

        # transfer_clickstream_to_minio >> verify_bronze_landing
        self.assertIn(
            "verify_bronze_landing", [t.task_id for t in transfer_task.downstream_list]
        )
        self.assertIn(
            "transfer_clickstream_to_minio",
            [t.task_id for t in verify_task.upstream_list],
        )

        # verify_bronze_landing >> end_pipeline
        self.assertIn("end_pipeline", [t.task_id for t in verify_task.downstream_list])
        self.assertIn(
            "verify_bronze_landing", [t.task_id for t in end_task.upstream_list]
        )

    @patch("airflow.plugins.sftp_hook.SFTPHook")
    def test_scan_remote_sftp_logs(self, mock_sftp_cls: MagicMock) -> None:
        """Verify scan_remote_sftp_logs lists files from SFTP remote directory."""
        mock_hook = MagicMock()
        mock_hook.list_files.return_value = [
            "clickstream_20250101_00.json",
            "clickstream_20250101_01.json",
        ]
        mock_sftp_cls.return_value.__enter__.return_value = mock_hook

        result = scan_remote_sftp_logs()
        self.assertEqual(len(result), 2)
        self.assertIn("clickstream_20250101_00.json", result)
        mock_hook.list_files.assert_called_once_with(
            "/var/log/ecommerce/clickstream", pattern="*.json"
        )

    @patch("airflow.plugins.minio_hook.MinIOHook")
    @patch("airflow.plugins.sftp_hook.SFTPHook")
    def test_transfer_clickstream_to_minio(
        self, mock_sftp_cls: MagicMock, mock_minio_cls: MagicMock
    ) -> None:
        """Verify transfer_clickstream_to_minio transfers files to partitioned S3 destination."""
        mock_sftp = MagicMock()
        mock_sftp.read_file_content.return_value = b'{"event_id": "evt_001"}\n'
        mock_sftp_cls.return_value.__enter__.return_value = mock_sftp

        mock_minio = MagicMock()
        mock_minio_cls.return_value = mock_minio

        # Simulate context with ti.xcom_pull
        mock_ti = MagicMock()
        mock_ti.xcom_pull.return_value = ["clickstream_2025-01-01_10.json"]

        context = {"ti": mock_ti, "ds": "2025-01-01"}
        transferred = transfer_clickstream_to_minio(**context)

        self.assertEqual(transferred, 1)
        mock_minio.create_bucket.assert_called_once_with("lakehouse")
        mock_sftp.read_file_content.assert_called_once_with(
            "/var/log/ecommerce/clickstream/clickstream_2025-01-01_10.json"
        )
        mock_minio.upload_bytes.assert_called_once_with(
            data=b'{"event_id": "evt_001"}\n',
            bucket_name="lakehouse",
            object_key="bronze/clickstream/ingest_date=2025-01-01/clickstream_2025-01-01_10.json",
        )

    @patch("airflow.plugins.minio_hook.MinIOHook")
    def test_verify_bronze_landing(self, mock_minio_cls: MagicMock) -> None:
        """Verify verify_bronze_landing checks presence of files in target prefix."""
        mock_minio = MagicMock()
        mock_minio.list_objects.return_value = [
            "bronze/clickstream/ingest_date=2025-01-01/clickstream_2025-01-01_10.json"
        ]
        mock_minio_cls.return_value = mock_minio

        context = {"ds": "2025-01-01"}
        result = verify_bronze_landing(**context)
        self.assertTrue(result)
        mock_minio.list_objects.assert_called_once_with(
            "lakehouse", prefix="bronze/clickstream/ingest_date=2025-01-01"
        )


if __name__ == "__main__":
    unittest.main()
