with date_spine as (
    select explode(
        sequence(
            to_date('2020-01-01'),
            to_date('2030-12-31'),
            interval 1 day
        )
    ) as calendar_date
),

calendar as (
    select
        cast(date_format(calendar_date, 'yyyyMMdd') as int) as date_key,
        calendar_date,
        year(calendar_date) as year,
        month(calendar_date) as month,
        date_format(calendar_date, 'MM-yyyy') as month_year,
        quarter(calendar_date) as quarter,
        concat('Q', quarter(calendar_date)) as quarter_name,
        concat('Q', quarter(calendar_date), '-', year(calendar_date)) as quarter_year,
        date_format(calendar_date, 'MMMM') as month_name,
        date_format(calendar_date, 'EEEE') as day_name,
        case
            when dayofweek(calendar_date) in (1, 7) then 1
            else 0
        end as is_weekend,
        case
            when dayofweek(calendar_date) in (1, 7) then 0
            else 1
        end as is_weekday,
        current_timestamp() as _created_at
    from date_spine
)

select * from calendar
