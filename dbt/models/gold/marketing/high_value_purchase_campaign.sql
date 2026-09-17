{{
    config(
        alias='high_value_purchase_campaign',
        materialized='incremental',
        file_format='delta',
        incremental_strategy='merge',
        unique_key=['customer_id', 'campaign_date']
    )
}}

with ml_features as (
    select * from {{ ref('ml_user_behavior_3d_agg_feature') }}
),

customers as (
    select * from {{ ref('silver_customers') }}
),

/*
    Rule-based and calibrated campaign propensity scoring aligning with
    PySpark MLlib Logistic Regression daily batch inference.
    Computes purchase probability from 12 rolling behavioral indicators.
*/
scored_leads as (
    select
        f.user_id as customer_id,
        f.prediction_date as campaign_date,
        round(
            1.0 / (
                1.0 + exp(
                    -(
                        -1.8
                        + 0.35 * coalesce(f.sessions_3d, 0)
                        + 0.0002 * coalesce(f.total_duration_3d, 0)
                        + 0.15 * coalesce(f.total_page_views_3d, 0)
                        + 0.000002 * coalesce(f.total_revenue_3d, 0.0)
                        + 0.45 * coalesce(f.add_to_cart_count_3d, 0)
                        + 0.60 * coalesce(f.checkout_view_count_3d, 0)
                        + 0.80 * coalesce(f.cart_conversion_rate_3d, 0.0)
                    )
                )
            ),
            4
        ) as purchase_probability
    from ml_features as f
    {% if is_incremental() %}
    where f.prediction_date >= (select coalesce(max(campaign_date), '1970-01-01') from {{ this }})
    {% endif %}
),

segmented as (
    select
        s.customer_id,
        s.campaign_date,
        s.purchase_probability,
        case
            when s.purchase_probability >= 0.70 then 'Hot Lead'
            when s.purchase_probability >= 0.40 then 'Medium Intent'
            else 'Low Intent'
        end as customer_segment,
        case
            when s.purchase_probability >= 0.70 then 'Send Premium Offer SMS'
            when s.purchase_probability >= 0.40 then 'Personalized Email Recommendation'
            else 'Retargeting Display Ad'
        end as campaign_action,
        case
            when s.purchase_probability >= 0.70 then 'SMS_AND_PUSH'
            when s.purchase_probability >= 0.40 then 'EMAIL'
            else 'DISPLAY_ADS'
        end as campaign_channel
    from scored_leads as s
),

final as (
    select
        sg.customer_id,
        sg.campaign_date,
        sg.purchase_probability,
        sg.customer_segment,
        sg.campaign_action,
        sg.campaign_channel,
        coalesce(c.first_name, 'Unknown') as first_name,
        coalesce(c.last_name, 'Customer') as last_name,
        c.email,
        c.phone_number as phone,
        current_timestamp() as predicted_at,
        current_timestamp() as created_at,
        cast(year(sg.campaign_date) as int) as year,
        cast(month(sg.campaign_date) as int) as month,
        cast(day(sg.campaign_date) as int) as day
    from segmented as sg
    left join customers as c
        on sg.customer_id = c.customer_id
)

select * from final
