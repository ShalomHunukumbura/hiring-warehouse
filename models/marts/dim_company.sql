-- One row per company, as it looked in the newest extract (type 1: no history kept).
select
    company_id,
    company_name,
    company_slug,
    ats,
    board_token,
    is_enabled,
    created_at
from {{ ref('stg_unlisted__companies') }}
qualify row_number() over (partition by company_id order by extract_date desc) = 1
