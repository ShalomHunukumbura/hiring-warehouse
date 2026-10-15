{#
  Sorts each job into a family from its current title, using seeds/job_families.csv.
  Families are tried in priority order and the first that matches wins, so
  "Data Engineer" lands in Data before Software engineering gets a look.
#}
with titles as (
    select job_id, title
    from {{ ref('int_job_versions') }}
    where is_current
),

matches as (
    select
        titles.job_id,
        families.family,
        row_number() over (partition by titles.job_id order by families.priority) as pick
    from titles
    inner join {{ ref('job_families') }} as families
        on regexp_matches(titles.title, families.pattern, 'i')
)

select
    titles.job_id,
    coalesce(matches.family, 'Other') as job_family
from titles
left join matches on matches.job_id = titles.job_id and matches.pick = 1
