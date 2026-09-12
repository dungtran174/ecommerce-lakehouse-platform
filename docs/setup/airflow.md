# Apache Airflow Workflow Orchestration & Operational Runbook

This document details the architectural configuration, DAG catalog, deployment instructions, and operational procedures for **Apache Airflow 2.7.3** within the **Modern E-Commerce Data Lakehouse Platform**.

Airflow serves as the primary data orchestration engine, scheduling automated ingestions from transactional MySQL databases and remote SFTP log servers, loading partitioned raw data into the **MinIO Bronze tier**, and triggering downstream **dbt-spark** Medallion transformations and data quality test suites on **Apache Spark 3.3 Thrift Server**.

---

## 1. Architecture & Component Topography

```
                                  +------------------------------------+
                                  |   Airflow Webserver (Port 8080)    |
                                  |   airflow.lakehouse.local          |
                                  +-----------------+------------------+
                                                    |
                      +-----------------------------+-----------------------------+
                      |                                                           |
                      v                                                           v
       +-------------------------------+                           +-------------------------------+
       | Airflow PostgreSQL Metadata   | <=======================> | Airflow Scheduler             |
       | Database (Port 5432)          |     LocalExecutor Jobs    | (Job evaluation & dispatch)   |
       +-------------------------------+                           +---------------+---------------+
                                                                                   |
                         +---------------------------------------------------------+
                         | Dispatches Ingestion & Transformation Tasks
                         v
+--------------------------------------------------------------------------------------------------+
| Task Pipelines & Execution Engines                                                               |
|                                                                                                  |
| 1. OLTP MySQL Ingestion        ---> SqlToS3Operator  ---> MinIO Bronze (s3a://lakehouse/bronze)  |
| 2. Clickstream SFTP Ingestion  ---> SFTPHook + MinIO ---> MinIO Bronze (partitioned NDJSON)      |
| 3. Medallion Transformations   ---> BashOperator     ---> dbt compile/run/test on Spark Thrift   |
| 4. Incident Notifications      ---> Alerting Plugin  ---> Slack / Teams / Webhook Callbacks      |
+--------------------------------------------------------------------------------------------------+
```

### Component Directory

| Service / Workload | Container Name | K8s Deployment | Port | Purpose |
| :--- | :--- | :--- | :---: | :--- |
| **Airflow Webserver** | `lakehouse-airflow-webserver` | `airflow-webserver` | `8080` | DAG monitoring UI, manual triggers, connection management |
| **Airflow Scheduler** | `lakehouse-airflow-scheduler` | `airflow-scheduler` | — | DAG evaluation, task scheduling via `LocalExecutor` |
| **Airflow Metadata DB** | `lakehouse-airflow-postgres` | `airflow-postgres` | `5432` | PostgreSQL 14 storing task instances, states, and XComs |
| **Airflow DB Init** | `lakehouse-airflow-init` | Job / InitContainer | — | Schema migrations (`airflow db init`) and admin user creation |

---

## 2. DAG Inventory & Pipeline Specifications

### 2.1 MySQL OLTP Batch Pipeline (`oltp_data_pipeline`)

- **DAG ID:** `oltp_data_pipeline`
- **Schedule:** `@daily` (`0 0 * * *`)
- **Tags:** `lakehouse`, `oltp`, `mysql`, `bronze`, `ingestion`
- **Catchup:** `False`
- **Execution Flow:**
  1. `start_pipeline` (`EmptyOperator`): Pipeline initialization.
  2. Parallel extraction of master & dimension tables:
     - `extract_brands_to_bronze` (`SqlToS3Operator` -> `bronze/mysql/brands_snapshot/`)
     - `extract_categories_to_bronze` (`SqlToS3Operator` -> `bronze/mysql/category_snapshot/`)
     - `extract_payment_methods_to_bronze` (`SqlToS3Operator` -> `bronze/mysql/payment_method_snapshot/`)
     - `extract_customers_to_bronze` (`SqlToS3Operator` -> `bronze/mysql/customers_snapshot/`)
     - `extract_products_to_bronze` (`SqlToS3Operator` -> `bronze/mysql/products_snapshot/`)
  3. `extract_orders_to_bronze` (`SqlToS3Operator` -> `bronze/mysql/orders_snapshot/`): Transaction headers.
  4. `extract_order_items_to_bronze` (`SqlToS3Operator` -> `bronze/mysql/order_items_snapshot/`): Line items.
  5. `dbt_compile` (`BashOperator`): Validates and compiles dbt Jinja SQL models.
  6. `dbt_run` (`BashOperator`): Executes Bronze -> Silver -> Gold models on Spark Thrift Server.
  7. `dbt_test` (`BashOperator`): Executes schema uniqueness, referential integrity, and business assertions.
  8. `end_pipeline` (`EmptyOperator`): Pipeline completion marker.

### 2.2 Web Clickstream Telemetry Pipeline (`user_activity_logs_pipeline`)

- **DAG ID:** `user_activity_logs_pipeline`
- **Schedule:** `@hourly` (`0 * * * *`)
- **Tags:** `lakehouse`, `clickstream`, `sftp`, `bronze`, `ingestion`
- **Catchup:** `False`
- **Execution Flow:**
  1. `start_pipeline` (`EmptyOperator`): Run initialization.
  2. `scan_sftp_logs` (`PythonOperator` with `SFTPHook`): Scans remote directory `/var/log/ecommerce/clickstream` for uningested `.json` event files.
  3. `transfer_clickstream_to_minio` (`PythonOperator` with `MinIOHook` & `SFTPHook`): Streams clickstream files directly into MinIO Bronze storage under `bronze/clickstream/ingest_date={{ ds }}/`.
  4. `verify_bronze_landing` (`PythonOperator`): Verifies file presence in MinIO bucket.
  5. `dbt_compile` (`BashOperator`): Compiles downstream clickstream models (`--select stg_clickstream_events+`).
  6. `dbt_run` (`BashOperator`): Materializes `silver_user_sessions`, `silver_session_actions`, and `ml_user_behavior_3d_agg_feature`.
  7. `dbt_test` (`BashOperator`): Asserts clickstream schema fidelity and foreign key constraints.
  8. `end_pipeline` (`EmptyOperator`): Marks run completion.

---

## 3. Connections & Credentials Management

Airflow connects to external sources and destinations via pre-configured connections:

### Required Connections Matrix

| Connection ID | Conn Type | Host | Port | Schema / Bucket | Extra / Notes |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `mysql_default` | `MySQL` | `mysql-oltp` | `3306` | `ecommerce` | MySQL user & password |
| `minio_default` | `Amazon Web Services` | `http://minio:9000` | `9000` | `lakehouse` | AWS Access/Secret keys, `endpoint_url` |
| `sftp_default` | `SSH / SFTP` | `sftp-server` | `22` | `/var/log/ecommerce` | Remote key / password credentials |

### Provisioning Connections via CLI

You can register connections directly inside the Airflow container:

```bash
# Register MySQL Connection
docker exec -it lakehouse-airflow-webserver airflow connections add 'mysql_default' \
    --conn-type 'mysql' \
    --conn-host 'mysql-oltp' \
    --conn-login 'root' \
    --conn-password 'rootpassword' \
    --conn-schema 'ecommerce' \
    --conn-port 3306

# Register MinIO S3 Connection
docker exec -it lakehouse-airflow-webserver airflow connections add 'minio_default' \
    --conn-type 'aws' \
    --conn-extra '{"endpoint_url": "http://minio:9000", "aws_access_key_id": "minioadmin", "aws_secret_access_key": "minioadmin"}'

# Register SFTP Connection
docker exec -it lakehouse-airflow-webserver airflow connections add 'sftp_default' \
    --conn-type 'sftp' \
    --conn-host 'sftp.lakehouse.local' \
    --conn-login 'telemetry' \
    --conn-password 'sftppassword' \
    --conn-port 22
```

---

## 4. Deployment Instructions

### 4.1 Local Deployment via Docker Compose

1. Start metadata database and execute Airflow migration:
   ```bash
   docker compose -f docker/docker-compose.yml up -d airflow-postgres
   docker compose -f docker/docker-compose.yml up airflow-init
   ```

2. Start Webserver and Scheduler:
   ```bash
   docker compose -f docker/docker-compose.yml up -d airflow-webserver airflow-scheduler
   ```

3. Access Airflow UI:
   - URL: `http://localhost:8080` (or `http://airflow.lakehouse.local:8080`)
   - Username: `admin`
   - Password: `admin` (or configured via `_AIRFLOW_WWW_USER_PASSWORD`)

### 4.2 Kubernetes Deployment

Apply base Airflow manifests using Kustomize:

```bash
kubectl apply -k k8s/base/
```

Verify pod health:
```bash
kubectl get pods -n lakehouse -l app=airflow
kubectl get svc -n lakehouse -l app=airflow
kubectl get ingress -n lakehouse -l app=airflow
```

---

## 5. Alerting & Incident Notification Plugin

The platform provides an integrated alerting plugin (`airflow/plugins/alerting.py`) supporting automatic notifications for task failures, task retries, and SLA breaches.

### Configuration
Set the webhook URL in your environment:
```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T00/B00/XXXX"
export ALERT_WEBHOOK_URL="https://webhook.site/your-custom-endpoint"
export ENVIRONMENT="production" # or staging / development
```

### Supported Callbacks

- `task_failure_alert(context)`: Dispatches structured incident card containing DAG ID, task ID, try count, error trace, and direct Airflow log link.
- `task_retry_alert(context)`: Dispatches warning when a task fails transiently and initiates an automatic retry.
- `task_success_alert(context)`: Dispatches success notification for mission-critical milestone tasks.
- `sla_miss_alert(dag, task_list, ...)`: Alerts operations when execution duration exceeds defined SLA windows.

---

## 6. Operational Procedures & Runbook

### 6.1 Triggering Pipelines Manually

```bash
# Trigger MySQL OLTP Ingestion & Transformation
docker exec -it lakehouse-airflow-webserver airflow dags trigger oltp_data_pipeline

# Trigger Hourly Clickstream Telemetry Ingestion
docker exec -it lakehouse-airflow-webserver airflow dags trigger user_activity_logs_pipeline
```

### 6.2 Clearing & Retrying Failed Tasks

If a transient network glitch occurs during extraction or dbt execution:

```bash
# Clear failed tasks in a DAG run to allow automatic restart
docker exec -it lakehouse-airflow-webserver airflow tasks clear oltp_data_pipeline \
    --start-date 2025-01-01 \
    --end-date 2025-01-01 \
    --failed-only
```

### 6.3 Checking Logs & Diagnostics

```bash
# Follow scheduler logs
docker logs -f lakehouse-airflow-scheduler

# Follow webserver logs
docker logs -f lakehouse-airflow-webserver

# Inspect task logs on disk
ls -la airflow/logs/dag_id=oltp_data_pipeline/
```

### 6.4 Verifying DAG Integrity Locally

To test that all DAGs compile without circular dependencies before pushing to production:

```bash
python3 -m unittest tests/test_airflow_dags.py
```
