with source as (
    select * from {{ source('clickstream', 'clickstream_events') }}
),

renamed as (
    select
        cast(event_id as string) as event_id,
        cast(session_id as string) as session_id,
        cast(timestamp as timestamp) as event_timestamp,
        cast(timestamp as date) as event_date,
        cast(user_id as bigint) as user_id,
        cast(user_segment as string) as user_segment,

        -- Device Telemetry
        get_json_object(cast(device as string), '$.type') as device_type,
        get_json_object(cast(device as string), '$.os') as device_os,
        get_json_object(cast(device as string), '$.browser') as device_browser,
        get_json_object(cast(device as string), '$.version') as device_version,

        -- Geographic Coordinates
        get_json_object(cast(location as string), '$.city') as city,
        get_json_object(cast(location as string), '$.country') as country,
        cast(get_json_object(cast(location as string), '$.coordinates.lat') as double) as latitude,
        cast(get_json_object(cast(location as string), '$.coordinates.lon') as double) as longitude,

        -- Inbound Traffic & Attribution
        cast(referrer as string) as referrer,
        cast(referrer_type as string) as referrer_type,
        cast(source as string) as utm_source,
        cast(campaign as string) as utm_campaign,

        -- Session Engagement Metrics
        cast(
            get_json_object(cast(session_metrics as string), '$.duration_seconds') as int
        ) as duration_seconds,
        cast(
            get_json_object(cast(session_metrics as string), '$.page_views') as int
        ) as page_views,
        cast(
            get_json_object(cast(session_metrics as string), '$.actions_count') as int
        ) as actions_count,
        coalesce(
            cast(get_json_object(cast(session_metrics as string), '$.has_purchase') as boolean),
            false
        ) as has_purchase,
        coalesce(
            cast(get_json_object(cast(session_metrics as string), '$.revenue') as double),
            0.0
        ) as revenue,

        -- Device & Localization Properties
        coalesce(
            cast(get_json_object(cast(properties as string), '$.is_mobile') as boolean),
            get_json_object(cast(device as string), '$.type') = 'mobile'
        ) as is_mobile,
        get_json_object(cast(properties as string), '$.language') as language,
        get_json_object(cast(properties as string), '$.ab_test') as ab_test,

        -- Raw actions JSON array (preserved for unnesting in downstream silver model)
        cast(actions as string) as actions,

        -- Ingestion & Partitioning Metadata
        cast(coalesce(ingest_date, cast(timestamp as string)) as date) as ingest_date,
        current_timestamp() as _ingested_at
    from source
    {% if is_incremental() %}
        where cast(timestamp as timestamp) > (select max(event_timestamp) from {{ this }})
    {% endif %}
)

select * from renamed
