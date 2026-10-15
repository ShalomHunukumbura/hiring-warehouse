-- Every job has exactly one current version.
select job_id, count(*) filter (where is_current) as current_versions
from {{ ref('int_job_versions') }}
group by job_id
having count(*) filter (where is_current) <> 1
