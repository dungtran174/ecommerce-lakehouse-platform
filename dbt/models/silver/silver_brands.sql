{{
    config(
        alias='brands'
    )
}}

with source as (
    select * from {{ ref('stg_brands') }}
),

deduplicated as (
    select
        brand_id,
        brand_name,
        brand_origin,
        row_number() over (
            partition by brand_id
            order by brand_name
        ) as row_num
    from source
),

sanitized as (
    select
        trim(brand_id) as brand_id,
        trim(brand_name) as brand_name,
        coalesce(trim(brand_origin), 'Unknown') as brand_origin,
        current_timestamp() as _transformed_at
    from deduplicated
    where row_num = 1
        and brand_id is not null
        and length(trim(brand_id)) > 0
)

select * from sanitized
