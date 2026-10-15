-- Which jobs existed in Unlisted on each extract date, and whether they were open.
select
    id       as job_id,
    extract_date,
    open     as is_open
from {{ source('unlisted', 'present') }}
