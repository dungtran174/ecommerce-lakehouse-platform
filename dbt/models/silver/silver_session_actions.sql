{{
    config(
        alias='session_actions',
        partition_by=['year', 'month', 'day']
    )
}}

with source as (
    select * from {{ ref('stg_clickstream_events') }}
),

parsed_actions as (
    select
        session_id,
        event_timestamp,
        explode(
            from_json(
                actions,
                concat(
                    'array<struct<type:string,time_offset:int,page:string,',
                    'search_term:string,product_id:bigint,product_name:string,',
                    'category:string,price:double,order_id:string>>'
                )
            )
        ) as act
    from source
    where actions is not null
),

flattened as (
    select
        session_id,
        cast(
            from_unixtime(
                unix_timestamp(event_timestamp) + coalesce(act.time_offset, 0)
            ) as timestamp
        ) as action_timestamp,
        trim(act.type) as action_type,
        act.product_id as product_id,
        trim(act.search_term) as search_term,
        trim(act.order_id) as order_id,
        case
            when act.type = 'purchase' then coalesce(cast(act.price as double), 0.0)
            else 0.0
        end as revenue,
        cast(act.price as double) as product_price,
        trim(act.category) as product_category,
        case when act.type = 'view' then 1 else 0 end as is_view,
        case when act.type = 'add_to_cart' then 1 else 0 end as is_add_to_cart,
        case when act.type = 'purchase' then 1 else 0 end as is_purchase,
        case when act.type = 'search' then 1 else 0 end as is_search,
        case when act.type = 'wishlist' then 1 else 0 end as is_wishlist,
        case when act.type = 'review' then 1 else 0 end as is_review,
        case when act.type = 'remove_from_cart' then 1 else 0 end as is_remove_from_cart,
        case when act.type = 'checkout_view' then 1 else 0 end as is_checkout_view,
        year(event_timestamp) as year,
        month(event_timestamp) as month,
        day(event_timestamp) as day
    from parsed_actions
),

final as (
    select
        concat(
            session_id,
            '-act-',
            cast(
                row_number() over (
                    partition by session_id
                    order by action_timestamp, action_type
                ) as string
            )
        ) as action_id,
        session_id,
        action_timestamp,
        action_type,
        product_id,
        search_term,
        order_id,
        revenue,
        product_price,
        product_category,
        is_view,
        is_add_to_cart,
        is_purchase,
        is_search,
        is_wishlist,
        is_review,
        is_remove_from_cart,
        is_checkout_view,
        year,
        month,
        day,
        current_timestamp() as _transformed_at
    from flattened
)

select * from final
