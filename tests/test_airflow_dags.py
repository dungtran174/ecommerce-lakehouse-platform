"""Comprehensive DAG integrity, cycle detection, and alerting callback test suite."""

from __future__ import annotations

import glob
import os
import py_compile
import unittest
import urllib.error
from typing import Any
from unittest.mock import MagicMock, patch

from airflow.dags.oltp_data_pipeline import dag as oltp_dag
from airflow.dags.user_activity_logs_pipeline import dag as clickstream_dag
from airflow.plugins.alerting import (
    ALERT_ENVIRONMENT,
    build_alert_payload,
    send_webhook_notification,
    sla_miss_alert,
    task_failure_alert,
    task_retry_alert,
    task_success_alert,
)


class TestAirflowDagsIntegrity(unittest.TestCase):
    """Test suite validating DAG compilation, acyclic topological properties, and alerting."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate Airflow DAGs directory and collect all DAG files."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.dags_dir = os.path.join(cls.root_dir, "airflow", "dags")
        cls.dag_files = glob.glob(os.path.join(cls.dags_dir, "*.py"))
        cls.dags = [oltp_dag, clickstream_dag]

    def test_dag_files_exist_and_compile(self) -> None:
        """Verify all DAG files exist and compile without syntax errors."""
        self.assertGreaterEqual(len(self.dag_files), 2)
        for dag_file in self.dag_files:
            compiled = py_compile.compile(dag_file, doraise=True)
            self.assertTrue(os.path.exists(compiled), f"Failed to compile {dag_file}")

    def test_dag_standards_and_best_practices(self) -> None:
        """Verify production configuration standards across all DAGs."""
        for dag in self.dags:
            dag_id = dag.dag_id
            self.assertIsNotNone(dag_id, "DAG must have a valid identifier")
            self.assertFalse(
                dag.catchup,
                f"DAG '{dag_id}' must set catchup=False to avoid unwanted backfills",
            )
            self.assertGreater(
                len(dag.tags), 0, f"DAG '{dag_id}' must have tags configured"
            )
            self.assertIn(
                "lakehouse", dag.tags, f"DAG '{dag_id}' must have 'lakehouse' tag"
            )

            # Check default_args
            default_args = dag.default_args or {}
            self.assertIn("owner", default_args, f"DAG '{dag_id}' must specify owner")
            self.assertFalse(
                default_args.get("depends_on_past", False),
                f"DAG '{dag_id}' depends_on_past should default to False",
            )
            self.assertGreaterEqual(
                default_args.get("retries", 0),
                1,
                f"DAG '{dag_id}' must configure at least 1 retry",
            )
            self.assertIn(
                "retry_delay",
                default_args,
                f"DAG '{dag_id}' must configure a retry_delay",
            )

    def test_no_task_id_duplicates_within_dags(self) -> None:
        """Verify that every task within a DAG possesses a unique identifier."""
        for dag in self.dags:
            tasks_by_id = {}
            if hasattr(dag, "task_dict") and dag.task_dict:
                tasks_by_id = dag.task_dict
            elif hasattr(dag, "tasks") and dag.tasks:
                tasks_by_id = {t.task_id: t for t in dag.tasks}

            task_ids = list(tasks_by_id.keys())
            self.assertEqual(
                len(task_ids),
                len(set(task_ids)),
                f"Duplicate task IDs discovered in DAG '{dag.dag_id}': {task_ids}",
            )
            self.assertGreaterEqual(
                len(task_ids),
                4,
                f"DAG '{dag.dag_id}' should contain a multi-stage task pipeline",
            )

    @staticmethod
    def _detect_cycle(
        tid: str,
        state: dict[str, int],
        tasks_by_id: dict[str, Any],
    ) -> bool:
        state[tid] = 1  # visiting
        task = tasks_by_id[tid]
        downstream_tasks = getattr(task, "downstream_list", [])
        for down in downstream_tasks:
            down_id = getattr(down, "task_id", str(down))
            if down_id not in state:
                continue
            if state[down_id] == 1:
                return True
            if state[down_id] == 0:
                if TestAirflowDagsIntegrity._detect_cycle(down_id, state, tasks_by_id):
                    return True
        state[tid] = 2  # visited
        return False

    def test_dag_cycle_detection_directed_acyclic_property(self) -> None:
        """Verify that all DAGs are strictly acyclic (no circular task dependencies)."""
        for dag in self.dags:
            tasks_by_id = {}
            if hasattr(dag, "task_dict") and dag.task_dict:
                tasks_by_id = dag.task_dict
            elif hasattr(dag, "tasks") and dag.tasks:
                tasks_by_id = {t.task_id: t for t in dag.tasks}

            state: dict[str, int] = {tid: 0 for tid in tasks_by_id}
            for tid in tasks_by_id:
                if state[tid] == 0:
                    self.assertFalse(
                        self._detect_cycle(tid, state, tasks_by_id),
                        f"Cycle detected in DAG '{dag.dag_id}' involving task '{tid}'",
                    )

    def test_build_alert_payload(self) -> None:
        """Verify alert payload extraction from mock Airflow execution context."""
        mock_ti = MagicMock()
        mock_ti.task_id = "extract_orders"
        mock_ti.try_number = 2
        mock_ti.log_url = "http://airflow.lakehouse.local:8080/log?dag_id=test"

        mock_dag = MagicMock()
        mock_dag.dag_id = "oltp_data_pipeline"

        context = {
            "ti": mock_ti,
            "dag": mock_dag,
            "execution_date": "2025-01-01T00:00:00",
            "exception": ValueError("Database connection lost"),
        }

        payload = build_alert_payload("task_failure", context)
        self.assertEqual(payload["event_type"], "task_failure")
        self.assertEqual(payload["dag_id"], "oltp_data_pipeline")
        self.assertEqual(payload["task_id"], "extract_orders")
        self.assertEqual(payload["try_number"], 2)
        self.assertEqual(payload["environment"], ALERT_ENVIRONMENT)
        self.assertIn("Database connection lost", payload["error_message"])
        self.assertIn("oltp_data_pipeline.extract_orders", payload["title"])

    def test_send_webhook_notification_empty_url(self) -> None:
        """Verify webhook dispatcher skips gracefully when no webhook URL is configured."""
        payload = {"event_type": "test", "dag_id": "test", "task_id": "test"}
        with patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "", "ALERT_WEBHOOK_URL": ""}):
            result = send_webhook_notification(payload, webhook_url="")
            self.assertFalse(result)

    @patch("urllib.request.urlopen")
    def test_send_webhook_notification_success(self, mock_urlopen: MagicMock) -> None:
        """Verify webhook dispatcher delivers JSON payload to remote endpoint."""
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response

        payload = {"event_type": "task_failure", "dag_id": "oltp", "task_id": "extract"}
        success = send_webhook_notification(
            payload, webhook_url="https://hooks.slack.com/services/test"
        )

        self.assertTrue(success)
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        self.assertEqual(req.get_full_url(), "https://hooks.slack.com/services/test")
        self.assertEqual(req.headers.get("Content-type"), "application/json")

    @patch("urllib.request.urlopen")
    def test_send_webhook_notification_network_failure(
        self, mock_urlopen: MagicMock
    ) -> None:
        """Verify webhook dispatcher catches network URLError and logs error without crashing."""
        mock_urlopen.side_effect = urllib.error.URLError("DNS resolution failed")

        payload = {"event_type": "task_failure", "dag_id": "oltp", "task_id": "extract"}
        success = send_webhook_notification(
            payload, webhook_url="https://hooks.slack.com/services/bad"
        )

        self.assertFalse(success)

    @patch("airflow.plugins.alerting.send_webhook_notification")
    def test_alerting_callbacks(self, mock_send: MagicMock) -> None:
        """Verify task_failure_alert, task_retry_alert, and task_success_alert invocations."""
        context = {
            "dag_id": "test_pipeline",
            "task_id": "test_step",
            "try_number": 1,
            "exception": RuntimeError("Boom!"),
        }

        # Failure alert
        fail_payload = task_failure_alert(context)
        self.assertEqual(fail_payload["event_type"], "task_failure")
        self.assertIn("Boom!", fail_payload["error_message"])

        # Retry alert
        retry_payload = task_retry_alert(context)
        self.assertEqual(retry_payload["event_type"], "task_retry")

        # Success alert
        success_payload = task_success_alert(context)
        self.assertEqual(success_payload["event_type"], "task_success")

        # SLA miss alert
        sla_payload = sla_miss_alert(
            "test_pipeline", "extract_orders", "load_bronze", [], []
        )
        self.assertEqual(sla_payload["event_type"], "sla_miss")
        self.assertEqual(sla_payload["dag_id"], "test_pipeline")

        self.assertEqual(mock_send.call_count, 4)


if __name__ == "__main__":
    unittest.main()
