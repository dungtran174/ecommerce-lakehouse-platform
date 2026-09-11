{{
    config(
        alias='payment_method'
    )
}}

with source as (
    select * from {{ ref('stg_payment_methods') }}
),

deduplicated as (
    select
        payment_method_id,
        display_name,
        type,
        provider,
        row_number() over (
            partition by payment_method_id
            order by display_name
        ) as row_num
    from source
),

sanitized as (
    select
        payment_method_id,
        trim(display_name) as display_name,
        trim(type) as type,
        trim(provider) as provider,
        current_timestamp() as _transformed_at
    from deduplicated
    where row_num = 1
        and payment_method_id is not null
)

select * from sanitized
