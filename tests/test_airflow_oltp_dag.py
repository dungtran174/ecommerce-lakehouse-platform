"""Unit tests for MySQL OLTP ingestion Airflow DAG (oltp_data_pipeline)."""

from __future__ import annotations

import os
import py_compile
import unittest

from airflow.dags.oltp_data_pipeline import TABLE_CONFIGS, dag


class TestAirflowOltpDag(unittest.TestCase):
    """Test suite validating the structure, tasks, and configuration of oltp_data_pipeline DAG."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate DAG file."""
        cls.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.dag_file = os.path.join(
            cls.root_dir, "airflow", "dags", "oltp_data_pipeline.py"
        )

    def test_dag_file_exists_and_compiles(self) -> None:
        """Verify DAG file exists on disk and has valid Python syntax."""
        self.assertTrue(os.path.exists(self.dag_file), "DAG file must exist")
        # Ensure file compiles cleanly without syntax errors
        compiled = py_compile.compile(self.dag_file, doraise=True)
        self.assertTrue(os.path.exists(compiled))

    def test_dag_metadata_and_properties(self) -> None:
        """Verify DAG identifier, schedule, tags, and execution constraints."""
        self.assertEqual(dag.dag_id, "oltp_data_pipeline")
        self.assertEqual(dag.schedule_interval, "@daily")
        self.assertFalse(dag.catchup)
        self.assertIn("lakehouse", dag.tags)
        self.assertIn("oltp", dag.tags)
        self.assertIn("bronze", dag.tags)

    def test_dag_declares_all_seven_tables(self) -> None:
        """Verify all 7 MySQL tables are declared in TABLE_CONFIGS with correct keys and queries."""
        expected_tables = {
            "brands": "bronze/mysql/brands_snapshot/brands_snapshot.csv",
            "categories": "bronze/mysql/category_snapshot/category_snapshot.csv",
            "payment_methods": "bronze/mysql/payment_method_snapshot/payment_method_snapshot.csv",
            "customers": "bronze/mysql/customers_snapshot/customers_snapshot.csv",
            "products": "bronze/mysql/products_snapshot/products_snapshot.csv",
            "orders": "bronze/mysql/orders_snapshot/orders_snapshot.csv",
            "order_items": "bronze/mysql/order_items_snapshot/order_items_snapshot.csv",
        }

        configured_names = {cfg["name"]: cfg["s3_key"] for cfg in TABLE_CONFIGS}
        self.assertEqual(configured_names, expected_tables)

        for cfg in TABLE_CONFIGS:
            self.assertTrue(cfg["query"].startswith("SELECT "))
            self.assertTrue(cfg["s3_key"].startswith("bronze/mysql/"))
            self.assertTrue(cfg["task_id"].startswith("extract_"))

    def test_task_pipeline_dependencies(self) -> None:
        """Verify upstream/downstream task flow relationships."""
        # Find tasks in DAG
        tasks_by_id = {}
        if hasattr(dag, "task_dict") and dag.task_dict:
            tasks_by_id = dag.task_dict
        elif hasattr(dag, "tasks") and dag.tasks:
            tasks_by_id = {t.task_id: t for t in dag.tasks}
        else:
            # Fallback for custom DAG mock
            import airflow.dags.oltp_data_pipeline as module

            for attr_name in dir(module):
                val = getattr(module, attr_name)
                if hasattr(val, "task_id"):
                    tasks_by_id[val.task_id] = val

        # Ensure start and end tasks exist
        self.assertIn("start_pipeline", tasks_by_id)
        self.assertIn("end_pipeline", tasks_by_id)

        # Ensure all 7 extract tasks exist
        for cfg in TABLE_CONFIGS:
            self.assertIn(cfg["task_id"], tasks_by_id)

        # Check dependency ordering
        start_task = tasks_by_id["start_pipeline"]
        orders_task = tasks_by_id["extract_orders_to_bronze"]
        items_task = tasks_by_id["extract_order_items_to_bronze"]
        end_task = tasks_by_id["end_pipeline"]

        # start_pipeline must be upstream of master tables
        downstream_start = [t.task_id for t in start_task.downstream_list]
        self.assertIn("extract_brands_to_bronze", downstream_start)

        # orders must be upstream of order_items
        downstream_orders = [t.task_id for t in orders_task.downstream_list]
        self.assertIn("extract_order_items_to_bronze", downstream_orders)

        # order_items must be upstream of end_pipeline
        downstream_items = [t.task_id for t in items_task.downstream_list]
        self.assertIn("end_pipeline", downstream_items)

        upstream_end = [t.task_id for t in end_task.upstream_list]
        self.assertIn("extract_order_items_to_bronze", upstream_end)


if __name__ == "__main__":
    unittest.main()
