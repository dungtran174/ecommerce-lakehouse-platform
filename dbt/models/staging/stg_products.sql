with source as (
    select * from {{ source('mysql_oltp', 'products_snapshot') }}
),

renamed as (
    select
        cast(product_id as int) as product_id,
        trim(cast(product_name as string)) as product_name,
        trim(cast(product_description as string)) as product_description,
        cast(price as double) as price,
        cast(category_id as int) as category_id,
        trim(cast(brand_id as string)) as brand_id,
        cast(created_at as timestamp) as created_at,
        cast(updated_at as timestamp) as updated_at,
        current_timestamp() as _ingested_at
    from source
)

select * from renamed
