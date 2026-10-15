-- New postings per week by workplace (on-site, hybrid, remote) and how far remote reaches.
select
    d.week_start,
    l.workplace,
    coalesce(l.remote_reach, '') as remote_reach,
    count(*) as postings
from {{ ref('fact_job_posting') }} as f
inner join {{ ref('dim_date') }} as d on d.date_day = f.posted_on
inner join {{ ref('dim_location') }} as l using (location_key)
group by all
