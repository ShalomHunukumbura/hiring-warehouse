-- The skill dictionary. The extract uses the same file to find skills in descriptions.
select
    skill,
    category
from {{ ref('skills') }}
