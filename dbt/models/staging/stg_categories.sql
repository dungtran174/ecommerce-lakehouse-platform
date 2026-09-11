with source as (
    select * from {{ source('mysql_oltp', 'category_snapshot') }}
),

renamed as (
    select
        cast(category_id as int) as category_id,
        trim(cast(category_display_name as string)) as category_display_name,
        trim(cast(category_description as string)) as category_description,
        current_timestamp() as _ingested_at
    from source
)

select * from renamed
