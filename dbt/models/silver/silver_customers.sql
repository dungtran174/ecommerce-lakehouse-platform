{{
    config(
        alias='customer'
    )
}}

with source as (
    select * from {{ ref('stg_customers') }}
),

deduplicated as (
    select
        customer_id,
        first_name,
        last_name,
        email,
        phone_number,
        gender,
        tire,
        address,
        created_at,
        updated_at,
        row_number() over (
            partition by customer_id
            order by updated_at desc, created_at desc
        ) as row_num
    from source
),

sanitized as (
    select
        customer_id,
        first_name,
        last_name,

        -- PII Sanitization & Normalization
        lower(email) as email,
        case
            when phone_number is not null
                and length(regexp_replace(phone_number, '[^0-9]', '')) >= 9
                then regexp_replace(phone_number, '[^0-9]', '')
        end as phone_number,

        -- Standardized Gender Classification
        case
            when lower(gender) in ('nam', 'male', 'm') then 'Nam'
            when lower(gender) in ('nu', 'female', 'f') then 'Nu'
            else 'Other'
        end as gender,

        -- Standardized Loyalty Tier
        case
            when lower(tire) in ('bronze', 'silver', 'gold', 'platinum') then lower(tire)
            else 'bronze'
        end as tire,

        address,
        created_at,
        updated_at,
        current_timestamp() as _transformed_at
    from deduplicated
    where row_num = 1
)

select * from sanitized
