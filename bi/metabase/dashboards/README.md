# Executive Sales Performance & Revenue Trend Dashboards

This directory contains the production SQL analytical recipes and Metabase dashboard metadata for **Executive Sales Performance & Revenue Trend Analysis**.

---

## 1. Overview & Business Persona

The **Executive Revenue Dashboard** delivers real-time visibility into top-line business indicators for C-suite leaders (CEO, CFO, VP of E-Commerce). It continuously computes revenue trajectories, order velocity, discount efficiency, and time-intelligence growth benchmarks across millions of transactional records in the **Delta Lake Gold Data Mart (`gold_sale_mart`)** served by Trino MPP.

### Core Business Questions Answered
- How is net revenue tracking month-over-month (MoM) and year-over-year (YoY)?
- What is our rolling 7-day sales run rate after filtering day-of-week seasonality?
- What is our current Average Order Value (AOV) and how effective are discount promotions?
- Which days of the week generate the highest volume and revenue share?

---

## 2. Dashboard Layout & Cards

The dashboard layout is structured as a 12-column responsive grid:

| Card ID | Metric / Visualization | Display Type | Grain / Dimensions | Business Formula |
| :--- | :--- | :--- | :--- | :--- |
| **#101** | Total Net Revenue | Scalar (KPI) | Lifetime / Filtered | `SUM(sub_total)` |
| **#102** | Total Orders | Scalar (KPI) | Lifetime / Filtered | `COUNT(DISTINCT order_id)` |
| **#103** | Average Order Value (AOV) | Scalar (KPI) | Lifetime / Filtered | `SUM(sub_total) / COUNT(DISTINCT order_id)` |
| **#104** | Effective Discount Rate | Scalar (KPI) | Lifetime / Filtered | `SUM(discount_amt) / SUM(price) * 100` |
| **#105** | Monthly Revenue & MoM Growth % | Combo (Bar + Line) | `year`, `month_year` | `LAG(net_revenue) OVER (ORDER BY year, month)` |
| **#106** | Quarterly Performance & YoY % | Bar Chart | `quarter_year` | `LAG(net_revenue, 4) OVER (ORDER BY year, quarter)` |
| **#107** | 7-Day Moving Avg Run-Rate | Line Chart | `calendar_date` | `AVG(...) OVER (ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)` |
| **#108** | Day-of-Week Revenue Share | Pie Chart | `day_name` | `SUM(sub_total) / TOTAL * 100` |

---

## 3. Data Lineage & Schema Reference

All queries connect to the **Trino Lakehouse Catalog**:
- Fact Table: `lakehouse.gold_sale_mart.fact_order`
- Dimension Table: `lakehouse.gold_sale_mart.dim_date`

```
  lakehouse.gold_sale_mart.fact_order
  +-----------------------------------+
  | order_id (PK)                     |
  | customer_key (FK)                 |
  | payment_method_key (FK)           |
  | date_key (FK YYYYMMDD)            |---+
  | quantity                          |   |
  | price                             |   |
  | discount_amt                      |   |
  | sub_total                         |   |
  +-----------------------------------+   |
                                          | INNER JOIN on date_key
  lakehouse.gold_sale_mart.dim_date       |
  +-----------------------------------+   |
  | date_key (PK YYYYMMDD)            |<--+
  | calendar_date (DATE)              |
  | year (INT)                        |
  | month (INT)                       |
  | month_year (VARCHAR)              |
  | quarter (INT)                     |
  | quarter_name (VARCHAR)            |
  | quarter_year (VARCHAR)            |
  | day_name (VARCHAR)                |
  | is_weekend (INT)                  |
  +-----------------------------------+
```

---

## 4. Query Execution & Verification

Run these queries directly in Trino CLI or CloudBeaver:

```sql
-- Verify Executive Summary Card metrics
SELECT
    CAST(SUM(f.sub_total) AS DECIMAL(18, 2)) AS net_revenue,
    COUNT(DISTINCT f.order_id) AS total_orders,
    ROUND(CAST(SUM(f.sub_total) AS DOUBLE) / NULLIF(COUNT(DISTINCT f.order_id), 0), 2) AS aov
FROM lakehouse.gold_sale_mart.fact_order f;
```

---

## 5. Product Catalog, Brand Origin & Payment Channel Dashboard

This dashboard visualizes merchandise sales, category concentration, cross-engine brand origin federation, and consumer payment method market share (Momo, ZaloPay, ShopeePay, VNPay, COD, Visa).

### Dashboard Layout & Visual Cards

| Card ID | Metric / Visualization | Display Type | Grain / Dimensions | Data Source |
| :--- | :--- | :--- | :--- | :--- |
| **#201** | Top 10 Products by Net Revenue | Bar Chart | `product_name` | `lakehouse.gold_sale_mart.fact_order_items` + `dim_product` |
| **#202** | Category Revenue Distribution | Donut / Pie | `category` | `lakehouse.gold_sale_mart.fact_order_items` + `dim_product` |
| **#203** | Brand Origin Contribution | Bar Chart | `country_of_origin` | **Federated Join:** `lakehouse` + `mysql.ecommerce_oltp.brands` |
| **#204** | Payment Method Market Share | Pie Chart | `display_name` | `lakehouse.gold_sale_mart.fact_order` + `dim_payment_method` |
| **#205** | Payment Channel Type Share | Bar Chart | `payment_type` | `lakehouse.gold_sale_mart.fact_order` + `dim_payment_method` |
| **#206** | Average Order Value by Channel | Bar Chart | `display_name` | `lakehouse.gold_sale_mart.fact_order` + `dim_payment_method` |

---

## 6. Cross-Engine Federated Query Architecture

Trino seamlessly coordinates distributed query execution across storage engines:
1. **Delta Lake Parquet on MinIO S3:** Stores order line items (`fact_order_items`) and denormalized products (`dim_product`).
2. **MySQL OLTP:** Hosts live operational brand catalogs (`mysql.ecommerce_oltp.brands`).

```
 +-------------------------------------+       +------------------------------------+
 |   Delta Lake Gold Data Mart         |       |   MySQL 8.0 OLTP Database          |
 |   fact_order_items + dim_product    |       |   ecommerce_oltp.brands            |
 +------------------+------------------+       +-----------------+------------------+
                    |                                            |
                    +--------------------+-----------------------+
                                         |
                       Trino Distributed Hash Join
                                         v
                    +------------------------------------+
                    |   Federated Analytical Result      |
                    |   (Product + Brand Origin + Sales) |
                    +------------------------------------+
```

