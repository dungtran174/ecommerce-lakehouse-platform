-- ==============================================================================
-- Modern E-Commerce Data Lakehouse Platform
-- dbt Singular Test: assert_positive_revenue
--
-- Ensures all monetary measures across orders and order items are strictly non-negative.
-- Returns any anomalous records where revenue, price, or sub_total is negative.
-- ==============================================================================

with invalid_orders as (
    select
        'fact_order' as model_name,
        order_id as record_id,
        sub_total,
        price
    from {{ ref('fact_order') }}
    where sub_total < 0
        or price < 0
        or discount_amt < 0
),

invalid_order_items as (
    select
        'fact_order_items' as model_name,
        order_item_id as record_id,
        sub_total,
        price
    from {{ ref('fact_order_items') }}
    where sub_total < 0
        or price < 0
        or discount_amt < 0
),

all_invalid as (
    select * from invalid_orders
    union all
    select * from invalid_order_items
)

select * from all_invalid
