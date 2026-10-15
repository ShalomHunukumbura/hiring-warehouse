{#
  One row per job posting: the main fact table. Keys point at the dimensions; the rest
  are measures and dates. Attributes come from the job's current version.
#}
with current_version as (
    select *
    from {{ ref('int_job_versions') }}
    where is_current
),

skill_counts as (
    select job_id, count(*) as skill_count
    from {{ ref('bridge_job_skill') }}
    group by job_id
)

select
    v.job_id,
    v.company_id,
    {{ hash_columns(['v.country', 'v.region', 'v.is_remote', 'v.remote_scope', 'v.open_to']) }} as location_key,
    l.posted_on,
    l.first_present_on,
    l.last_present_on,
    l.closed_on,
    l.removed_on,
    l.status,
    v.title,
    fam.job_family,
    v.department,
    v.employment_type,
    v.exp_min_years,
    -- Pay as a yearly US dollar figure, only where Unlisted parsed it in USD.
    case
        when v.comp_currency <> 'USD' then null
        when v.comp_period = 'year' then v.comp_min
        when v.comp_period = 'month' then v.comp_min * 12
        when v.comp_period = 'hour' then v.comp_min * 2080
    end as pay_min_usd_yearly,
    case
        when v.comp_currency <> 'USD' then null
        when v.comp_period = 'year' then v.comp_max
        when v.comp_period = 'month' then v.comp_max * 12
        when v.comp_period = 'hour' then v.comp_max * 2080
    end as pay_max_usd_yearly,
    case when l.closed_on is not null then l.closed_on - l.posted_on end as days_to_close,
    coalesce(s.skill_count, 0) as skill_count
from current_version as v
inner join {{ ref('int_job_lifecycle') }} as l using (job_id)
left join skill_counts as s using (job_id)
inner join {{ ref('int_job_family') }} as fam using (job_id)
