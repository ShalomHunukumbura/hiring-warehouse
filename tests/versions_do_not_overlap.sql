-- Each version ends the day the next one starts, and never before it began.
select *
from (
    select
        job_id,
        valid_from,
        valid_to,
        lead(valid_from) over (partition by job_id order by valid_from) as next_from
    from {{ ref('int_job_versions') }}
)
where valid_to <= valid_from
   or valid_to is distinct from next_from
