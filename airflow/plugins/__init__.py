"""Airflow custom plugins module for Modern E-Commerce Data Lakehouse Platform."""

from __future__ import annotations

from airflow.plugins.alerting import (
    sla_miss_alert,
    task_failure_alert,
    task_retry_alert,
    task_success_alert,
)
from airflow.plugins.minio_hook import MinIOHook
from airflow.plugins.sftp_hook import SFTPHook

try:
    from airflow.plugins_manager import AirflowPlugin
except ImportError:  # pragma: no cover

    class AirflowPlugin:  # type: ignore[no-redef]
        """Fallback AirflowPlugin class when running in non-Airflow environments."""

        name = "lakehouse_platform_plugin"
        hooks: list = []


class LakehousePlatformPlugin(AirflowPlugin):
    """Custom Airflow Plugin registering MinIO and SFTP hooks."""

    name = "lakehouse_platform_plugin"
    hooks = [MinIOHook, SFTPHook]


__all__ = [
    "MinIOHook",
    "SFTPHook",
    "LakehousePlatformPlugin",
    "task_failure_alert",
    "task_retry_alert",
    "task_success_alert",
    "sla_miss_alert",
]
