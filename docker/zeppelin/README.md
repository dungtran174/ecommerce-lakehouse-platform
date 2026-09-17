# Apache Zeppelin Notebook Container

This directory provides the Docker container configuration for [Apache Zeppelin](https://zeppelin.apache.org/) 0.10.1, customized with PySpark, Delta Lake 2.2.0, MinIO S3A storage, and Hive Metastore integration for the Modern E-Commerce Data Lakehouse Platform.

---

## 1. Overview & Machine Learning Role

Apache Zeppelin provides an interactive web-based notebook environment for Data Scientists and ML Engineers to perform:
- **Exploratory Data Analysis (EDA):** Interactive exploration of Bronze, Silver, and Gold Medallion Lakehouse tables.
- **Behavioral Feature Engineering:** Packaging customer session metrics (`gold_ml.ml_user_behavior_3d_agg_feature`) into feature vectors via PySpark MLlib.
- **Model Training & Evaluation:** Training classification and regression models (e.g., Next-Day Purchase Propensity) using Spark MLlib.
- **Model Artifact Export:** Writing trained model pipelines directly to MinIO `s3a://lakehouse/models/`.

---

## 2. Architecture & Container Networking

```
   +-----------------------------------------------------------+
   |                  Browser / Data Scientist                 |
   |                   http://localhost:8082                   |
   +-----------------------------+-----------------------------+
                                 |
                                 v
   +-----------------------------+-----------------------------+
   |                   lakehouse-zeppelin                      |
   |                   apache/zeppelin:0.10.1                  |
   |                   IP: 172.28.0.82:8080                    |
   |                                                           |
   |   +---------------------------------------------------+   |
   |   | Pre-configured PySpark Interpreter                |   |
   |   | - delta-spark 2.2.0 + DeltaSparkSessionExtension  |   |
   |   | - Hadoop AWS S3A (MinIO 172.28.0.20:9000)         |   |
   |   | - Hive Metastore Thrift (172.28.0.31:9083)        |   |
   |   | - Local ML Notebooks: /zeppelin/notebook/         |   |
   |   +---------------------------------------------------+   |
   +-----------------------------+-----------------------------+
                                 |
        +------------------------+------------------------+
        |                                                 |
        v                                                 v
+-------+--------------------+            +---------------+--------------------+
|  lakehouse-minio           |            |  lakehouse-hive-metastore          |
|  MinIO S3 (Port 9000)      |            |  HMS Thrift (Port 9083)            |
|  s3a://lakehouse/warehouse |            |  Catalog schema & table metadata   |
+----------------------------+            +------------------------------------+
```

---

## 3. Pre-Configured Interpreter Properties

| Property | Value | Description |
| :--- | :--- | :--- |
| `spark.master` | `local[*]` | Execution engine (all available CPU cores) |
| `spark.sql.extensions` | `io.delta.sql.DeltaSparkSessionExtension` | Delta Lake SQL syntax and parser support |
| `spark.sql.catalog.spark_catalog` | `org.apache.spark.sql.delta.catalog.DeltaCatalog` | Delta Lake ACID catalog |
| `spark.hadoop.fs.s3a.endpoint` | `http://minio:9000` | Internal MinIO S3 endpoint |
| `spark.hadoop.hive.metastore.uris` | `thrift://hive-metastore:9083` | Hive Metastore catalog Thrift URI |
| `spark.sql.warehouse.dir` | `s3a://lakehouse/warehouse` | Managed Lakehouse storage root |

---

## 4. Operational Commands

```bash
# Start Zeppelin service
docker-compose up -d zeppelin

# Check Zeppelin container health
docker-compose ps zeppelin

# Verify Zeppelin API version
curl -f http://localhost:8082/api/version

# Tail Zeppelin server logs
docker logs -f lakehouse-zeppelin
```
