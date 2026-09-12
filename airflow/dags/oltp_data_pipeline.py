"""Airflow DAG: Automated MySQL OLTP batch extraction into MinIO Bronze Lakehouse tier."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any

try:
    from airflow.operators.empty import EmptyOperator
    from airflow.providers.amazon.aws.transfers.sql_to_s3 import SqlToS3Operator

    from airflow import DAG
except ImportError:  # pragma: no cover
    # Provide lightweight fallbacks for environments without airflow-providers-amazon
    try:
        from airflow import DAG  # type: ignore[no-redef]

        try:
            from airflow.operators.empty import EmptyOperator  # type: ignore[no-redef]
        except ImportError:
            from airflow.operators.dummy import DummyOperator as EmptyOperator  # type: ignore[no-redef]
        from airflow.models.baseoperator import BaseOperator

        class SqlToS3Operator(BaseOperator):  # type: ignore[no-redef]
            def __init__(
                self,
                *,
                query: str,
                s3_bucket: str,
                s3_key: str,
                sql_conn_id: str = "mysql_default",
                aws_conn_id: str = "minio_default",
                replace: bool = True,
                file_format: str = "csv",
                pd_kwargs: dict[str, Any] | None = None,
                **kwargs: Any,
            ) -> None:
                super().__init__(**kwargs)
                self.query = query
                self.s3_bucket = s3_bucket
                self.s3_key = s3_key
                self.sql_conn_id = sql_conn_id
                self.aws_conn_id = aws_conn_id
                self.replace = replace
                self.file_format = file_format
                self.pd_kwargs = pd_kwargs or {}

    except ImportError:
        # Standalone mock fallback for isolated unit testing
        class DAG:  # type: ignore[no-redef]
            _current_dag: DAG | None = None

            def __init__(self, dag_id: str, **kwargs: Any) -> None:
                self.dag_id = dag_id
                self.default_args = kwargs.get("default_args", {})
                self.schedule_interval = kwargs.get("schedule_interval")
                self.start_date = kwargs.get("start_date")
                self.catchup = kwargs.get("catchup", False)
                self.tags = kwargs.get("tags", [])
                self.task_dict: dict[str, Any] = {}

            def __enter__(self) -> DAG:
                DAG._current_dag = self
                return self

            def __exit__(self, *args: Any) -> None:
                DAG._current_dag = None

        class BaseTask:
            def __init__(self, task_id: str, **kwargs: Any) -> None:
                self.task_id = task_id
                self.upstream_list: list[BaseTask] = []
                self.downstream_list: list[BaseTask] = []
                for k, v in kwargs.items():
                    setattr(self, k, v)
                if DAG._current_dag is not None:
                    DAG._current_dag.task_dict[task_id] = self

            def __rshift__(self, other: Any) -> Any:
                if isinstance(other, list):
                    for o in other:
                        self.downstream_list.append(o)
                        o.upstream_list.append(self)
                else:
                    self.downstream_list.append(other)
                    other.upstream_list.append(self)
                return other

            def __rrshift__(self, other: Any) -> Any:
                if isinstance(other, list):
                    for o in other:
                        o.downstream_list.append(self)
                        self.upstream_list.append(o)
                return self

        class EmptyOperator(BaseTask):  # type: ignore[no-redef]
            pass

        class SqlToS3Operator(BaseTask):  # type: ignore[no-redef]
            def __init__(
                self,
                task_id: str,
                query: str,
                s3_bucket: str,
                s3_key: str,
                sql_conn_id: str = "mysql_default",
                aws_conn_id: str = "minio_default",
                replace: bool = True,
                file_format: str = "csv",
                pd_kwargs: dict[str, Any] | None = None,
                **kwargs: Any,
            ) -> None:
                super().__init__(
                    task_id=task_id,
                    query=query,
                    s3_bucket=s3_bucket,
                    s3_key=s3_key,
                    sql_conn_id=sql_conn_id,
                    aws_conn_id=aws_conn_id,
                    replace=replace,
                    file_format=file_format,
                    pd_kwargs=pd_kwargs or {},
                    **kwargs,
                )


# S3 Destination and Connection configurations
S3_BUCKET = os.getenv("MINIO_DEFAULT_BUCKET", "lakehouse")
SQL_CONN_ID = "mysql_default"
AWS_CONN_ID = "minio_default"

# Table extraction specifications (source_table, target_key, query)
TABLE_CONFIGS = [
    {
        "name": "brands",
        "task_id": "extract_brands_to_bronze",
        "s3_key": "bronze/mysql/brands_snapshot/brands_snapshot.csv",
        "query": "SELECT brand_id, brand_name, brand_origin FROM brands;",
    },
    {
        "name": "categories",
        "task_id": "extract_categories_to_bronze",
        "s3_key": "bronze/mysql/category_snapshot/category_snapshot.csv",
        "query": "SELECT category_id, category_display_name, category_description FROM categories;",
    },
    {
        "name": "payment_methods",
        "task_id": "extract_payment_methods_to_bronze",
        "s3_key": "bronze/mysql/payment_method_snapshot/payment_method_snapshot.csv",
        "query": "SELECT payment_method_id, display_name, type, provider FROM payment_method;",
    },
    {
        "name": "customers",
        "task_id": "extract_customers_to_bronze",
        "s3_key": "bronze/mysql/customers_snapshot/customers_snapshot.csv",
        "query": (
            "SELECT customer_id, first_name, last_name, email, phone_number, "
            "gender, tire, address, created_at, updated_at FROM customers;"
        ),
    },
    {
        "name": "products",
        "task_id": "extract_products_to_bronze",
        "s3_key": "bronze/mysql/products_snapshot/products_snapshot.csv",
        "query": (
            "SELECT product_id, product_name, product_description, price, "
            "category_id, brand_id, created_at, updated_at FROM products;"
        ),
    },
    {
        "name": "orders",
        "task_id": "extract_orders_to_bronze",
        "s3_key": "bronze/mysql/orders_snapshot/orders_snapshot.csv",
        "query": (
            "SELECT order_id, customer_id, order_date, total_amount, "
            "payment_method_id, created_at, updated_at FROM orders;"
        ),
    },
    {
        "name": "order_items",
        "task_id": "extract_order_items_to_bronze",
        "s3_key": "bronze/mysql/order_items_snapshot/order_items_snapshot.csv",
        "query": "SELECT order_item_id, order_id, product_id, quantity, price, discount FROM order_items;",
    },
]

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
}

with DAG(
    dag_id="oltp_data_pipeline",
    default_args=default_args,
    description="Automated batch extraction of MySQL OLTP tables landed as CSV into MinIO Bronze tier",
    schedule_interval="@daily",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["lakehouse", "oltp", "mysql", "bronze", "ingestion"],
) as dag:
    start_pipeline = EmptyOperator(task_id="start_pipeline")
    end_pipeline = EmptyOperator(task_id="end_pipeline")

    extraction_tasks: dict[str, Any] = {}
    for cfg in TABLE_CONFIGS:
        task = SqlToS3Operator(
            task_id=cfg["task_id"],
            query=cfg["query"],
            s3_bucket=S3_BUCKET,
            s3_key=cfg["s3_key"],
            sql_conn_id=SQL_CONN_ID,
            aws_conn_id=AWS_CONN_ID,
            replace=True,
            file_format="csv",
            pd_kwargs={"index": False},
        )
        extraction_tasks[cfg["name"]] = task

    # Task dependency pipeline ordering:
    # 1. Start pipeline
    # 2. Extract dimensional & reference tables in parallel (brands, categories, payment_methods, customers, products)
    # 3. Extract transactional order headers
    # 4. Extract granular order line items
    # 5. End pipeline
    master_tasks = [
        extraction_tasks["brands"],
        extraction_tasks["categories"],
        extraction_tasks["payment_methods"],
        extraction_tasks["customers"],
        extraction_tasks["products"],
    ]

    start_pipeline >> master_tasks
    master_tasks >> extraction_tasks["orders"]
    extraction_tasks["orders"] >> extraction_tasks["order_items"]
    extraction_tasks["order_items"] >> end_pipeline
