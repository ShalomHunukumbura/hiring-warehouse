select
    id           as company_id,
    extract_date,
    trim(name)   as company_name,
    ats,
    board_token,
    slug         as company_slug,
    enabled      as is_enabled,
    created_at
from {{ source('unlisted', 'companies') }}
