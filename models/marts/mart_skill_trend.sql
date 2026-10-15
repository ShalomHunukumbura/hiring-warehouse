{#
  One row per job family and skill: the skill's share of the family's new postings over
  the last 28 days, the 28 days before that, and the change. "All jobs" covers every
  family. Until the warehouse holds 56 days, the earlier window is empty and the change
  is null.
#}
with newest as (
    select max(extract_date) as day
    from {{ ref('stg_unlisted__present') }}
),

windowed as (
    select
        f.job_id,
        f.job_family,
        case
            when f.posted_on > newest.day - 28 then 'recent'
            when f.posted_on > newest.day - 56 then 'previous'
        end as period
    from {{ ref('fact_job_posting') }} as f
    cross join newest
),

postings as (
    select job_id, job_family, period from windowed
    union all
    select job_id, 'All jobs', period from windowed
),

totals as (
    select
        job_family,
        count(*) filter (where period = 'recent') as recent,
        count(*) filter (where period = 'previous') as previous
    from postings
    group by job_family
),

by_skill as (
    select
        p.job_family,
        b.skill,
        count(*) filter (where p.period = 'recent') as recent,
        count(*) filter (where p.period = 'previous') as previous
    from postings as p
    inner join {{ ref('bridge_job_skill') }} as b using (job_id)
    group by all
)

select
    t.job_family,
    s.skill,
    s.category,
    t.recent as family_postings_recent,
    coalesce(b.recent, 0) as postings_recent,
    coalesce(b.previous, 0) as postings_previous,
    coalesce(b.recent, 0) / nullif(t.recent, 0) as share_recent,
    coalesce(b.previous, 0) / nullif(t.previous, 0) as share_previous,
    coalesce(b.recent, 0) / nullif(t.recent, 0)
        - coalesce(b.previous, 0) / nullif(t.previous, 0) as share_change,
    rank() over (partition by t.job_family order by coalesce(b.recent, 0) desc) as rank_recent
from totals as t
cross join {{ ref('dim_skill') }} as s
left join by_skill as b on b.job_family = t.job_family and b.skill = s.skill
