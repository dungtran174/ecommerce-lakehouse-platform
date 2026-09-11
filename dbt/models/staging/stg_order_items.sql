with source as (
    select * from {{ source('mysql_oltp', 'order_items_snapshot') }}
),

renamed as (
    select
        cast(order_item_id as int) as order_item_id,
        cast(order_id as int) as order_id,
        cast(product_id as int) as product_id,
        cast(quantity as int) as quantity,
        cast(price as double) as price,
        coalesce(cast(discount as double), 0.0) as discount,
        cast(quantity * price - coalesce(discount, 0.0) as double) as line_total_amount,
        current_timestamp() as _ingested_at
    from source
    {% if is_incremental() %}
        where order_item_id > (select max(order_item_id) from {{ this }})
    {% endif %}
)

select * from renamed
