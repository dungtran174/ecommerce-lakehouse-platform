"""Airflow Alerting Callbacks & Incident Notification Plugin.

Provides automated alert dispatchers (Slack, Teams, Discord, generic Webhooks)
for task failure, task retry, and SLA miss events across Lakehouse DAGs.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

# Webhook configuration environment variables
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", ALERT_WEBHOOK_URL)
ALERT_ENVIRONMENT = os.getenv("ENVIRONMENT", "production")


def build_alert_payload(
    event_type: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Extract execution context and format a standardized incident payload."""
    ti = context.get("task_instance") or context.get("ti")
    dag = context.get("dag")
    execution_date = context.get("execution_date") or context.get("ts", "N/A")
    exception = context.get("exception")

    dag_id = getattr(dag, "dag_id", str(context.get("dag_id", "unknown_dag")))
    task_id = getattr(ti, "task_id", str(context.get("task_id", "unknown_task")))
    try_number = getattr(ti, "try_number", context.get("try_number", 1))
    log_url = getattr(ti, "log_url", context.get("log_url", "N/A"))

    error_message = str(exception) if exception else "No exception details provided"

    payload = {
        "event_type": event_type,
        "environment": ALERT_ENVIRONMENT,
        "dag_id": dag_id,
        "task_id": task_id,
        "try_number": try_number,
        "execution_date": str(execution_date),
        "log_url": log_url,
        "error_message": error_message,
        "title": f"[{ALERT_ENVIRONMENT.upper()}] Airflow {event_type.replace('_', ' ').title()}: {dag_id}.{task_id}",
    }
    return payload


def send_webhook_notification(
    payload: dict[str, Any],
    webhook_url: str | None = None,
) -> bool:
    """Send JSON-formatted incident alert payload to remote webhook URL."""
    target_url = webhook_url or SLACK_WEBHOOK_URL or ALERT_WEBHOOK_URL
    if not target_url:
        logger.warning(
            "Alert notification skipped: neither SLACK_WEBHOOK_URL nor ALERT_WEBHOOK_URL is configured."
        )
        return False

    headers = {"Content-Type": "application/json"}
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(target_url, data=body, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            status_code = response.getcode()
            logger.info(
                "Successfully dispatched %s alert for %s.%s (HTTP %d)",
                payload.get("event_type"),
                payload.get("dag_id"),
                payload.get("task_id"),
                status_code,
            )
            return status_code in (200, 201, 204)
    except urllib.error.URLError as err:
        logger.error("Failed to deliver alert notification to webhook: %s", err)
        return False
    except Exception as exc:  # pragma: no cover
        logger.error("Unexpected error delivering alert notification: %s", exc)
        return False


def task_failure_alert(context: dict[str, Any]) -> dict[str, Any]:
    """Callback function triggered when an Airflow task execution fails permanently."""
    payload = build_alert_payload("task_failure", context)
    logger.error(
        "CRITICAL: Task failure detected in DAG '%s', Task '%s', Error: %s",
        payload["dag_id"],
        payload["task_id"],
        payload["error_message"],
    )
    send_webhook_notification(payload)
    return payload


def task_retry_alert(context: dict[str, Any]) -> dict[str, Any]:
    """Callback function triggered when an Airflow task fails and attempts an automatic retry."""
    payload = build_alert_payload("task_retry", context)
    logger.warning(
        "WARNING: Task retry triggered for DAG '%s', Task '%s', Attempt: %s",
        payload["dag_id"],
        payload["task_id"],
        payload["try_number"],
    )
    send_webhook_notification(payload)
    return payload


def task_success_alert(context: dict[str, Any]) -> dict[str, Any]:
    """Callback function triggered upon successful completion of critical tasks."""
    payload = build_alert_payload("task_success", context)
    logger.info(
        "SUCCESS: Task succeeded in DAG '%s', Task '%s'",
        payload["dag_id"],
        payload["task_id"],
    )
    send_webhook_notification(payload)
    return payload


def sla_miss_alert(
    dag: Any,
    task_list: str,
    blocking_task_list: str,
    slas: list[Any],
    blocking_tis: list[Any],
) -> dict[str, Any]:
    """Callback function triggered when DAG execution breaches configured SLA threshold."""
    dag_id = getattr(dag, "dag_id", str(dag))
    payload = {
        "event_type": "sla_miss",
        "environment": ALERT_ENVIRONMENT,
        "dag_id": dag_id,
        "task_list": str(task_list),
        "blocking_task_list": str(blocking_task_list),
        "title": f"[{ALERT_ENVIRONMENT.upper()}] Airflow SLA Miss: {dag_id}",
        "error_message": f"SLA breached for tasks: {task_list}. Blocking tasks: {blocking_task_list}",
    }
    logger.error(
        "SLA MISSED: DAG '%s' breached SLA timing. Tasks: %s, Blocking: %s",
        dag_id,
        task_list,
        blocking_task_list,
    )
    send_webhook_notification(payload)
    return payload
