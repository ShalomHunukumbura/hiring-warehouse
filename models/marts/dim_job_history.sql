-- Every version of every job (type 2). Use is_current for the latest version.
select
    job_version_key,
    job_id,
    version_number,
    valid_from,
    valid_to,
    is_current,
    title,
    department,
    employment_type,
    location_raw,
    {{ hash_columns(['country', 'region', 'is_remote', 'remote_scope', 'open_to']) }} as location_key,
    comp_min,
    comp_max,
    comp_currency,
    comp_period,
    exp_min_years,
    exp_max_years,
    is_closed
from {{ ref('int_job_versions') }}
