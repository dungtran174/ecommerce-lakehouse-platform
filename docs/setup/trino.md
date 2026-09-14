# Trino Distributed Query Engine & Cross-Source Federation Runbook

This document specifies the deployment architecture, catalog connectors, performance tuning, security governance, and multi-dimensional analytical SQL recipes for **Trino 435 (MPP Query Engine)** within the **Modern E-Commerce Data Lakehouse Platform**.

Trino serves as the high-concurrency, low-latency SQL serving tier, providing unified query access across ACID Delta Lake tables on MinIO S3, Apache Hive Metastore, and operational MySQL OLTP databases with centralized Apache Ranger authorization.

---

## 1. Architecture Overview & Federation Topology

```
                                  +-------------------------------------------------------------+
                                  |                     Client Applications                     |
                                  |       Metabase BI (3000)  |  CloudBeaver Web SQL (8978)     |
                                  |       Trino CLI / JDBC    |  Python (trino-python-client)   |
                                  +------------------------------+------------------------------+
                                                                 |
                                                       HTTP / JDBC (Port 8085)
                                                                 v
+-------------------------------------------------------------------------------------------------------------------------------+
| Trino Distributed MPP Query Engine (Coordinator: trino.lakehouse.local:8085)                                                  |
| - Cost-Based Optimizer (CBO): Automatic Join Distribution & Join Reordering                                                   |
| - Concurrency: task.concurrency=8, exchange.client-threads=8, task.http-response-threads=8                                    |
| - Security Plugin: Apache Ranger 2.4.0 System Access Control (RBAC & Dynamic Column Masking)                                 |
+-------------------+--------------------------------------------+------------------------------------------+-------------------+
                    |                                            |                                          |
          Catalog: lakehouse / delta                    Catalog: hive                              Catalog: mysql
          (connector: delta-lake)                       (connector: hive)                          (connector: mysql)
                    |                                            |                                          |
                    v                                            v                                          v
+---------------------------------------+   +---------------------------------------+   +---------------------------------------+
| MinIO S3 Object Storage (Port 9000)   |   | MinIO S3 Object Storage (Port 9000)   |   | MySQL OLTP Database (Port 3306)       |
| - Bucket: lakehouse                   |   | - Bucket: lakehouse                   |   | - Database: ecommerce_oltp            |
| - bronze / silver / gold Delta tables |   | - Legacy Hive Parquet / ORC tables    |   | - Source transactional tables         |
+-------------------+-------------------+   +-------------------+-------------------+   +---------------------------------------+
                    |                                           |
                    +---------------------+---------------------+
                                          | Thrift RPC (Port 9083)
                                          v
                    +-------------------------------------------+
                    | Apache Hive Metastore 3.0 (HMS)           |
                    | - Catalog schema registry & partition DB  |
                    +-------------------------------------------+
```

### Component Directory

| Component | Container Name | K8s Deployment | Port | Internal Hostname | Purpose |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **Trino Coordinator** | `lakehouse-trino-coordinator` | `trino-coordinator` | `8085` | `trino-coordinator` | Query planning, CBO optimization, Ranger authorization, Web UI |
| **Trino Worker** | `lakehouse-trino-worker` | `trino-worker` | `8085` | `trino-worker` | Distributed parallel query task execution and data processing |
| **Hive Metastore** | `lakehouse-hive-metastore` | `hive-metastore` | `9083` | `hive-metastore` | Centralized schema definition and partition metadata registry |
| **MinIO Storage** | `lakehouse-minio` | `minio-0` | `9000` | `minio` | S3-compatible storage hosting bronze, silver, and gold tiers |
| **Ranger Admin** | `lakehouse-ranger-admin` | `ranger-admin` | `6080` | `ranger-admin` | Centralized RBAC policy authoring, audit logging, and dynamic masking |
| **MySQL OLTP** | `lakehouse-mysql-oltp` | `mysql-oltp` | `3306` | `mysql-oltp` | Operational transactional store for federated reconciliation |

---

## 2. Catalog Connectors & Federation Setup

Trino organizes data sources through catalog properties files located in `docker/trino/catalog/`:

### 2.1. Delta Lake Catalogs (`delta.properties` & `lakehouse.properties`)
Connects directly to Delta Lake ACID tables stored on MinIO:

```properties
connector.name=delta-lake
hive.metastore.uri=thrift://hive-metastore:9083
fs.native-s3.enabled=true
s3.endpoint=http://minio:9000
s3.region=us-east-1
s3.path-style-access=true
s3.aws-access-key=minioadmin
s3.aws-secret-key=minioadmin
s3.ssl.enabled=false
delta.register-table-procedure.enabled=true
delta.metadata.cache-ttl=10m
delta.metadata.cache-size=1000
delta.max-partitions-per-writer=100
hive.metastore-cache-ttl=10m
hive.metastore-refresh-interval=2m
hive.metastore-cache-maximum-size=5000
hive.metastore.partition-batch-size=1000
```

> **Note:** The `lakehouse` catalog is identical in configuration to `delta`, providing exact alias alignment with Apache Ranger security policies and BI tools.

### 2.2. Hive Parquet Catalog (`hive.properties`)
Enables querying standard Parquet files registered in Hive Metastore:

```properties
connector.name=hive
hive.metastore.uri=thrift://hive-metastore:9083
fs.native-s3.enabled=true
s3.endpoint=http://minio:9000
s3.path-style-access=true
s3.aws-access-key=minioadmin
s3.aws-secret-key=minioadmin
s3.ssl.enabled=false
hive.storage-format=PARQUET
hive.parquet.use-column-names=true
hive.metastore-cache-ttl=10m
hive.metastore-refresh-interval=2m
hive.metastore-cache-maximum-size=5000
hive.metastore.partition-batch-size=1000
```

### 2.3. MySQL OLTP Federation Catalog (`mysql.properties`)
Enables live cross-source queries between MySQL transactional tables and Lakehouse Delta storage:

```properties
connector.name=mysql
connection-url=jdbc:mysql://mysql-oltp:3306/ecommerce_oltp
connection-user=lakehouse_user
connection-password=lakehouse_password
```

---

## 3. Centralized Security & Authorization via Apache Ranger

Trino integrates with Apache Ranger via the System Access Control plugin configured in `docker/trino/etc/access-control.properties`:

```properties
access-control.name=ranger
ranger.trino-service-name=dev_trino
ranger.policy-cache-dir=/data/trino/ranger/cache
ranger.poll-interval=30s
```

### Authorization & Enforcement Flow

1. **Query Submission:** Client sends SQL query to Trino Coordinator.
2. **AST Parsing & Resource Extraction:** Trino extracts targeted catalogs, schemas, tables, and columns.
3. **Ranger Interception:** The Ranger plugin checks permissions against cached policies synced from `ranger-admin:6080`.
4. **RBAC & Schema Protection:** Users outside authorized groups are blocked from restricted schemas (e.g. `marketing`).
5. **Dynamic Data Masking:** Column masking rewrites query AST:
   - Customer `email`: Hashed via `MASK_HASH`.
   - Customer `phone_number`: Masked via `MASK_SHOW_LAST_4`.
6. **Execution:** Authorized query executes in parallel across Trino workers.
7. **Audit Logging:** Access result (`1` for allowed, `0` for denied) logged to console and server logs via log4j.

---

## 4. Performance Tuning & Execution Concurrency

The coordinator and worker configurations in `docker/trino/etc/config.properties` and `config-worker.properties` are tuned for multi-million-row fact table analytics:

```properties
# Memory Management
query.max-memory=4GB
query.max-memory-per-node=1GB
query.max-total-memory-per-node=2GB

# Concurrency & Networking
task.concurrency=8
task.http-response-threads=8
task.info-update-interval=2s
exchange.client-threads=8

# Cost-Based Optimizer (CBO)
join-distribution-type=AUTOMATIC
optimizer.join-reordering-strategy=AUTOMATIC
optimizer.optimize-metadata-queries=true
```

- **`task.concurrency=8`:** Scales local operator concurrency to utilize 8 parallel processing pipelines for scans and hash joins.
- **`exchange.client-threads=8`:** Eliminates network buffer bottlenecks during cross-worker data shuffling.
- **`join-distribution-type=AUTOMATIC`:** Automatically broadcasts small dimension tables while partitioning large fact tables.
- **`delta.metadata.cache-ttl=10m`:** Caches Delta transaction log commits locally to avoid redundant S3 `LIST` API requests.

---

## 5. Multi-Dimensional SQL Query Recipes

The following recipes demonstrate advanced analytics, cross-source federation, and security policy enforcement on Trino:

### Recipe 1: Cross-Source Federation (Reconciliation Audit)
Compare operational MySQL order counts with Gold Lakehouse fact tables in a single query:

```sql
SELECT 
    'MySQL OLTP' AS source_system,
    COUNT(*) AS total_orders,
    COALESCE(SUM(total_amount), 0) AS gross_revenue
FROM mysql.ecommerce_oltp.orders
WHERE order_status = 'COMPLETED'

UNION ALL

SELECT 
    'Lakehouse Gold Mart' AS source_system,
    COUNT(*) AS total_orders,
    COALESCE(SUM(total_amount), 0) AS gross_revenue
FROM lakehouse.gold_sale_mart.fact_order
WHERE order_status = 'COMPLETED';
```

### Recipe 2: Executive Revenue & Trend Analysis
Analyze monthly revenue performance and Average Order Value (AOV) across Gold dimensions:

```sql
SELECT 
    d.year,
    d.month,
    d.month_name,
    COUNT(f.order_id) AS total_completed_orders,
    ROUND(SUM(f.total_amount), 2) AS gross_revenue_vnd,
    ROUND(AVG(f.total_amount), 2) AS average_order_value_vnd,
    COUNT(DISTINCT f.customer_key) AS unique_purchasers
FROM lakehouse.gold_sale_mart.fact_order f
JOIN lakehouse.gold_sale_mart.dim_date d 
    ON f.order_date_key = d.date_key
WHERE f.order_status = 'COMPLETED'
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year DESC, d.month DESC;
```

### Recipe 3: Bestselling Products & Brand Share Federation
Federate Delta Lake order items with MySQL brand origin data:

```sql
SELECT 
    p.product_id,
    p.product_name,
    b.brand_name,
    b.country_of_origin,
    SUM(foi.quantity) AS total_units_sold,
    ROUND(SUM(foi.line_total), 2) AS total_revenue_vnd
FROM lakehouse.gold_sale_mart.fact_order_items foi
JOIN lakehouse.gold_sale_mart.dim_product p 
    ON foi.product_key = p.product_key
JOIN mysql.ecommerce_oltp.brands b 
    ON p.brand_id = b.brand_id
GROUP BY p.product_id, p.product_name, b.brand_name, b.country_of_origin
ORDER BY total_revenue_vnd DESC
LIMIT 10;
```

### Recipe 4: Customer PII Dynamic Masking Verification
Verify that Apache Ranger dynamically masks sensitive fields for data analysts:

```sql
SELECT 
    customer_key,
    customer_name,
    email,              -- Masked via MASK_HASH for non-admin personas
    phone_number,       -- Masked via MASK_SHOW_LAST_4 (e.g., ***-***-5678)
    loyalty_tier,
    province
FROM lakehouse.gold_sale_mart.dim_customer
LIMIT 10;
```

### Recipe 5: ML Feature Store Aggregation
Retrieve customer rolling 3-day behavioral features for churn or repurchase propensity models:

```sql
SELECT 
    feature_date,
    customer_id,
    rolling_3d_event_count,
    rolling_3d_product_views,
    rolling_3d_cart_adds,
    rolling_3d_checkout_starts,
    rolling_3d_order_count,
    rolling_3d_total_spend,
    next_day_purchased
FROM lakehouse.gold_ml.ml_user_behavior_3d_agg_feature
WHERE feature_date = CURRENT_DATE - INTERVAL '1' DAY
ORDER BY rolling_3d_total_spend DESC
LIMIT 20;
```

---

## 6. Operational & Verification Runbook

### Starting the Trino Cluster

```bash
# Start Coordinator, Worker, MinIO, Metastore, and Ranger
docker compose -f docker/docker-compose.yml up -d \
  minio metastore-db hive-metastore ranger-db ranger-admin trino-coordinator trino-worker
```

### Connecting via Interactive CLI

```bash
docker exec -it lakehouse-trino-coordinator \
  trino --server http://localhost:8085 --catalog lakehouse --schema default
```

### Inspecting Node Status via REST API

```bash
curl -s http://localhost:8085/v1/node | jq .
```

### Running Automated Test Suite

```bash
pytest tests/test_trino_config.py \
       tests/test_trino_catalogs.py \
       tests/test_trino_ranger_integration.py \
       tests/test_trino_tuning.py \
       tests/test_k8s_trino_manifests.py -v
```

---

## 7. Troubleshooting & Diagnostic Guide

### Issue 1: `AccessDeniedException: Access Denied: User [analyst] cannot select from [table]`
- **Cause:** User does not belong to authorized Ranger group or policy does not grant `SELECT`.
- **Diagnostic:** Check effective user via `SELECT current_user`. Check Ranger policy in `http://localhost:6080`.
- **Resolution:** Add user to group `analysts` or add policy item in `dev_trino`.

### Issue 2: `Could not connect to Hive Metastore at thrift://hive-metastore:9083`
- **Cause:** HMS container not ready or Thrift port unreachable.
- **Diagnostic:** Run `docker exec -it lakehouse-trino-coordinator nc -zv hive-metastore 9083`.
- **Resolution:** Verify `metastore-db` is healthy and restart `lakehouse-hive-metastore`.

### Issue 3: `Query exceeded maximum total memory limit of 4GB`
- **Cause:** Unbounded Cartesian product join or large shuffle without filter predicate.
- **Diagnostic:** View query execution plan via `EXPLAIN ANALYZE <query>`.
- **Resolution:** Ensure `join-distribution-type=AUTOMATIC` is set and add partition filter on `order_date` or `year/month`.
