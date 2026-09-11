{{
    config(
        alias='order_items'
    )
}}

with source as (
    select * from {{ ref('stg_order_items') }}
),

deduplicated as (
    select
        order_item_id,
        order_id,
        product_id,
        quantity,
        price,
        discount,
        row_number() over (
            partition by order_item_id
            order by order_item_id
        ) as row_num
    from source
),

sanitized as (
    select
        order_item_id,
        order_id,
        product_id,
        quantity,
        cast(price as double) as price,
        cast(coalesce(discount, 0.0) as double) as discount,
        cast(
            greatest(quantity * price - coalesce(discount, 0.0), 0.0) as double
        ) as line_total_amount,
        current_timestamp() as _transformed_at
    from deduplicated
    where row_num = 1
        and order_item_id is not null
        and quantity > 0
        and price >= 0
)

select * from sanitized
