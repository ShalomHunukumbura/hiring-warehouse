-- One row per day, from the earliest posting date to the newest extract.
with bounds as (
    select
        (select min(posted_on) from {{ ref('int_job_lifecycle') }}) as first_day,
        (select max(extract_date) from {{ ref('stg_unlisted__present') }}) as last_day
),

days as (
    select cast(unnest(generate_series(first_day, last_day, interval 1 day)) as date) as date_day
    from bounds
)

select
    date_day,
    cast(date_trunc('week', date_day) as date)  as week_start,
    cast(date_trunc('month', date_day) as date) as month_start,
    year(date_day)                              as year,
    isodow(date_day)                            as iso_day_of_week,
    dayname(date_day)                           as day_name,
    isodow(date_day) in (6, 7)                  as is_weekend
from days
