-- A job cannot close before it was posted.
select job_id, posted_on, closed_on
from {{ ref('fact_job_posting') }}
where closed_on < posted_on
