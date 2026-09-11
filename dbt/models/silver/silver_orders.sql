{{
    config(
        alias='orders'
    )
}}

with source as (
    select * from {{ ref('stg_orders') }}
),

deduplicated as (
    select
        order_id,
        customer_id,
        order_date,
        total_amount,
        payment_method_id,
        created_at,
        updated_at,
        row_number() over (
            partition by order_id
            order by updated_at desc, created_at desc
        ) as row_num
    from source
),

sanitized as (
    select
        order_id,
        customer_id,
        cast(order_date as date) as order_date,
        cast(total_amount as double) as total_amount,
        payment_method_id,
        created_at,
        updated_at,
        current_timestamp() as _transformed_at
    from deduplicated
    where row_num = 1
        and order_id is not null
        and total_amount >= 0
)

select * from sanitized
