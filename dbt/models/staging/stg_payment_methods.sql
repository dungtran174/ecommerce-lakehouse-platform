with source as (
    select * from {{ source('mysql_oltp', 'payment_method_snapshot') }}
),

renamed as (
    select
        cast(payment_method_id as int) as payment_method_id,
        trim(cast(display_name as string)) as display_name,
        trim(cast(type as string)) as type,
        trim(cast(provider as string)) as provider,
        current_timestamp() as _ingested_at
    from source
)

select * from renamed
