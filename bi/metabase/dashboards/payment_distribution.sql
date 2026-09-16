-- ==============================================================================
-- Modern E-Commerce Data Lakehouse Platform
-- Metabase BI Dashboard: Payment Method & Channel Distribution
-- Engine: Trino MPP Query Engine
-- Catalog / Schema: lakehouse.gold_sale_mart
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. Payment Method Market Share and Volume Analysis
-- Evaluates transaction volume and monetary share across all payment channels
-- ------------------------------------------------------------------------------
WITH payment_summary AS (
    SELECT
        pm.payment_method_id,
        pm.display_name,
        pm.type AS payment_type,
        pm.provider,
        COUNT(DISTINCT f.order_id) AS total_orders,
        CAST(SUM(f.sub_total) AS DECIMAL(18, 2)) AS total_net_revenue,
        ROUND(CAST(SUM(f.sub_total) AS DOUBLE) / NULLIF(COUNT(DISTINCT f.order_id), 0), 2) AS aov
    FROM lakehouse.gold_sale_mart.fact_order f
    INNER JOIN lakehouse.gold_sale_mart.dim_payment_method pm
        ON f.payment_method_key = pm.payment_method_id
    GROUP BY
        pm.payment_method_id,
        pm.display_name,
        pm.type,
        pm.provider
)
SELECT
    payment_method_id,
    display_name,
    payment_type,
    provider,
    total_orders,
    total_net_revenue,
    aov,
    ROUND(
        CAST(total_orders AS DOUBLE) / NULLIF(SUM(CAST(total_orders AS DOUBLE)) OVER (), 0) * 100,
        2
    ) AS transaction_volume_share_pct,
    ROUND(
        CAST(total_net_revenue AS DOUBLE) / NULLIF(SUM(CAST(total_net_revenue AS DOUBLE)) OVER (), 0) * 100,
        2
    ) AS revenue_market_share_pct
FROM payment_summary
ORDER BY
    total_net_revenue DESC;


-- ------------------------------------------------------------------------------
-- 2. Payment Channel Type Breakdown (E-Wallet vs COD vs Cards vs Banking)
-- High-level split of consumer payment preferences and digital adoption
-- ------------------------------------------------------------------------------
WITH channel_types AS (
    SELECT
        pm.type AS payment_channel_type,
        COUNT(DISTINCT f.order_id) AS total_orders,
        CAST(SUM(f.sub_total) AS DECIMAL(18, 2)) AS total_net_revenue,
        ROUND(CAST(SUM(f.sub_total) AS DOUBLE) / NULLIF(COUNT(DISTINCT f.order_id), 0), 2) AS aov
    FROM lakehouse.gold_sale_mart.fact_order f
    INNER JOIN lakehouse.gold_sale_mart.dim_payment_method pm
        ON f.payment_method_key = pm.payment_method_id
    GROUP BY
        pm.type
)
SELECT
    payment_channel_type,
    total_orders,
    total_net_revenue,
    aov,
    ROUND(
        CAST(total_net_revenue AS DOUBLE) / NULLIF(SUM(CAST(total_net_revenue AS DOUBLE)) OVER (), 0) * 100,
        2
    ) AS revenue_share_pct
FROM channel_types
ORDER BY
    total_net_revenue DESC;


-- ------------------------------------------------------------------------------
-- 3. Monthly Payment Channel Adoption and Migration Trend
-- Tracks the secular shift from cash-on-delivery (COD) toward cashless digital wallets
-- ------------------------------------------------------------------------------
WITH monthly_payments AS (
    SELECT
        d.year,
        d.month,
        d.month_year,
        pm.display_name AS payment_method,
        pm.type AS payment_type,
        COUNT(DISTINCT f.order_id) AS monthly_orders,
        CAST(SUM(f.sub_total) AS DECIMAL(18, 2)) AS monthly_revenue
    FROM lakehouse.gold_sale_mart.fact_order f
    INNER JOIN lakehouse.gold_sale_mart.dim_payment_method pm
        ON f.payment_method_key = pm.payment_method_id
    INNER JOIN lakehouse.gold_sale_mart.dim_date d
        ON f.date_key = d.date_key
    GROUP BY
        d.year,
        d.month,
        d.month_year,
        pm.display_name,
        pm.type
)
SELECT
    year,
    month,
    month_year,
    payment_method,
    payment_type,
    monthly_orders,
    monthly_revenue,
    ROUND(
        CAST(monthly_revenue AS DOUBLE) / NULLIF(SUM(CAST(monthly_revenue AS DOUBLE)) OVER (PARTITION BY year, month), 0) * 100,
        2
    ) AS monthly_revenue_share_pct
FROM monthly_payments
ORDER BY
    year ASC,
    month ASC,
    monthly_revenue DESC;
