with products as (
    select * from {{ ref('silver_products') }}
),

categories as (
    select * from {{ ref('silver_categories') }}
),

brands as (
    select * from {{ ref('silver_brands') }}
),

joined as (
    select
        p.product_id,
        p.product_name,
        p.product_description,
        cast(p.price as decimal(10, 2)) as unit_price,
        coalesce(c.category_display_name, 'Uncategorized') as category,
        coalesce(b.brand_name, 'Generic') as brand_name,
        coalesce(b.brand_origin, 'Unknown') as brand_origin,
        current_timestamp() as _created_at
    from products as p
    left join categories as c
        on p.category_id = c.category_id
    left join brands as b
        on p.brand_id = b.brand_id
)

select * from joined
