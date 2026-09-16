-- ==============================================================================
-- Modern E-Commerce Data Lakehouse Platform
-- Metabase BI Dashboard: Regional E-Commerce Geographic Order Heatmap
-- Engine: Trino MPP Query Engine
-- Catalog / Schema: lakehouse.gold_sale_mart
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. Vietnam 63 Provinces Geographic Order Density & Revenue Heatmap
-- Aggregates customer geographic footprints for spatial density and market share
-- ------------------------------------------------------------------------------
SELECT
    COALESCE(c.address, 'Unknown Province') AS province,
    COUNT(DISTINCT f.order_id) AS total_orders,
    COUNT(DISTINCT c.customer_id) AS active_customers,
    SUM(f.quantity) AS total_units_sold,
    CAST(SUM(f.sub_total) AS DECIMAL(18, 2)) AS total_net_revenue,
    ROUND(CAST(SUM(f.sub_total) AS DOUBLE) / NULLIF(COUNT(DISTINCT f.order_id), 0), 2) AS average_order_value,
    ROUND(
        CAST(SUM(f.sub_total) AS DOUBLE) / NULLIF(SUM(SUM(f.sub_total)) OVER (), 0) * 100,
        2
    ) AS revenue_share_pct
FROM lakehouse.gold_sale_mart.fact_order f
INNER JOIN lakehouse.gold_sale_mart.dim_customer c
    ON f.customer_key = c.customer_id
GROUP BY
    COALESCE(c.address, 'Unknown Province')
ORDER BY
    total_net_revenue DESC;


-- ------------------------------------------------------------------------------
-- 2. Top 10 Metropolitan Purchasing Power Hubs
-- Highlights leading economic centers driving online retail consumption
-- ------------------------------------------------------------------------------
SELECT
    COALESCE(c.address, 'Unknown Province') AS province,
    CAST(SUM(f.sub_total) AS DECIMAL(18, 2)) AS total_net_revenue,
    COUNT(DISTINCT f.order_id) AS total_orders,
    COUNT(DISTINCT c.customer_id) AS total_customers,
    ROUND(CAST(SUM(f.sub_total) AS DOUBLE) / NULLIF(COUNT(DISTINCT f.order_id), 0), 2) AS aov
FROM lakehouse.gold_sale_mart.fact_order f
INNER JOIN lakehouse.gold_sale_mart.dim_customer c
    ON f.customer_key = c.customer_id
GROUP BY
    COALESCE(c.address, 'Unknown Province')
ORDER BY
    total_net_revenue DESC
LIMIT 10;


-- ------------------------------------------------------------------------------
-- 3. Macro-Regional Performance Breakdown (Northern, Central, Southern Vietnam)
-- Clusters 63 provinces into strategic logistics zones with share of market
-- ------------------------------------------------------------------------------
WITH regional_categorization AS (
    SELECT
        f.order_id,
        f.customer_key,
        f.sub_total,
        f.quantity,
        CASE
            WHEN c.address IN (
                'Hà Nội', 'Hải Phòng', 'Bắc Ninh', 'Quảng Ninh', 'Hải Dương',
                'Hưng Yên', 'Hà Nam', 'Nam Định', 'Ninh Bình', 'Thái Bình',
                'Vĩnh Phúc', 'Phú Thọ', 'Thái Nguyên', 'Bắc Giang', 'Tuyên Quang',
                'Hà Giang', 'Cao Bằng', 'Bắc Kạn', 'Lạng Sơn', 'Lào Cai',
                'Yên Bái', 'Hòa Bình', 'Sơn La', 'Điện Biên', 'Lai Châu'
            ) THEN 'Miền Bắc'
            WHEN c.address IN (
                'Đà Nẵng', 'Thừa Thiên Huế', 'Quảng Trị', 'Quảng Bình', 'Hà Tĩnh',
                'Nghệ An', 'Thanh Hóa', 'Quảng Nam', 'Quảng Ngãi', 'Bình Định',
                'Phú Yên', 'Khánh Hòa', 'Ninh Thuận', 'Bình Thuận', 'Kon Tum',
                'Gia Lai', 'Đắk Lắk', 'Đắk Nông', 'Lâm Đồng'
            ) THEN 'Miền Trung & Tây Nguyên'
            ELSE 'Miền Nam'
        END AS macro_region
    FROM lakehouse.gold_sale_mart.fact_order f
    INNER JOIN lakehouse.gold_sale_mart.dim_customer c
        ON f.customer_key = c.customer_id
)
SELECT
    macro_region,
    COUNT(DISTINCT order_id) AS total_orders,
    COUNT(DISTINCT customer_key) AS total_customers,
    SUM(quantity) AS units_sold,
    CAST(SUM(sub_total) AS DECIMAL(18, 2)) AS regional_net_revenue,
    ROUND(CAST(SUM(sub_total) AS DOUBLE) / NULLIF(COUNT(DISTINCT order_id), 0), 2) AS aov,
    ROUND(
        CAST(SUM(sub_total) AS DOUBLE) / NULLIF(SUM(SUM(sub_total)) OVER (), 0) * 100,
        2
    ) AS regional_revenue_share_pct
FROM regional_categorization
GROUP BY
    macro_region
ORDER BY
    regional_net_revenue DESC;


-- ------------------------------------------------------------------------------
-- 4. Customer Loyalty Tier Penetration by Region
-- Visualizes customer value segmentation across Vietnamese geographic zones
-- ------------------------------------------------------------------------------
WITH customer_tiers AS (
    SELECT
        CASE
            WHEN c.address IN (
                'Hà Nội', 'Hải Phòng', 'Bắc Ninh', 'Quảng Ninh', 'Hải Dương',
                'Hưng Yên', 'Hà Nam', 'Nam Định', 'Ninh Bình', 'Thái Bình',
                'Vĩnh Phúc', 'Phú Thọ', 'Thái Nguyên', 'Bắc Giang', 'Tuyên Quang',
                'Hà Giang', 'Cao Bằng', 'Bắc Kạn', 'Lạng Sơn', 'Lào Cai',
                'Yên Bái', 'Hòa Bình', 'Sơn La', 'Điện Biên', 'Lai Châu'
            ) THEN 'Miền Bắc'
            WHEN c.address IN (
                'Đà Nẵng', 'Thừa Thiên Huế', 'Quảng Trị', 'Quảng Bình', 'Hà Tĩnh',
                'Nghệ An', 'Thanh Hóa', 'Quảng Nam', 'Quảng Ngãi', 'Bình Định',
                'Phú Yên', 'Khánh Hòa', 'Ninh Thuận', 'Bình Thuận', 'Kon Tum',
                'Gia Lai', 'Đắk Lắk', 'Đắk Nông', 'Lâm Đồng'
            ) THEN 'Miền Trung & Tây Nguyên'
            ELSE 'Miền Nam'
        END AS macro_region,
        COALESCE(c.tire, 'Standard') AS loyalty_tier,
        f.order_id,
        f.sub_total
    FROM lakehouse.gold_sale_mart.fact_order f
    INNER JOIN lakehouse.gold_sale_mart.dim_customer c
        ON f.customer_key = c.customer_id
)
SELECT
    macro_region,
    loyalty_tier,
    COUNT(DISTINCT order_id) AS tier_orders,
    CAST(SUM(sub_total) AS DECIMAL(18, 2)) AS tier_revenue,
    ROUND(CAST(SUM(sub_total) AS DOUBLE) / NULLIF(COUNT(DISTINCT order_id), 0), 2) AS tier_aov
FROM customer_tiers
GROUP BY
    macro_region,
    loyalty_tier
ORDER BY
    macro_region ASC,
    tier_revenue DESC;


-- ------------------------------------------------------------------------------
-- 5. Regional Fulfillment Lead-Time & Logistics Service Level Simulation
-- Correlates regional demand density with delivery lead-time SLA metrics
-- ------------------------------------------------------------------------------
SELECT
    COALESCE(c.address, 'Unknown Province') AS province,
    COUNT(DISTINCT f.order_id) AS total_orders,
    CAST(SUM(f.sub_total) AS DECIMAL(18, 2)) AS net_revenue,
    CASE
        WHEN c.address IN ('Hà Nội', 'TP Hồ Chí Minh', 'Đà Nẵng') THEN 1.2
        WHEN c.address IN ('Hải Phòng', 'Bình Dương', 'Đồng Nai', 'Cần Thơ', 'Bắc Ninh') THEN 1.8
        WHEN c.address IN (
            'Lai Châu', 'Điện Biên', 'Hà Giang', 'Cao Bằng', 'Bắc Kạn',
            'Kon Tum', 'Đắk Nông'
        ) THEN 3.9
        ELSE 2.4
    END AS estimated_delivery_days,
    CASE
        WHEN c.address IN ('Hà Nội', 'TP Hồ Chí Minh', 'Đà Nẵng') THEN 'Tier 1 - Same/Next Day'
        WHEN c.address IN ('Hải Phòng', 'Bình Dương', 'Đồng Nai', 'Cần Thơ', 'Bắc Ninh') THEN 'Tier 2 - Express (48h)'
        WHEN c.address IN (
            'Lai Châu', 'Điện Biên', 'Hà Giang', 'Cao Bằng', 'Bắc Kạn',
            'Kon Tum', 'Đắk Nông'
        ) THEN 'Tier 4 - Remote (>72h)'
        ELSE 'Tier 3 - Standard (72h)'
    END AS delivery_service_tier
FROM lakehouse.gold_sale_mart.fact_order f
INNER JOIN lakehouse.gold_sale_mart.dim_customer c
    ON f.customer_key = c.customer_id
GROUP BY
    COALESCE(c.address, 'Unknown Province')
ORDER BY
    total_orders DESC;
