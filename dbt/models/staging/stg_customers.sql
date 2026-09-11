with source as (
    select * from {{ source('mysql_oltp', 'customers_snapshot') }}
),

renamed as (
    select
        cast(customer_id as int) as customer_id,
        trim(cast(first_name as string)) as first_name,
        trim(cast(last_name as string)) as last_name,
        lower(trim(cast(email as string))) as email,
        trim(cast(phone_number as string)) as phone_number,
        trim(cast(gender as string)) as gender,
        lower(trim(cast(tire as string))) as tire,
        trim(cast(address as string)) as address,
        cast(created_at as timestamp) as created_at,
        cast(updated_at as timestamp) as updated_at,
        current_timestamp() as _ingested_at
    from source
)

select * from renamed
