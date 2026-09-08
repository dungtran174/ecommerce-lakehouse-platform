<div align="center">

# Modern E-Commerce Data Lakehouse Platform
### Enterprise-Grade Lakehouse Architecture with Medallion Pattern, Delta Lake, Apache Spark, Trino, dbt, Apache Airflow, Apache Ranger, Metabase & Spark MLlib

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Apache Spark](https://img.shields.io/badge/Apache%20Spark-3.3.4-E25A1C.svg?logo=apachespark&logoColor=white)](https://spark.apache.org/)
[![Delta Lake](https://img.shields.io/badge/Delta%20Lake-2.2.0-00ADD8.svg?logo=delta&logoColor=white)](https://delta.io/)
[![Trino](https://img.shields.io/badge/Trino-MPP%20SQL-DD00A1.svg?logo=trino&logoColor=white)](https://trino.io/)
[![dbt](https://img.shields.io/badge/dbt--spark-1.7-FF694B.svg?logo=dbt&logoColor=white)](https://www.getdbt.com/)
[![Apache Airflow](https://img.shields.io/badge/Apache%20Airflow-2.7-017CEE.svg?logo=apacheairflow&logoColor=white)](https://airflow.apache.org/)
[![MinIO](https://img.shields.io/badge/MinIO-S3%20Compatible-C72C48.svg?logo=minio&logoColor=white)](https://min.io/)
[![Apache Ranger](https://img.shields.io/badge/Apache%20Ranger-Governance-24A148.svg)](https://ranger.apache.org/)
[![Metabase](https://img.shields.io/badge/Metabase-BI%20Analytics-509EE3.svg?logo=metabase&logoColor=white)](https://www.metabase.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-Helm-326CE5.svg?logo=kubernetes&logoColor=white)](https://kubernetes.io/)


</div>

---

## Table of Contents

- [1. Business Context & Problem Statement](#1-business-context--problem-statement)
- [2. System Architecture](#2-system-architecture)
- [3. Medallion Lakehouse Design](#3-medallion-lakehouse-design)
- [4. Tech Stack](#4-tech-stack)
- [5. Repository Structure](#5-repository-structure)
- [6. Data Governance & Security](#6-data-governance--security)
- [7. Business Intelligence & Dashboards](#7-business-intelligence--dashboards)
- [8. Machine Learning: Customer Purchase Prediction](#8-machine-learning-customer-purchase-prediction)
- [9. Quick Start & Operational Lifecycle](#9-quick-start--operational-lifecycle)
- [10. References](#10-references)

---

## 1. Business Context & Problem Statement

### The Analytics Bottleneck in Modern E-Commerce
Modern 24/7 e-commerce platforms generate dual streams of high-volume data:
- **Transactional Entities (OLTP):** Orders, line items, customer profiles, product catalogs, and payment methods. Running analytical reporting queries directly on operational relational databases creates resource contention, locking, and degraded checkout responsiveness.
- **Behavioral Clickstream Events:** Web and mobile interaction events (page impressions, search keywords, cart updates, checkout attempts). These semi-structured streams reach gigabytes to terabytes daily and cannot be accommodated by traditional schema-on-write warehouses without expensive ETL pre-processing.

### The Decoupled Lakehouse Solution
This platform implements an open-format **Data Lakehouse** architecture:
1. **Separation of Compute and Storage:** Scalable distributed object storage (**MinIO**) decoupled from processing engines (**Spark**, **Trino**).
2. **ACID Transactional Guarantees:** **Delta Lake** provides serializable isolation, schema enforcement, time-travel auditing, and efficient partition pruning over Apache Parquet.
3. **Enterprise Security & Governance:** Centralized Role-Based Access Control (RBAC) and dynamic PII column masking via **Apache Ranger** and the Trino-Ranger plugin.
4. **End-to-End Workflow Automation:** Scheduled pipelines managed by **Apache Airflow** coordinate ingestion, multi-tier dbt transformations, automated quality assertions, and ML inference scoring.

---

## 2. System Architecture

![System Architecture](images/architecture.png)

### Data Flow Lifecycle
1. **Source Ingestion:**
   - Transactional tables are extracted from MySQL in batch snapshots and incremental slices via JDBC into the Bronze landing zone.
   - User activity logs (~12GB NDJSON) are transferred from web application nodes via SFTP into daily partition folders in Bronze.
2. **Storage & Metadata Management:**
   - Raw files reside in MinIO S3 buckets (`lakehouse/bronze/`).
   - Apache Hive Metastore (HMS) maintains catalog metadata, schemas, and partition locations.
3. **Data Transformation & Cleansing (Silver Layer):**
   - dbt models run on Spark Thrift Server to flatten nested JSON structs, cast strict data types, sanitize PII, and register Delta Lake tables.
4. **Dimensional Modeling & Feature Stores (Gold Layer):**
   - Kimball Galaxy Schema (`sale_mart`) materializes dimension tables and granular fact tables.
   - Rolling 3-day behavioral features are generated into `ml.user_behavior_3d_agg_feature`.
5. **Serving & Query Federation:**
   - Trino executes distributed MPP queries against Delta Lake tables with zero data duplication.
   - Apache Ranger enforces fine-grained authorization before query compilation.
6. **Downstream Consumption:**
   - Metabase renders executive and operational dashboards.
   - Spark MLlib trains a Logistic Regression classifier to predict next-day purchase probability.

For in-depth architectural specifications and diagrams, refer to [docs/architecture.md](docs/architecture.md).

---

## 3. Medallion Lakehouse Design

| Layer | Storage & Format | Data Entities & Tables | Processing Objectives |
| :--- | :--- | :--- | :--- |
| **Bronze** | MinIO `lakehouse/bronze/`<br>Raw CSV & NDJSON | - `customers_snapshot.csv`<br>- `products_snapshot.csv`<br>- `brands_snapshot.csv`<br>- `category_snapshot.csv`<br>- `payment_method_snapshot.csv`<br>- `orders_{yyyymmdd}.csv`<br>- `order_items_{yyyymmdd}.csv`<br>- `part_{xxxx}.ndjson` (Clickstream) | Raw, immutable landing zone. Preserves full historical fidelity and audit lineage directly from source extraction. |
| **Silver** | MinIO `lakehouse/silver/`<br>**Delta Lake** (Parquet) | - `silver.customer`<br>- `silver.products`<br>- `silver.brands`<br>- `silver.category`<br>- `silver.payment_method`<br>- `silver.orders`<br>- `silver.order_items`<br>- `silver.user_sessions` *(Partitioned by Y/M/D)*<br>- `silver.session_actions` *(Partitioned by Y/M/D)* | Cleansed, strongly typed, and deduplicated conformed tables. Flattens nested JSON payloads, sanitizes PII, and applies ACID guarantees. |
| **Gold** | MinIO `lakehouse/gold/`<br>**Delta Lake** (Parquet) | **Sale Mart (Kimball Galaxy Schema):**<br>- `sale_mart.dim_customer`<br>- `sale_mart.dim_product`<br>- `sale_mart.dim_date`<br>- `sale_mart.dim_payment_method` *(SCD2)*<br>- `sale_mart.fact_order`<br>- `sale_mart.fact_order_items`<br>**ML & Marketing Marts:**<br>- `ml.user_behavior_3d_agg_feature`<br>- `marketing.high_value_purchase_campaign` | Production analytical data marts optimized for executive BI dashboards, ad-hoc OLAP exploration, and rolling 3-day ML feature stores. |

For detailed field definitions, constraints, and data types, refer to [docs/data_dictionary.md](docs/data_dictionary.md).

---

## 4. Tech Stack

| Component | Technology | Role & Purpose |
| :--- | :--- | :--- |
| **Object Storage** | [MinIO](https://min.io/) | S3-compatible distributed object storage for all Medallion tiers |
| **Table Format** | [Delta Lake 2.2](https://delta.io/) | ACID transactions, time travel, and metadata indexing over Parquet |
| **Catalog Registry** | [Apache Hive Metastore 3.0](https://hive.apache.org/) | Centralized metastore mapping Delta tables to logical schemas |
| **Compute Engine** | [Apache Spark 3.3](https://spark.apache.org/) | Distributed in-memory data processing, Thrift server, and Spark MLlib |
| **Transformation** | [dbt-spark 1.7](https://www.getdbt.com/) | Modular SQL data transformation, testing, and schema documentation |
| **Orchestration** | [Apache Airflow 2.7](https://airflow.apache.org/) | DAG scheduling, dependency management, and automated retries |
| **Serving Engine** | [Trino](https://trino.io/) | Distributed MPP SQL engine for sub-second analytical queries |
| **Governance** | [Apache Ranger](https://ranger.apache.org/) | Centralized access control, RBAC, and dynamic column masking |
| **BI & Analytics** | [Metabase](https://www.metabase.com/) & [CloudBeaver](https://cloudbeaver.io/) | Executive BI dashboard reporting and web SQL IDE exploration |
| **Infrastructure** | [Docker](https://www.docker.com/) & [Kubernetes](https://kubernetes.io/) | Multi-container compose stack and cloud-native Helm deployments |

---

## 5. Repository Structure

```
ecommerce-lakehouse-platform/
├── .github/
│   └── workflows/
│       └── ci-lint.yml                  # Automated Python, SQL, and YAML linting
├── airflow/
│   ├── config/                          # Airflow environment configuration
│   ├── dags/                            # Batch ingestion & ML DAGs
│   └── plugins/                         # Custom Airflow operators and hooks
├── bi/
│   ├── metabase/                        # Exported dashboard queries and definitions
│   └── screenshots/                     # Visual dashboard assets
├── data_generators/                     # Synthetic OLTP and clickstream log generators
├── dbt/
│   ├── macros/                          # Custom dbt macros (Delta properties, schemas)
│   ├── models/                          # Staging, Silver, and Gold SQL models
│   └── tests/                           # Schema validations and business assertions
├── docker/                              # Docker Compose stack & custom Dockerfiles
├── docs/                                # Architecture, data dictionary, runbooks
├── images/                              # Architecture diagrams and dashboard screenshots
├── k8s/                                 # Kubernetes base manifests, ingress, Helm values
├── ml/                                  # Zeppelin notebooks & PySpark ML pipelines
├── scripts/                             # Automation scripts (MinIO init, bootstrap, tests)
├── Makefile                             # Central developer automation interface
├── requirements.txt                     # Core production dependencies
├── requirements-dev.txt                 # Linting and testing dependencies
└── README.md
```

---

## 6. Data Governance & Security

Using **Apache Ranger** integrated with **Trino**:
- **Role-Based Access Control (RBAC):** Restricts access to sensitive data marts. For example, marketing campaign leads are restricted to marketing personnel, while standard analysts can query only aggregated sale metrics.
- **Dynamic Column Masking:** Sensitive customer fields (`phone_number`, `email`) are masked dynamically for unauthorized roles.
- **Audit Logging:** Every read and write transaction against Delta Lake tables is recorded for compliance.

---

## 7. Business Intelligence & Dashboards

![Metabase Dashboard](images/dashboard.png)

Production dashboards configured on **Metabase** connect directly to **Trino**:
1. **Executive Revenue Overview:** Year-over-Year revenue growth, total gross orders, and average order value (AOV).
2. **Product & Brand Performance:** Top 10 bestselling products by volume and revenue; performance distribution by brand origin.
3. **Geographic Distribution:** Order volume and revenue heatmaps across Vietnamese provinces.
4. **Payment Channel Adoption:** Market share breakdown across digital wallets (Momo, ZaloPay, ShopeePay, VNPay), bank transfer, and COD.

---

## 8. Machine Learning: Customer Purchase Prediction

- **Algorithm:** Spark MLlib Logistic Regression with standardized feature vectors (`VectorAssembler` + `StandardScaler`).
- **Feature Set:** 12 behavioral metrics aggregated across a rolling 3-day window (`sessions_3d`, `duration`, `page_views`, `actions_per_session`, `cart_conversion_rate`, `distinct_products`).
- **Target Label:** Binary outcome indicating whether the user completes a purchase on day $T+1$.
- **Model Evaluation:** Evaluated with **AUC-ROC ~ 0.78** and **F1-Score ~ 0.74**.
- **Actionability:** Daily batch inference automatically populates `marketing.high_value_purchase_campaign` with personalized engagement actions (SMS, Push Notification, Email).

---

## 9. Quick Start & Operational Lifecycle

### Prerequisites
- Docker (>= 24.0) & Docker Compose (>= 2.20)
- Python (>= 3.10, <= 3.11)

### 1. Initialize Environment
```bash
make setup
```

### 2. Start Lakehouse Stack
```bash
make docker-up
```

### 3. Initialize MinIO Buckets
```bash
make init-lakehouse
```

### 4. Seed Synthetic E-Commerce Datasets
```bash
make seed-data
```
For custom volume profiles (`small`, `medium`, `full`) and database seeding options, see the [Data Generation Guide](docs/setup/data_generation.md).

### 5. Access Services
- **Airflow Webserver:** `http://localhost:8080` (admin / admin)
- **MinIO Console:** `http://localhost:9001` (minioadmin / minioadmin)
- **Trino Web UI:** `http://localhost:8085`
- **Metabase:** `http://localhost:3000`
- **CloudBeaver:** `http://localhost:8978`

---

## 10. References

1. Armbrust, M., et al. (2020). *Lakehouse: A New Generation of Open Platforms that Unify Data Warehousing and Advanced Analytics*. Proceedings of CIDR 2021.
2. Kimball, R., & Ross, M. (2013). *The Data Warehouse Toolkit: The Definitive Guide to Dimensional Modeling* (3rd ed.). Wiley.
3. Delta Lake Documentation: [https://docs.delta.io/](https://docs.delta.io/)
4. Trino Distributed Query Engine: [https://trino.io/docs/](https://trino.io/docs/)
5. Apache Ranger Architecture: [https://ranger.apache.org/](https://ranger.apache.org/)
