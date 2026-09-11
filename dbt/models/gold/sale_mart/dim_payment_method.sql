with source as (
    select * from {{ ref('silver_payment_methods') }}
),

scd2 as (
    select
        payment_method_id,
        display_name,
        provider,
        type,
        cast('2025-01-01' as date) as effective_start_date,
        cast(null as date) as effective_end_date,
        true as is_current,
        current_timestamp() as _created_at
    from source
)

select * from scd2
