with source as (
    select * from {{ ref('silver_customers') }}
)

select
    customer_id,
    first_name,
    last_name,
    gender,
    tire,
    address,
    current_timestamp() as _created_at
from source
