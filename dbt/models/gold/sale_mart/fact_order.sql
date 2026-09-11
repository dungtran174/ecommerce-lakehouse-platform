with orders as (
    select * from {{ ref('silver_orders') }}
),

order_items as (
    select * from {{ ref('silver_order_items') }}
),

items_aggregated as (
    select
        order_id,
        sum(quantity) as total_quantity,
        sum(quantity * price) as gross_price,
        sum(discount) as total_discount,
        sum(line_total_amount) as total_sub_total
    from order_items
    group by order_id
),

final as (
    select
        o.order_id,
        o.customer_id as customer_key,
        o.payment_method_id as payment_method_key,
        cast(date_format(o.order_date, 'yyyyMMdd') as int) as date_key,
        cast(coalesce(i.total_quantity, 0) as int) as quantity,
        cast(coalesce(i.gross_price, o.total_amount) as decimal(10, 2)) as price,
        cast(coalesce(i.total_discount, 0.0) as decimal(10, 2)) as discount_amt,
        cast(coalesce(i.total_sub_total, o.total_amount) as decimal(10, 2)) as sub_total,
        current_timestamp() as _created_at
    from orders as o
    left join items_aggregated as i
        on o.order_id = i.order_id
)

select * from final
