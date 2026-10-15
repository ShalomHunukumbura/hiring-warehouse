{#
  For each week, job family and skill: how many new postings asked for the skill, and
  what share of the family's new postings that is. "All jobs" covers every family.

  A week counts as complete once the warehouse has seen all of it, so the newest week
  is not compared as if it were finished.
#}
with postings as (
    select f.job_id, f.job_family, d.week_start
    from {{ ref('fact_job_posting') }} as f
    inner join {{ ref('dim_date') }} as d on d.date_day = f.posted_on
    union all
    select f.job_id, 'All jobs', d.week_start
    from {{ ref('fact_job_posting') }} as f
    inner join {{ ref('dim_date') }} as d on d.date_day = f.posted_on
),

weeks as (
    select week_start, job_family, count(*) as postings
    from postings
    group by all
),

newest as (
    select max(extract_date) as newest_extract
    from {{ ref('stg_unlisted__present') }}
),

counts as (
    select p.week_start, p.job_family, b.skill, count(*) as postings_with_skill
    from postings as p
    inner join {{ ref('bridge_job_skill') }} as b using (job_id)
    group by all
)

select
    w.week_start,
    w.job_family,
    s.skill,
    s.category,
    coalesce(c.postings_with_skill, 0) as postings_with_skill,
    w.postings as postings_in_week,
    coalesce(c.postings_with_skill, 0) / w.postings as share,
    w.week_start + 6 < newest.newest_extract as is_complete_week
from weeks as w
cross join {{ ref('dim_skill') }} as s
cross join newest
left join counts as c
    on c.week_start = w.week_start and c.job_family = w.job_family and c.skill = s.skill
