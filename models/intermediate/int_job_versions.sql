{#
  The history of every job, one row per version (slowly changing dimension, type 2).

  A job shows up in an extract whenever Unlisted touched it, often with nothing we care
  about changed (Unlisted bumps last_seen_at on every sync). So we hash the attributes we
  track and keep only the rows where that hash differs from the job's previous row. Each
  kept row is valid from its extract date until the next kept row's date.

  Everything here comes from the saved extracts, so it rebuilds the same from an empty
  database.
#}
{% set tracked = [
    'title', 'department', 'team', 'employment_type', 'location_raw', 'country', 'region',
    'is_remote', 'remote_scope', 'open_to', 'comp_min', 'comp_max', 'comp_currency',
    'comp_period', 'exp_min_years', 'exp_max_years', 'is_closed'
] %}

with rows as (
    select
        *,
        closed_at is not null as is_closed
    from {{ ref('stg_unlisted__jobs') }}
),

hashed as (
    select
        *,
        {{ hash_columns(tracked) }} as attributes_hash
    from rows
),

compared as (
    select
        *,
        lag(attributes_hash) over (partition by job_id order by extract_date) as previous_hash
    from hashed
),

changes as (
    select *
    from compared
    where previous_hash is null or previous_hash <> attributes_hash
)

select
    {{ hash_columns(['job_id', 'extract_date']) }} as job_version_key,
    job_id,
    company_id,
    {% for column in tracked %}{{ column }},
    {% endfor -%}
    closed_at,
    extract_date as valid_from,
    lead(extract_date) over (partition by job_id order by extract_date) as valid_to,
    lead(extract_date) over (partition by job_id order by extract_date) is null as is_current,
    row_number() over (partition by job_id order by extract_date) as version_number
from changes
