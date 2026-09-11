with source as (
    select * from {{ source('mysql_oltp', 'orders_snapshot') }}
),

renamed as (
    select
        cast(order_id as int) as order_id,
        cast(customer_id as int) as customer_id,
        cast(order_date as timestamp) as order_timestamp,
        cast(order_date as date) as order_date,
        cast(total_amount as double) as total_amount,
        cast(payment_method_id as int) as payment_method_id,
        cast(created_at as timestamp) as created_at,
        cast(updated_at as timestamp) as updated_at,
        current_timestamp() as _ingested_at
    from source
    {% if is_incremental() %}
        where updated_at > (select max(updated_at) from {{ this }})
    {% endif %}
)

select * from renamed
