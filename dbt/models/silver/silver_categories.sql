{{
    config(
        alias='category'
    )
}}

with source as (
    select * from {{ ref('stg_categories') }}
),

deduplicated as (
    select
        category_id,
        category_display_name,
        category_description,
        row_number() over (
            partition by category_id
            order by category_display_name
        ) as row_num
    from source
),

sanitized as (
    select
        category_id,
        trim(category_display_name) as category_display_name,
        trim(category_description) as category_description,
        current_timestamp() as _transformed_at
    from deduplicated
    where row_num = 1
        and category_id is not null
)

select * from sanitized
