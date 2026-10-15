{#
  When each job was posted, first and last seen by an extract, closed, and removed.

  Unlisted deletes a job 14 days after it was posted, open or not. So "removed" usually
  means "aged out of Unlisted", not "filled". Only closed_at tells us a job was taken down.
#}
with extract_dates as (
    select distinct extract_date
    from {{ ref('stg_unlisted__present') }}
),

presence as (
    select
        job_id,
        min(extract_date) as first_present_on,
        max(extract_date) as last_present_on,
        min(extract_date) filter (where not is_open) as first_seen_closed_on
    from {{ ref('stg_unlisted__present') }}
    group by job_id
),

removed as (
    select
        presence.job_id,
        min(extract_dates.extract_date) as removed_on
    from presence
    inner join extract_dates
        on extract_dates.extract_date > presence.last_present_on
    group by presence.job_id
),

first_row as (
    select
        job_id,
        min(coalesce(posted_at, first_seen_at)) as posted_at,
        min(first_seen_at) as first_seen_at
    from {{ ref('stg_unlisted__jobs') }}
    group by job_id
),

current_version as (
    select job_id, closed_at
    from {{ ref('int_job_versions') }}
    where is_current
)

select
    first_row.job_id,
    cast(first_row.posted_at as date)          as posted_on,
    cast(first_row.first_seen_at as date)      as first_seen_on,
    presence.first_present_on,
    presence.last_present_on,
    coalesce(cast(current_version.closed_at as date), presence.first_seen_closed_on) as closed_on,
    removed.removed_on,
    case
        when current_version.closed_at is not null then 'closed'
        when removed.removed_on is not null then 'removed'
        else 'open'
    end as status
from first_row
inner join presence using (job_id)
left join removed using (job_id)
left join current_version using (job_id)
