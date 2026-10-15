{#
  A periodic snapshot: one row per job per extract day it was in Unlisted. Answers
  "how many jobs were open on this day?", which a table of postings cannot.
#}
select
    p.extract_date as snapshot_date,
    p.job_id,
    p.is_open,
    f.company_id,
    f.location_key
from {{ ref('stg_unlisted__present') }} as p
inner join {{ ref('fact_job_posting') }} as f using (job_id)
