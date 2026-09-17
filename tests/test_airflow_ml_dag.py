"""Unit tests for ML batch inference & marketing campaign Airflow DAG (marketing_campaign_pipeline)."""

from __future__ import annotations

import os
import py_compile
import unittest
from typing import Any

from airflow.dags.marketing_campaign_pipeline import (
    DBT_PROFILES_DIR,
    DBT_PROJECT_DIR,
    DEFAULT_ARGS,
    ML_SCRIPTS_DIR,
    dag,
)


class TestAirflowMLDag(unittest.TestCase):
    """Test suite validating marketing_campaign_pipeline DAG configuration and task graph."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate DAG file on disk."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.dag_file = os.path.join(
            cls.root_dir, "airflow", "dags", "marketing_campaign_pipeline.py"
        )

    def test_dag_file_exists_and_compiles(self) -> None:
        """Verify DAG file exists on disk and has valid Python syntax without errors."""
        self.assertTrue(os.path.exists(self.dag_file), "DAG file must exist")
        compiled = py_compile.compile(self.dag_file, doraise=True)
        self.assertTrue(os.path.exists(compiled))

    def test_dag_metadata_and_properties(self) -> None:
        """Verify DAG identifier, schedule, tags, and execution constraints."""
        self.assertEqual(dag.dag_id, "marketing_campaign_pipeline")
        self.assertEqual(dag.schedule_interval, "0 6 * * *")
        self.assertFalse(dag.catchup)
        self.assertEqual(dag.max_active_runs, 1)

        expected_tags = ["lakehouse", "ml", "marketing", "campaign", "gold"]
        for tag in expected_tags:
            self.assertIn(tag, dag.tags)

    def test_default_args(self) -> None:
        """Verify DAG default_args for retries, owner, and email settings."""
        self.assertEqual(DEFAULT_ARGS["owner"], "marketing_ops")
        self.assertEqual(DEFAULT_ARGS["retries"], 2)
        self.assertFalse(DEFAULT_ARGS["email_on_failure"])
        self.assertFalse(DEFAULT_ARGS["email_on_retry"])
        self.assertFalse(DEFAULT_ARGS["depends_on_past"])

    def test_environment_and_paths(self) -> None:
        """Verify environment paths for dbt and ML scripts are configured."""
        self.assertTrue(bool(DBT_PROJECT_DIR))
        self.assertTrue(bool(DBT_PROFILES_DIR))
        self.assertTrue(bool(ML_SCRIPTS_DIR))

    def _get_task_dict(self) -> dict[str, Any]:
        """Retrieve dictionary of tasks by task_id across native or fallback environments."""
        if hasattr(dag, "task_dict") and dag.task_dict:
            return dag.task_dict
        if hasattr(dag, "tasks") and dag.tasks:
            return {t.task_id: t for t in dag.tasks}
        import airflow.dags.marketing_campaign_pipeline as module

        tasks = {}
        for attr_name in dir(module):
            val = getattr(module, attr_name)
            if hasattr(val, "task_id"):
                tasks[val.task_id] = val
        return tasks

    def test_dag_tasks_declared(self) -> None:
        """Verify all essential marketing pipeline tasks exist in the DAG."""
        task_dict = self._get_task_dict()
        expected_tasks = {
            "start",
            "wait_for_gold_ml_features",
            "spark_ml_batch_inference",
            "dbt_compile_marketing",
            "dbt_run_marketing",
            "dbt_test_marketing",
            "generate_campaign_summary",
            "end",
        }
        for task_id in expected_tasks:
            self.assertIn(task_id, task_dict)

    def test_task_command_arguments(self) -> None:
        """Verify task commands target proper models, directories, and tables."""
        task_dict = self._get_task_dict()

        # Inference task verification
        inference_task = task_dict.get("spark_ml_batch_inference")
        self.assertIsNotNone(inference_task)
        self.assertIn("inference.py", getattr(inference_task, "bash_command", ""))
        self.assertIn(
            "lakehouse.gold_ml.ml_user_behavior_3d_agg_feature",
            getattr(inference_task, "bash_command", ""),
        )
        self.assertIn(
            "lakehouse.marketing.high_value_purchase_campaign",
            getattr(inference_task, "bash_command", ""),
        )

        # dbt tasks verification
        dbt_compile = task_dict.get("dbt_compile_marketing")
        self.assertIn("models/gold/marketing", getattr(dbt_compile, "bash_command", ""))

        dbt_run = task_dict.get("dbt_run_marketing")
        self.assertIn("models/gold/marketing", getattr(dbt_run, "bash_command", ""))

        dbt_test = task_dict.get("dbt_test_marketing")
        self.assertIn("models/gold/marketing", getattr(dbt_test, "bash_command", ""))

    def test_linear_task_dependencies(self) -> None:
        """Verify DAG task graph has linear dependencies without cycles."""
        task_dict = self._get_task_dict()

        start = task_dict["start"]
        wait_features = task_dict["wait_for_gold_ml_features"]
        inference = task_dict["spark_ml_batch_inference"]
        dbt_comp = task_dict["dbt_compile_marketing"]
        dbt_run = task_dict["dbt_run_marketing"]
        dbt_test = task_dict["dbt_test_marketing"]
        summary = task_dict["generate_campaign_summary"]
        end = task_dict["end"]

        # Check upstream / downstream links
        self.assertIn(wait_features, start.downstream_list)
        self.assertIn(inference, wait_features.downstream_list)
        self.assertIn(dbt_comp, inference.downstream_list)
        self.assertIn(dbt_run, dbt_comp.downstream_list)
        self.assertIn(dbt_test, dbt_run.downstream_list)
        self.assertIn(summary, dbt_test.downstream_list)
        self.assertIn(end, summary.downstream_list)


if __name__ == "__main__":
    unittest.main()
