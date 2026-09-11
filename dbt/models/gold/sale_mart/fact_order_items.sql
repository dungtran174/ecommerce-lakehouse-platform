with order_items as (
    select * from {{ ref('silver_order_items') }}
),

orders as (
    select * from {{ ref('silver_orders') }}
),

joined as (
    select
        oi.order_item_id,
        oi.order_id,
        o.customer_id as customer_key,
        oi.product_id as product_key,
        o.payment_method_id as payment_method_key,
        cast(date_format(o.order_date, 'yyyyMMdd') as int) as order_date_key,
        cast(oi.quantity as int) as quantity,
        cast(oi.price as decimal(10, 2)) as price,
        cast(oi.discount as decimal(10, 2)) as discount_amt,
        cast(oi.line_total_amount as decimal(10, 2)) as sub_total,
        current_timestamp() as _created_at
    from order_items as oi
    inner join orders as o
        on oi.order_id = o.order_id
)

select * from joined
