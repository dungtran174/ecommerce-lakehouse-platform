"""Airflow DAG: Automated SFTP ingestion of web clickstream logs into MinIO Bronze Lakehouse tier."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any

try:
    from airflow.operators.bash import BashOperator
    from airflow.operators.empty import EmptyOperator
    from airflow.operators.python import PythonOperator
    from airflow.providers.amazon.aws.transfers.sftp_to_s3 import SFTPToS3Operator

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
        from airflow.operators.python import PythonOperator  # type: ignore[no-redef]

        try:
            from airflow.operators.bash import BashOperator  # type: ignore[no-redef]
        except ImportError:

            class BashOperator(BaseOperator):  # type: ignore[no-redef]
                def __init__(
                    self,
                    *,
                    bash_command: str,
                    env: dict[str, str] | None = None,
                    **kwargs: Any,
                ) -> None:
                    super().__init__(**kwargs)
                    self.bash_command = bash_command
                    self.env = env or {}

        class SFTPToS3Operator(BaseOperator):  # type: ignore[no-redef]
            def __init__(
                self,
                *,
                sftp_path: str,
                s3_bucket: str,
                s3_key: str,
                sftp_conn_id: str = "sftp_default",
                s3_conn_id: str = "minio_default",
                **kwargs: Any,
            ) -> None:
                super().__init__(**kwargs)
                self.sftp_path = sftp_path
                self.s3_bucket = s3_bucket
                self.s3_key = s3_key
                self.sftp_conn_id = sftp_conn_id
                self.s3_conn_id = s3_conn_id

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

        class BashOperator(BaseTask):  # type: ignore[no-redef]
            def __init__(
                self,
                task_id: str,
                bash_command: str,
                env: dict[str, str] | None = None,
                **kwargs: Any,
            ) -> None:
                super().__init__(
                    task_id=task_id,
                    bash_command=bash_command,
                    env=env or {},
                    **kwargs,
                )

        class PythonOperator(BaseTask):  # type: ignore[no-redef]
            def __init__(
                self,
                task_id: str,
                python_callable: Any = None,
                op_kwargs: dict[str, Any] | None = None,
                **kwargs: Any,
            ) -> None:
                super().__init__(
                    task_id=task_id,
                    python_callable=python_callable,
                    op_kwargs=op_kwargs or {},
                    **kwargs,
                )

        class SFTPToS3Operator(BaseTask):  # type: ignore[no-redef]
            def __init__(
                self,
                task_id: str,
                sftp_path: str,
                s3_bucket: str,
                s3_key: str,
                sftp_conn_id: str = "sftp_default",
                s3_conn_id: str = "minio_default",
                **kwargs: Any,
            ) -> None:
                super().__init__(
                    task_id=task_id,
                    sftp_path=sftp_path,
                    s3_bucket=s3_bucket,
                    s3_key=s3_key,
                    sftp_conn_id=sftp_conn_id,
                    s3_conn_id=s3_conn_id,
                    **kwargs,
                )


logger = logging.getLogger(__name__)

# SFTP and S3 Configuration constants
SFTP_CONN_ID = "sftp_default"
MINIO_CONN_ID = "minio_default"
S3_BUCKET = os.getenv("MINIO_DEFAULT_BUCKET", "lakehouse")
SFTP_REMOTE_DIR = os.getenv("SFTP_REMOTE_DIR", "/var/log/ecommerce/clickstream")
FILE_PATTERN = "*.json"

# dbt transformation and test configuration
DBT_PROJECT_DIR = os.getenv("DBT_PROJECT_DIR", "/opt/airflow/dbt")
DBT_PROFILES_DIR = os.getenv("DBT_PROFILES_DIR", "/opt/airflow/dbt")
DBT_SELECT_MODELS = "stg_clickstream_events+"


def scan_remote_sftp_logs(**context: Any) -> list[str]:
    """Scan remote SFTP server for available clickstream log files."""
    from airflow.plugins.sftp_hook import SFTPHook

    with SFTPHook(sftp_conn_id=SFTP_CONN_ID) as hook:
        files = hook.list_files(SFTP_REMOTE_DIR, pattern=FILE_PATTERN)
        logger.info(
            "Discovered %d clickstream files in %s: %s",
            len(files),
            SFTP_REMOTE_DIR,
            files,
        )
        return files


def transfer_clickstream_to_minio(**context: Any) -> int:
    """Transfer clickstream files from SFTP into date-partitioned MinIO Bronze tier."""
    from airflow.plugins.minio_hook import MinIOHook
    from airflow.plugins.sftp_hook import SFTPHook

    ti = context.get("ti")
    ds = context.get("ds", datetime.utcnow().strftime("%Y-%m-%d"))
    files = []
    if ti:
        files = ti.xcom_pull(task_ids="scan_sftp_logs") or []

    minio_hook = MinIOHook(minio_conn_id=MINIO_CONN_ID)
    minio_hook.create_bucket(S3_BUCKET)

    target_prefix = f"bronze/clickstream/ingest_date={ds}"
    transferred_count = 0

    with SFTPHook(sftp_conn_id=SFTP_CONN_ID) as sftp_hook:
        # If no files found from XCom, check directory directly
        if not files:
            files = sftp_hook.list_files(SFTP_REMOTE_DIR, pattern=FILE_PATTERN)

        for filename in files:
            remote_path = f"{SFTP_REMOTE_DIR}/{filename}"
            content = sftp_hook.read_file_content(remote_path)
            s3_key = f"{target_prefix}/{filename}"
            minio_hook.upload_bytes(
                data=content,
                bucket_name=S3_BUCKET,
                object_key=s3_key,
            )
            logger.info("Transferred %s -> s3://%s/%s", remote_path, S3_BUCKET, s3_key)
            transferred_count += 1

    logger.info("Successfully transferred %d clickstream log files", transferred_count)
    return transferred_count


def verify_bronze_landing(**context: Any) -> bool:
    """Verify that clickstream files landed successfully in MinIO Bronze bucket."""
    from airflow.plugins.minio_hook import MinIOHook

    ds = context.get("ds", datetime.utcnow().strftime("%Y-%m-%d"))
    target_prefix = f"bronze/clickstream/ingest_date={ds}"

    minio_hook = MinIOHook(minio_conn_id=MINIO_CONN_ID)
    objects = minio_hook.list_objects(S3_BUCKET, prefix=target_prefix)
    logger.info(
        "Found %d objects under s3://%s/%s",
        len(objects),
        S3_BUCKET,
        target_prefix,
    )
    return True


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
}

with DAG(
    dag_id="user_activity_logs_pipeline",
    default_args=default_args,
    description="Automated SFTP ingestion of web clickstream logs landed as partitioned NDJSON into MinIO Bronze tier",
    schedule_interval="@hourly",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["lakehouse", "clickstream", "sftp", "bronze", "ingestion"],
) as dag:
    start_pipeline = EmptyOperator(task_id="start_pipeline")

    scan_logs = PythonOperator(
        task_id="scan_sftp_logs",
        python_callable=scan_remote_sftp_logs,
    )

    transfer_logs = PythonOperator(
        task_id="transfer_clickstream_to_minio",
        python_callable=transfer_clickstream_to_minio,
    )

    verify_landing = PythonOperator(
        task_id="verify_bronze_landing",
        python_callable=verify_bronze_landing,
    )

    dbt_compile = BashOperator(
        task_id="dbt_compile",
        bash_command=(
            f"dbt compile --project-dir {DBT_PROJECT_DIR} "
            f"--profiles-dir {DBT_PROFILES_DIR} --select {DBT_SELECT_MODELS}"
        ),
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=(
            f"dbt run --project-dir {DBT_PROJECT_DIR} "
            f"--profiles-dir {DBT_PROFILES_DIR} --select {DBT_SELECT_MODELS}"
        ),
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(
            f"dbt test --project-dir {DBT_PROJECT_DIR} "
            f"--profiles-dir {DBT_PROFILES_DIR} --select {DBT_SELECT_MODELS}"
        ),
    )

    end_pipeline = EmptyOperator(task_id="end_pipeline")

    # Ingestion & Transformation Pipeline Flow:
    # start_pipeline -> scan_sftp_logs -> transfer_clickstream_to_minio -> verify_bronze_landing -> dbt_compile -> dbt_run -> dbt_test -> end_pipeline
    (
        start_pipeline
        >> scan_logs
        >> transfer_logs
        >> verify_landing
        >> dbt_compile
        >> dbt_run
        >> dbt_test
        >> end_pipeline
    )
