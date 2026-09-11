# dbt Medallion Architecture & Data Lineage Documentation

This document outlines the end-to-end data transformation pipeline orchestrated by **dbt-spark** atop **Apache Spark Thrift Server** and **Delta Lake** within the Modern E-Commerce Data Lakehouse Platform.

---

## 1. Architectural Overview

The transformation layer implements Databricks' Medallion Architecture pattern, transitioning raw data across progressive refinement tiers:

```mermaid
flowchart LR
    subgraph Bronze["Bronze Tier (MinIO / S3A)"]
        b_mysql[("MySQL OLTP Snapshots")]
        b_clickstream[("Raw Clickstream JSON")]
    end

    subgraph Staging["Staging Layer (Views)"]
        stg_cust["stg_customers"]
        stg_prod["stg_products"]
        stg_brands["stg_brands"]
        stg_cat["stg_categories"]
        stg_pay["stg_payment_methods"]
        stg_orders["stg_orders"]
        stg_items["stg_order_items"]
        stg_events["stg_clickstream_events"]
    end

    subgraph Silver["Silver Tier (Delta Tables)"]
        slv_cust["silver_customers"]
        slv_prod["silver_products"]
        slv_brands["silver_brands"]
        slv_cat["silver_categories"]
        slv_pay["silver_payment_methods"]
        slv_orders["silver_orders"]
        slv_items["silver_order_items"]
        slv_sessions["silver_user_sessions"]
        slv_actions["silver_session_actions"]
    end

    subgraph Gold["Gold Tier (Sale Mart & ML Feature Store)"]
        dim_c["dim_customer"]
        dim_p["dim_product"]
        dim_pm["dim_payment_method"]
        dim_d["dim_date"]
        fact_o["fact_order"]
        fact_oi["fact_order_items"]
        ml_feat["ml_user_behavior_3d_agg_feature"]
    end

    b_mysql --> stg_cust & stg_prod & stg_brands & stg_cat & stg_pay & stg_orders & stg_items
    b_clickstream --> stg_events

    stg_cust --> slv_cust
    stg_prod --> slv_prod
    stg_brands --> slv_brands
    stg_cat --> slv_cat
    stg_pay --> slv_pay
    stg_orders --> slv_orders
    stg_items --> slv_items
    stg_events --> slv_sessions
    stg_events --> slv_actions

    slv_cust --> dim_c
    slv_prod & slv_cat & slv_brands --> dim_p
    slv_pay --> dim_pm

    slv_orders & slv_items --> fact_o
    slv_items & slv_orders --> fact_oi

    dim_c -.-> fact_o & fact_oi
    dim_p -.-> fact_oi
    dim_pm -.-> fact_o & fact_oi
    dim_d -.-> fact_o & fact_oi

    slv_sessions & slv_actions --> ml_feat
```

---

## 2. Medallion Transformation Tiers

### 2.1 Staging Layer (`staging.*`)
- **Materialization:** `view`
- **Purpose:** 1-to-1 lightweight abstraction over external Bronze Delta tables. Renames source fields to consistent lower snake_case conventions, casts basic data types, and applies row-level sanitization filters without modifying source grain.
- **Key Models:**
  - `stg_customers`: Cleansed customer profile views.
  - `stg_products`: Standardized product catalog records.
  - `stg_brands`, `stg_categories`, `stg_payment_methods`: Reference lookup views.
  - `stg_orders`, `stg_order_items`: Transaction headers and line items.
  - `stg_clickstream_events`: High-velocity website interaction logs.

### 2.2 Silver Layer (`silver.*`)
- **Materialization:** `table` (Delta Lake)
- **Purpose:** Cleansed, deduplicated, enriched single-source-of-truth conformed tables. Handles entity deduplication via `row_number() over (partition by ... order by updated_at desc)`, parses JSON telemetry arrays via `explode(from_json(...))`, and partitions event streams by `year/month/day`.
- **Key Models:**
  - `silver_customers`: Cleansed master customer directory with normalized email and phone.
  - `silver_products`: Curated product master with verified categories and pricing.
  - `silver_brands`, `silver_categories`, `silver_payment_methods`: Master reference tables.
  - `silver_orders`, `silver_order_items`: Conformed transactions with validated non-negative pricing.
  - `silver_user_sessions`: Flattened session engagement with device telemetry and geo coordinates.
  - `silver_session_actions`: Granular unnested actions with binary funnel interaction flags.

### 2.3 Gold Layer (`sale_mart.*` & `ml.*`)
- **Materialization:** `table` (Delta Lake)
- **Purpose:** Kimball Galaxy dimensional schema for BI analytical querying, executive KPI dashboards, and high-performance ML feature stores.
- **Sale Mart Galaxy Schema (`sale_mart.*`):**
  - `dim_customer`: Customer demographics, address geography, and loyalty tiers.
  - `dim_product`: Denormalized product dimension joined with brand and category hierarchies.
  - `dim_payment_method`: Conformed payment channel dimension with SCD Type 2 tracking.
  - `dim_date`: Continuous calendar dimension (2020–2030) with rich temporal attributes.
  - `fact_order`: Order-grain transaction fact table capturing gross sales, discounts, and net revenue.
  - `fact_order_items`: Line-item fact table linking SKU purchases directly to multidimensional keys.
- **Machine Learning Feature Store (`ml.*`):**
  - `ml_user_behavior_3d_agg_feature`: Rolling 3-day window aggregation of user behavioral features (sessions, pageviews, action breakdown, conversion ratios) and target label (`label_purchase_tomorrow`) for Spark MLlib training.

---

## 3. Data Quality & Assertion Framework

The dbt project leverages automated data quality checks executed before downstream data consumption:

### 3.1 Generic Schema Tests
- **Primary Key Uniqueness & Non-Null:** Enforced on every dimension (`customer_key`, `product_key`, `date_key`, `payment_method_id`) and fact table (`order_id`, `order_item_id`).
- **Referential Integrity (`relationships`):** Foreign keys in `fact_order` and `fact_order_items` must strictly reference valid primary keys in conformed dimension tables.
- **Accepted Values (`accepted_values`):** Binary flags (`is_weekend`, `is_weekday`, `label_purchase_tomorrow`) are constrained to `[0, 1]`.

### 3.2 Singular Business Tests
- **`assert_positive_revenue.sql`:** Queries across `fact_order` and `fact_order_items` ensuring no transaction possesses negative gross prices, negative discounts, or negative net revenue.

---

## 4. Operational Execution Commands

Run transformation workloads against Spark Thrift Server:

```bash
# Compile SQL models and validate Jinja templating
dbt compile --project-dir dbt --profiles-dir dbt

# Execute full Medallion pipeline (Staging -> Silver -> Gold)
dbt run --project-dir dbt --profiles-dir dbt

# Run all schema and data quality tests
dbt test --project-dir dbt --profiles-dir dbt

# Generate and inspect interactive dbt documentation catalog
dbt docs generate --project-dir dbt --profiles-dir dbt
dbt docs serve --port 8085
```
