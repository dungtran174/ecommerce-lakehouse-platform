{{
    config(
        alias='user_sessions',
        partition_by=['year', 'month', 'day']
    )
}}

with source as (
    select * from {{ ref('stg_clickstream_events') }}
),

deduplicated as (
    select
        session_id,
        user_id,
        event_timestamp,
        device_type,
        device_os,
        device_browser,
        city,
        country,
        latitude,
        longitude,
        duration_seconds,
        page_views,
        actions_count,
        has_purchase,
        revenue,
        user_segment,
        referrer,
        referrer_type,
        utm_source,
        utm_campaign,
        is_mobile,
        language,
        ab_test,
        row_number() over (
            partition by session_id
            order by event_timestamp desc
        ) as row_num
    from source
),

sanitized as (
    select
        session_id,
        user_id,
        event_timestamp as timestamp,
        device_type,
        device_os,
        device_browser as browser,
        city,
        country,
        latitude,
        longitude,
        duration_seconds,
        page_views,
        actions_count,
        has_purchase,
        revenue,
        user_segment,
        referrer,
        referrer_type,
        utm_source,
        utm_campaign,
        is_mobile,
        language,
        ab_test,
        year(event_timestamp) as year,
        month(event_timestamp) as month,
        day(event_timestamp) as day,
        current_timestamp() as _transformed_at
    from deduplicated
    where row_num = 1
        and session_id is not null
)

select * from sanitized
