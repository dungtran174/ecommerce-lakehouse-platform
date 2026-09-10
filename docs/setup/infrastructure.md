# Storage & Compute Infrastructure Deployment Guide

This document provides a comprehensive operational guide for provisioning, configuring, and verifying the core storage and distributed compute layers of the **Modern E-Commerce Data Lakehouse Platform**.

The architecture decouples durable object storage from scalable analytical compute engines, orchestrating **MinIO (S3A)**, **Apache Hive Metastore 3.0**, and **Apache Spark 3.3 (Thrift Server & Delta Lake 2.2)** across both local Docker Compose and cloud-native Kubernetes environments.

---

## 1. Architecture Overview & Component Matrix

The storage and compute tier forms the foundational backbone of the Lakehouse platform:

```
                                  +-------------------------------------------------------+
                                  |                 Client Applications                   |
                                  |   (dbt-spark, Trino MPP, BI Dashboards, Airflow DAGs) |
                                  +---------------------------+---------------------------+
                                                              |
                                                    JDBC / Thrift (Port 10000)
                                                              v
+-----------------------------------------------------------------------------------------+
| Apache Spark 3.3.3 Distributed Compute Engine (Driver & Thrift Server)                   |
| - Extensions: Delta Lake 2.2.0 (io.delta.sql.DeltaSparkSessionExtension)                |
| - Catalog: DeltaCatalog (org.apache.spark.sql.delta.catalog.DeltaCatalog)               |
| - Web UI: http://localhost:4040 (spark.lakehouse.local)                                 |
+------------------------------+-------------------------------------------+--------------+
                               |                                           |
               Metadata RPC    |                               S3A Read    | S3A Write
               (Port 9083)     |                               (Port 9000) | (Port 9000)
                               v                                           v
+---------------------------------------------------------+   +---------------------------+
| Apache Hive Metastore 3.0 (HMS)                         |   | MinIO S3 Object Store     |
| - Backend: MySQL 8.0 (metastore-db:3306)                |   | - Multi-tier Buckets:     |
| - Warehouse Dir: s3a://lakehouse/warehouse              |   |   lakehouse (bronze,      |
|                                                         |   |   silver, gold)           |
+---------------------------------------------------------+   +---------------------------+
```

### Infrastructure Service Directory

| Service Component | Container / Workload | Internal Port | Exposed / Node Port | Protocol | Ingress / Hostname | Description |
| :--- | :--- | :---: | :---: | :---: | :--- | :--- |
| **MinIO S3 API** | `lakehouse-minio` | `9000` | `9000` | HTTP / S3A | `s3.minio.lakehouse.local` | Object storage API endpoint for Lakehouse tiers |
| **MinIO Console** | `lakehouse-minio` | `9001` | `9001` | HTTP | `console.minio.lakehouse.local` | Web administration dashboard for MinIO |
| **MySQL OLTP** | `lakehouse-mysql-oltp` | `3306` | `3307` | TCP / MySQL | `mysql.lakehouse.local` | Operational e-commerce source database |
| **Metastore DB** | `lakehouse-metastore-db` | `3306` | `3308` | TCP / MySQL | — | Hive Metastore catalog metadata store (MySQL 8.0) |
| **Hive Metastore** | `lakehouse-hive-metastore` | `9083` | `9083` | Thrift RPC | `metastore.lakehouse.local` | Centralized schema and catalog registry |
| **Spark Thrift Server** | `lakehouse-spark-thrift-server` | `10000` | `10000` | Hive2 / Thrift | `spark.lakehouse.local` | Distributed SQL query engine with Delta Lake |
| **Spark Web UI** | `lakehouse-spark-thrift-server` | `4040` | `4040` | HTTP | `spark.lakehouse.local`, `spark-ui.lakehouse.local` | Live driver execution monitor, stage timelines & SQL metrics |

---

## 2. Local Deployment via Docker Compose

### Prerequisites
- Docker Engine >= 24.0
- Docker Compose >= 2.20
- Minimum allocated resources: 4 vCPU, 8 GB RAM

### Step 1: Configure Environment Variables
Copy `.env.example` to `.env` in the repository root and adjust credentials if needed:
```bash
cp .env.example .env
```

Key environment properties affecting storage and compute:
```ini
# MinIO Object Storage
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin
MINIO_DEFAULT_BUCKET=lakehouse

# Hive Metastore Database
METASTORE_DB_DATABASE=metastore_db
METASTORE_DB_USER=hive
METASTORE_DB_PASSWORD=hivepassword

# Apache Spark Thrift Server
SPARK_DRIVER_MEMORY=2g
SPARK_EXECUTOR_MEMORY=2g
SPARK_THRIFT_PORT=10000
SPARK_UI_PORT=4040
```

### Step 2: Start Infrastructure Services
Start the core storage and compute cluster in detached mode:
```bash
make docker-up
```

Alternatively, invoke Docker Compose directly:
```bash
docker compose -f docker/docker-compose.yml up -d minio metastore-db hive-metastore spark-thrift-server
```

### Step 3: Initialize MinIO Bucket Hierarchy
Execute the automated bucket initialization script to create the Medallion directory structure:
```bash
make init-lakehouse
```
This script creates:
- `s3a://lakehouse/bronze/` (Raw immutable landing zone: MySQL CSV snapshots, clickstream NDJSON)
- `s3a://lakehouse/silver/` (Cleansed Delta Lake tables: conformed entities and partitioned session logs)
- `s3a://lakehouse/gold/` (Dimensional Kimball data marts: sale marts and ML feature stores)
- `s3a://lakehouse/checkpoints/` (Streaming and delta transaction checkpoints)

### Step 4: Verify Container Health
Check that all containers report healthy status:
```bash
docker compose -f docker/docker-compose.yml ps
```

---

## 3. Kubernetes Cloud-Native Deployment

The platform provides modular Kubernetes manifests located under `k8s/base/` and `k8s/ingress/`.

### Directory Layout
```
k8s/
├── base/
│   ├── minio-statefulset.yaml          # MinIO 2-replica StatefulSet with PersistentVolumeClaims
│   ├── minio-service.yaml              # Headless & ClusterIP service for MinIO S3 & Console
│   ├── hive-metastore-deployment.yaml  # Hive Metastore 3.0 standalone Deployment
│   ├── hive-metastore-service.yaml     # Hive Metastore ClusterIP service (port 9083)
│   ├── spark-thrift-deployment.yaml    # Spark 3.3.3 Thrift Server Deployment (ports 10000, 4040)
│   ├── spark-thrift-service.yaml       # Spark Thrift ClusterIP service (ports 10000, 4040)
│   ├── spark-executor-pod-template.yaml# ConfigMap holding executor pod template for dynamic scaling
│   └── kustomization.yaml              # Kustomize entrypoint for namespace 'lakehouse'
└── ingress/
    ├── minio-ingress.yaml              # Nginx Ingress routing S3 and Console hostnames
    └── spark-ui-ingress.yaml           # Nginx Ingress routing Spark Web UI (port 4040)
```

### Step 1: Configure Local DNS Resolution
Add the following entries to `/etc/hosts` to enable local ingress routing:
```text
127.0.0.1  s3.minio.lakehouse.local
127.0.0.1  console.minio.lakehouse.local
127.0.0.1  spark.lakehouse.local
127.0.0.1  spark-ui.lakehouse.local
```

### Step 2: Deploy Using Kustomize
Apply the full base infrastructure stack into the `lakehouse` namespace:
```bash
kubectl apply -k k8s/base
```

### Step 3: Inspect Pods and Ingress Resources
Verify that pods transition to `Running` and readiness probes pass:
```bash
kubectl get pods,svc,ingress -n lakehouse
```

### Step 4: Spark Dynamic Allocation via Executor Pod Template
The `spark-executor-pod-template.yaml` ConfigMap allows the Spark Thrift Server driver to spin up and tear down Kubernetes executor pods dynamically. The driver mounts the template file at `/opt/spark/pod-template/executor-pod-template.yaml` and applies resource limits (`requests: 1000m CPU / 2Gi RAM`, `limits: 2000m CPU / 4Gi RAM`) under non-root user `185`.

---

## 4. End-to-End Verification & Health Probes

### Automated Verification Script
Run the automated verification suite to validate socket availability, Hive Metastore integration, and Delta Lake S3A I/O:
```bash
python scripts/verify_spark_thrift.py --host localhost --port 10000 --retries 10 --retry-delay 3
```

The script executes a 6-stage probe:
1. **TCP Port Probe:** Verifies socket availability on port 10000.
2. **Ping Probe:** Executes `SELECT 1` to ensure the Thrift server can parse and plan SQL queries.
3. **HMS Integration:** Queries `SHOW DATABASES` to verify communication with Hive Metastore.
4. **Delta Table DDL:** Creates a test database `lakehouse_smoke_test` and Delta table on `s3a://lakehouse/`.
5. **Delta Table DML:** Inserts a test record and selects it back to verify ACID commit logs (`_delta_log/`).
6. **Idempotent Cleanup:** Drops the smoke test table and database.

### Manual SQL Verification via Beeline / Docker
To connect interactively to the Spark Thrift Server using Beeline inside the container:
```bash
docker exec -it lakehouse-spark-thrift-server /opt/spark/bin/beeline -u "jdbc:hive2://localhost:10000/default" -n spark
```

Sample interactive verification queries:
```sql
-- Check active catalogs and databases
SHOW DATABASES;

-- Inspect Delta Lake support
CREATE DATABASE IF NOT EXISTS smoke_test;
CREATE TABLE IF NOT EXISTS smoke_test.test_delta (
    id INT,
    event_name STRING,
    created_at TIMESTAMP
) USING delta;

INSERT INTO smoke_test.test_delta VALUES (1, 'lakehouse_init', current_timestamp());

SELECT * FROM smoke_test.test_delta;

-- Inspect transaction history via Delta time travel
DESCRIBE HISTORY smoke_test.test_delta;

-- Cleanup
DROP TABLE smoke_test.test_delta;
DROP DATABASE smoke_test;
```

---

## 5. Troubleshooting & Maintenance Runbook

### Issue 1: Spark Thrift Server Connection Refused on Port 10000
- **Symptom:** `Socket connection failed: Connection refused` or Beeline fails to connect.
- **Root Cause:** The Thrift Server process may take 30–60 seconds to fully initialize the SparkContext and register with Hive Metastore.
- **Remedy:** Check the container logs:
  ```bash
  docker logs -f lakehouse-spark-thrift-server
  ```
  Verify that `HiveThriftServer2: HiveThriftServer2 started` appears in the log before initiating queries.

### Issue 2: S3A Bucket Access Denied or NoSuchBucketException
- **Symptom:** `AmazonS3Exception: The specified bucket does not exist` when creating Delta tables.
- **Root Cause:** MinIO was restarted without PersistentVolume data or the initialization script has not been run.
- **Remedy:** Re-run the bucket initialization script:
  ```bash
  bash scripts/init_minio.sh
  ```

### Issue 3: Hive Metastore Schema Out-of-Sync or Connection Pool Exhaustion
- **Symptom:** `MetaException: Version information not found in VERSION table` or MySQL connection timeout.
- **Root Cause:** Metastore database initialization had not completed before Hive Metastore attempted to start.
- **Remedy:** Verify `metastore-db` container health:
  ```bash
  docker compose -f docker/docker-compose.yml restart metastore-db hive-metastore
  ```
