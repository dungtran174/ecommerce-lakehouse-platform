{{
    config(
        alias='user_behavior_3d_agg_feature'
    )
}}

with sessions as (
    select * from {{ ref('silver_user_sessions') }}
),

actions as (
    select * from {{ ref('silver_session_actions') }}
),

daily_sessions as (
    select
        user_id,
        cast(timestamp as date) as activity_date,
        count(distinct session_id) as daily_sessions,
        sum(duration_seconds) as daily_duration,
        sum(page_views) as daily_page_views,
        sum(actions_count) as daily_actions,
        sum(case when has_purchase = 1 then 1 else 0 end) as daily_purchase_sessions,
        sum(revenue) as daily_revenue
    from sessions
    where user_id is not null
    group by user_id, cast(timestamp as date)
),

daily_actions as (
    select
        s.user_id,
        cast(a.action_timestamp as date) as activity_date,
        sum(a.is_view) as daily_views,
        sum(a.is_add_to_cart) as daily_add_to_carts,
        sum(a.is_purchase) as daily_purchases,
        sum(a.is_search) as daily_searches,
        sum(a.is_wishlist) as daily_wishlists,
        sum(a.is_checkout_view) as daily_checkout_views,
        count(distinct a.product_id) as daily_distinct_products,
        avg(a.product_price) as daily_avg_product_price
    from actions as a
    inner join sessions as s
        on a.session_id = s.session_id
    where s.user_id is not null
    group by s.user_id, cast(a.action_timestamp as date)
),

daily_activity as (
    select
        coalesce(s.user_id, a.user_id) as user_id,
        coalesce(s.activity_date, a.activity_date) as activity_date,
        coalesce(s.daily_sessions, 0) as sessions,
        coalesce(s.daily_duration, 0) as duration,
        coalesce(s.daily_page_views, 0) as page_views,
        coalesce(s.daily_actions, 0) as actions,
        coalesce(s.daily_purchase_sessions, 0) as purchase_sessions,
        coalesce(s.daily_revenue, 0.0) as revenue,
        coalesce(a.daily_views, 0) as view_count,
        coalesce(a.daily_add_to_carts, 0) as add_to_cart_count,
        coalesce(a.daily_purchases, 0) as purchase_count,
        coalesce(a.daily_searches, 0) as search_count,
        coalesce(a.daily_wishlists, 0) as wishlist_count,
        coalesce(a.daily_checkout_views, 0) as checkout_view_count,
        coalesce(a.daily_distinct_products, 0) as distinct_products,
        coalesce(a.daily_avg_product_price, 0.0) as avg_product_price
    from daily_sessions as s
    full outer join daily_actions as a
        on s.user_id = a.user_id
        and s.activity_date = a.activity_date
),

prediction_anchor as (
    select distinct
        user_id,
        activity_date as prediction_date,
        case
            when purchase_sessions > 0 or purchase_count > 0 then 1
            else 0
        end as label_purchase_tomorrow
    from daily_activity
),

rolling_features as (
    select
        p.user_id,
        p.prediction_date,
        p.label_purchase_tomorrow,
        cast(coalesce(sum(h.sessions), 0) as bigint) as sessions_3d,
        cast(coalesce(sum(h.duration), 0) as bigint) as total_duration_3d,
        cast(coalesce(sum(h.page_views), 0) as bigint) as total_page_views_3d,
        cast(coalesce(sum(h.actions), 0) as bigint) as total_actions_3d,
        cast(coalesce(sum(h.purchase_sessions), 0) as bigint) as purchase_sessions_3d,
        cast(coalesce(sum(h.revenue), 0.0) as double) as total_revenue_3d,
        cast(coalesce(sum(h.view_count), 0) as bigint) as view_count_3d,
        cast(coalesce(sum(h.add_to_cart_count), 0) as bigint) as add_to_cart_count_3d,
        cast(coalesce(sum(h.purchase_count), 0) as bigint) as purchase_count_3d,
        cast(coalesce(sum(h.search_count), 0) as bigint) as search_count_3d,
        cast(coalesce(sum(h.wishlist_count), 0) as bigint) as wishlist_count_3d,
        cast(coalesce(sum(h.checkout_view_count), 0) as bigint) as checkout_view_count_3d,
        cast(coalesce(max(h.distinct_products), 0) as bigint) as distinct_products_3d,
        cast(coalesce(avg(h.avg_product_price), 0.0) as double) as avg_product_price_3d
    from prediction_anchor as p
    left join daily_activity as h
        on p.user_id = h.user_id
        and h.activity_date >= date_sub(p.prediction_date, 3)
        and p.prediction_date > h.activity_date
    group by
        p.user_id,
        p.prediction_date,
        p.label_purchase_tomorrow
),

final as (
    select
        user_id,
        prediction_date,
        label_purchase_tomorrow,
        sessions_3d,
        total_duration_3d,
        case
            when sessions_3d > 0 then round(total_duration_3d / sessions_3d, 2)
            else 0.0
        end as avg_session_duration_3d,
        total_page_views_3d,
        total_actions_3d,
        purchase_sessions_3d,
        total_revenue_3d,
        view_count_3d,
        add_to_cart_count_3d,
        purchase_count_3d,
        search_count_3d,
        wishlist_count_3d,
        checkout_view_count_3d,
        distinct_products_3d,
        avg_product_price_3d,
        case
            when add_to_cart_count_3d > 0 then round(purchase_count_3d / add_to_cart_count_3d, 4)
            else 0.0
        end as cart_conversion_rate_3d,
        case
            when total_actions_3d > 0 then round(purchase_count_3d / total_actions_3d, 4)
            else 0.0
        end as purchase_conversion_rate_3d,
        case
            when sessions_3d > 0 then round(total_actions_3d / sessions_3d, 4)
            else 0.0
        end as actions_per_session_3d,
        case
            when sessions_3d > 0 then round(purchase_sessions_3d / sessions_3d, 4)
            else 0.0
        end as purchase_session_rate_3d,
        current_timestamp() as _created_at
    from rolling_features
)

select * from final
