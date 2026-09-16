-- ==============================================================================
-- Modern E-Commerce Data Lakehouse Platform
-- Metabase BI Dashboard: Product Catalog & Brand Origin Performance
-- Engine: Trino MPP Query Engine
-- Catalog / Schema: lakehouse.gold_sale_mart & mysql.ecommerce_oltp (Federated)
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. Top 10 Best-Selling Products by Net Revenue & Volume
-- Ranks individual SKU performance to identify core catalog revenue drivers
-- ------------------------------------------------------------------------------
SELECT
    p.product_id,
    p.product_name,
    p.category,
    p.brand_name,
    p.brand_origin,
    SUM(foi.quantity) AS total_units_sold,
    CAST(SUM(foi.sub_total) AS DECIMAL(18, 2)) AS total_net_revenue,
    ROUND(AVG(foi.price), 2) AS avg_unit_selling_price,
    COUNT(DISTINCT foi.order_id) AS total_order_appearances
FROM lakehouse.gold_sale_mart.fact_order_items foi
INNER JOIN lakehouse.gold_sale_mart.dim_product p
    ON foi.product_key = p.product_id
GROUP BY
    p.product_id,
    p.product_name,
    p.category,
    p.brand_name,
    p.brand_origin
ORDER BY
    total_net_revenue DESC
LIMIT 10;


-- ------------------------------------------------------------------------------
-- 2. Category Performance and Revenue Market Share
-- Aggregates merchandise performance by product category with % revenue share
-- ------------------------------------------------------------------------------
WITH category_totals AS (
    SELECT
        p.category,
        CAST(SUM(foi.sub_total) AS DECIMAL(18, 2)) AS category_net_revenue,
        SUM(foi.quantity) AS category_units_sold,
        COUNT(DISTINCT foi.order_id) AS category_orders,
        ROUND(CAST(SUM(foi.sub_total) AS DOUBLE) / NULLIF(SUM(foi.quantity), 0), 2) AS revenue_per_unit
    FROM lakehouse.gold_sale_mart.fact_order_items foi
    INNER JOIN lakehouse.gold_sale_mart.dim_product p
        ON foi.product_key = p.product_id
    GROUP BY
        p.category
)
SELECT
    category,
    category_net_revenue,
    category_units_sold,
    category_orders,
    revenue_per_unit,
    ROUND(
        CAST(category_net_revenue AS DOUBLE) / NULLIF(SUM(CAST(category_net_revenue AS DOUBLE)) OVER (), 0) * 100,
        2
    ) AS category_revenue_share_pct
FROM category_totals
ORDER BY
    category_net_revenue DESC;


-- ------------------------------------------------------------------------------
-- 3. Federated Cross-Engine Join: Brand Origin Revenue & Unit Breakdown
-- Combines Delta Lake order items with MySQL OLTP brand master data in real-time
-- ------------------------------------------------------------------------------
SELECT
    COALESCE(b.brand_name, p.brand_name, 'Unknown Brand') AS brand_name,
    COALESCE(b.brand_origin, p.brand_origin, 'Unknown Origin') AS country_of_origin,
    SUM(foi.quantity) AS total_units_sold,
    CAST(SUM(foi.sub_total) AS DECIMAL(18, 2)) AS total_net_revenue,
    COUNT(DISTINCT p.product_id) AS distinct_skus_sold,
    ROUND(
        CAST(SUM(foi.sub_total) AS DOUBLE) / NULLIF(SUM(foi.quantity), 0),
        2
    ) AS avg_revenue_per_unit
FROM lakehouse.gold_sale_mart.fact_order_items foi
INNER JOIN lakehouse.gold_sale_mart.dim_product p
    ON foi.product_key = p.product_id
LEFT JOIN mysql.ecommerce_oltp.brands b
    ON p.brand_name = b.brand_name
GROUP BY
    COALESCE(b.brand_name, p.brand_name, 'Unknown Brand'),
    COALESCE(b.brand_origin, p.brand_origin, 'Unknown Origin')
ORDER BY
    total_net_revenue DESC;


-- ------------------------------------------------------------------------------
-- 4. Geographic Brand Origin Market Share Analysis
-- Evaluates domestic vs international merchandise sourcing contributions
-- ------------------------------------------------------------------------------
WITH origin_metrics AS (
    SELECT
        COALESCE(b.brand_origin, p.brand_origin, 'Unknown Origin') AS country_of_origin,
        CAST(SUM(foi.sub_total) AS DECIMAL(18, 2)) AS origin_net_revenue,
        SUM(foi.quantity) AS origin_units_sold,
        COUNT(DISTINCT foi.order_id) AS origin_orders
    FROM lakehouse.gold_sale_mart.fact_order_items foi
    INNER JOIN lakehouse.gold_sale_mart.dim_product p
        ON foi.product_key = p.product_id
    LEFT JOIN mysql.ecommerce_oltp.brands b
        ON p.brand_name = b.brand_name
    GROUP BY
        COALESCE(b.brand_origin, p.brand_origin, 'Unknown Origin')
)
SELECT
    country_of_origin,
    origin_net_revenue,
    origin_units_sold,
    origin_orders,
    ROUND(
        CAST(origin_net_revenue AS DOUBLE) / NULLIF(SUM(CAST(origin_net_revenue AS DOUBLE)) OVER (), 0) * 100,
        2
    ) AS origin_revenue_share_pct
FROM origin_metrics
ORDER BY
    origin_net_revenue DESC;
