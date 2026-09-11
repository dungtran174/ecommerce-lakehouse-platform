{{
    config(
        alias='products'
    )
}}

with source as (
    select * from {{ ref('stg_products') }}
),

deduplicated as (
    select
        product_id,
        product_name,
        product_description,
        price,
        category_id,
        brand_id,
        created_at,
        updated_at,
        row_number() over (
            partition by product_id
            order by updated_at desc, created_at desc
        ) as row_num
    from source
),

sanitized as (
    select
        product_id,
        trim(product_name) as product_name,
        trim(product_description) as product_description,
        cast(price as double) as price,
        category_id,
        trim(brand_id) as brand_id,
        created_at,
        updated_at,
        current_timestamp() as _transformed_at
    from deduplicated
    where row_num = 1
        and price > 0
)

select * from sanitized
