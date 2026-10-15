-- Where a job is and who can take it: one row per combination seen in the data.
with combinations as (
    select distinct country, region, is_remote, remote_scope, open_to
    from {{ ref('int_job_versions') }}
)

select
    {{ hash_columns(['country', 'region', 'is_remote', 'remote_scope', 'open_to']) }} as location_key,
    country,
    region,
    is_remote,
    remote_scope,
    open_to,
    case
        when remote_scope = 'hybrid' then 'Hybrid'
        when is_remote then 'Remote'
        else 'On-site'
    end as workplace,
    case
        when not is_remote or remote_scope = 'hybrid' then null
        when open_to = 'anywhere' or remote_scope = 'global' then 'Worldwide'
        when open_to = 'region' or remote_scope = 'region' then 'One region'
        else 'One country'
    end as remote_reach
from combinations
