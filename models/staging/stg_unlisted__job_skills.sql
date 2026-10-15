select
    job_id,
    extract_date,
    skill
from {{ source('unlisted', 'job_skills') }}
