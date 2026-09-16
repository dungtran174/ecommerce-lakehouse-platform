-- ==============================================================================
-- Modern E-Commerce Data Lakehouse Platform
-- Metabase BI Dashboard: Executive Sales Performance & Revenue Trend
-- Engine: Trino MPP Query Engine
-- Catalog / Schema: lakehouse.gold_sale_mart
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. Executive High-Level KPI Summary Card
-- Computes lifetime/period totals: Gross Revenue, Net Revenue, Discounts,
-- Order Count, Units Sold, Average Order Value (AOV), and Units Per Transaction (UPT)
-- ------------------------------------------------------------------------------
SELECT
    CAST(SUM(f.price) AS DECIMAL(18, 2)) AS gross_revenue,
    CAST(SUM(f.discount_amt) AS DECIMAL(18, 2)) AS total_discount,
    CAST(SUM(f.sub_total) AS DECIMAL(18, 2)) AS net_revenue,
    ROUND(CAST(SUM(f.discount_amt) AS DOUBLE) / NULLIF(SUM(f.price), 0) * 100, 2) AS discount_rate_pct,
    COUNT(DISTINCT f.order_id) AS total_orders,
    SUM(f.quantity) AS total_units_sold,
    ROUND(CAST(SUM(f.sub_total) AS DOUBLE) / NULLIF(COUNT(DISTINCT f.order_id), 0), 2) AS average_order_value,
    ROUND(CAST(SUM(f.quantity) AS DOUBLE) / NULLIF(COUNT(DISTINCT f.order_id), 0), 2) AS units_per_transaction
FROM lakehouse.gold_sale_mart.fact_order f
INNER JOIN lakehouse.gold_sale_mart.dim_date d
    ON f.date_key = d.date_key;


-- ------------------------------------------------------------------------------
-- 2. Monthly Revenue Trend with Month-over-Month (MoM) Growth Analysis
-- Analyzes sales momentum, seasonal patterns, and MoM expansion percentages
-- ------------------------------------------------------------------------------
WITH monthly_metrics AS (
    SELECT
        d.year,
        d.month,
        d.month_year,
        d.month_name,
        CAST(SUM(f.sub_total) AS DECIMAL(18, 2)) AS net_revenue,
        COUNT(DISTINCT f.order_id) AS order_count,
        SUM(f.quantity) AS units_sold,
        ROUND(CAST(SUM(f.sub_total) AS DOUBLE) / NULLIF(COUNT(DISTINCT f.order_id), 0), 2) AS aov
    FROM lakehouse.gold_sale_mart.fact_order f
    INNER JOIN lakehouse.gold_sale_mart.dim_date d
        ON f.date_key = d.date_key
    GROUP BY
        d.year,
        d.month,
        d.month_year,
        d.month_name
)
SELECT
    year,
    month,
    month_year,
    month_name,
    net_revenue,
    order_count,
    units_sold,
    aov,
    LAG(net_revenue) OVER (ORDER BY year, month) AS prev_month_revenue,
    ROUND(
        (CAST(net_revenue AS DOUBLE) - LAG(CAST(net_revenue AS DOUBLE)) OVER (ORDER BY year, month))
        / NULLIF(LAG(CAST(net_revenue AS DOUBLE)) OVER (ORDER BY year, month), 0) * 100,
        2
    ) AS mom_revenue_growth_pct,
    ROUND(
        (CAST(order_count AS DOUBLE) - LAG(CAST(order_count AS DOUBLE)) OVER (ORDER BY year, month))
        / NULLIF(LAG(CAST(order_count AS DOUBLE)) OVER (ORDER BY year, month), 0) * 100,
        2
    ) AS mom_order_growth_pct
FROM monthly_metrics
ORDER BY
    year ASC,
    month ASC;


-- ------------------------------------------------------------------------------
-- 3. Quarterly Sales Performance & Year-over-Year (YoY) Growth
-- Strategic quarterly benchmarks evaluating year-over-year expansion rate
-- ------------------------------------------------------------------------------
WITH quarterly_metrics AS (
    SELECT
        d.year,
        d.quarter,
        d.quarter_name,
        d.quarter_year,
        CAST(SUM(f.sub_total) AS DECIMAL(18, 2)) AS net_revenue,
        COUNT(DISTINCT f.order_id) AS order_count,
        SUM(f.quantity) AS units_sold,
        ROUND(CAST(SUM(f.sub_total) AS DOUBLE) / NULLIF(COUNT(DISTINCT f.order_id), 0), 2) AS aov
    FROM lakehouse.gold_sale_mart.fact_order f
    INNER JOIN lakehouse.gold_sale_mart.dim_date d
        ON f.date_key = d.date_key
    GROUP BY
        d.year,
        d.quarter,
        d.quarter_name,
        d.quarter_year
)
SELECT
    year,
    quarter,
    quarter_name,
    quarter_year,
    net_revenue,
    order_count,
    units_sold,
    aov,
    LAG(net_revenue, 4) OVER (ORDER BY year, quarter) AS prev_year_same_quarter_revenue,
    ROUND(
        (CAST(net_revenue AS DOUBLE) - LAG(CAST(net_revenue AS DOUBLE), 4) OVER (ORDER BY year, quarter))
        / NULLIF(LAG(CAST(net_revenue AS DOUBLE), 4) OVER (ORDER BY year, quarter), 0) * 100,
        2
    ) AS yoy_revenue_growth_pct
FROM quarterly_metrics
ORDER BY
    year ASC,
    quarter ASC;


-- ------------------------------------------------------------------------------
-- 4. Daily Sales Run-Rate & 7-Day Moving Average Smoothed Trend
-- Filters out day-of-week noise to capture true velocity trajectory
-- ------------------------------------------------------------------------------
WITH daily_metrics AS (
    SELECT
        d.calendar_date,
        CAST(SUM(f.sub_total) AS DECIMAL(18, 2)) AS daily_net_revenue,
        COUNT(DISTINCT f.order_id) AS daily_orders,
        SUM(f.quantity) AS daily_units
    FROM lakehouse.gold_sale_mart.fact_order f
    INNER JOIN lakehouse.gold_sale_mart.dim_date d
        ON f.date_key = d.date_key
    GROUP BY
        d.calendar_date
)
SELECT
    calendar_date,
    daily_net_revenue,
    daily_orders,
    daily_units,
    ROUND(
        AVG(CAST(daily_net_revenue AS DOUBLE)) OVER (
            ORDER BY calendar_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ),
        2
    ) AS moving_avg_7d_net_revenue,
    ROUND(
        AVG(CAST(daily_orders AS DOUBLE)) OVER (
            ORDER BY calendar_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ),
        2
    ) AS moving_avg_7d_orders
FROM daily_metrics
ORDER BY
    calendar_date ASC;


-- ------------------------------------------------------------------------------
-- 5. Day-of-Week Customer Shopping Behavior Profile
-- Visualizes revenue distribution, order frequency, and weekend vs weekday habits
-- ------------------------------------------------------------------------------
WITH dow_metrics AS (
    SELECT
        d.day_name,
        d.is_weekend,
        d.is_weekday,
        CAST(SUM(f.sub_total) AS DECIMAL(18, 2)) AS net_revenue,
        COUNT(DISTINCT f.order_id) AS order_count,
        SUM(f.quantity) AS units_sold,
        ROUND(CAST(SUM(f.sub_total) AS DOUBLE) / NULLIF(COUNT(DISTINCT f.order_id), 0), 2) AS aov
    FROM lakehouse.gold_sale_mart.fact_order f
    INNER JOIN lakehouse.gold_sale_mart.dim_date d
        ON f.date_key = d.date_key
    GROUP BY
        d.day_name,
        d.is_weekend,
        d.is_weekday
)
SELECT
    day_name,
    CASE WHEN is_weekend = 1 THEN 'Weekend' ELSE 'Weekday' END AS day_type,
    net_revenue,
    order_count,
    units_sold,
    aov,
    ROUND(
        CAST(net_revenue AS DOUBLE) / NULLIF(SUM(CAST(net_revenue AS DOUBLE)) OVER (), 0) * 100,
        2
    ) AS revenue_share_pct
FROM dow_metrics
ORDER BY
    net_revenue DESC;
