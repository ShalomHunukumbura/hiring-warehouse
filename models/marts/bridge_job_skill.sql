{#
  Which skills each job asks for. One job has many skills and one skill is in many jobs,
  so this sits between fact_job_posting and dim_skill.

  Skills come from the job's newest extract row: if the description changed, the skills
  found in the new text replace the old ones.
#}
with newest as (
    select job_id, max(extract_date) as extract_date
    from {{ ref('stg_unlisted__jobs') }}
    group by job_id
)

select distinct
    s.job_id,
    s.skill
from {{ ref('stg_unlisted__job_skills') }} as s
inner join newest using (job_id, extract_date)
