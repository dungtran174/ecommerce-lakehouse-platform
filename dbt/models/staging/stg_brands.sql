with source as (
    select * from {{ source('mysql_oltp', 'brands_snapshot') }}
),

renamed as (
    select
        trim(cast(brand_id as string)) as brand_id,
        trim(cast(brand_name as string)) as brand_name,
        trim(cast(brand_origin as string)) as brand_origin,
        current_timestamp() as _ingested_at
    from source
)

select * from renamed
