# hiring-warehouse

A data warehouse over the job postings [Unlisted](https://findunlisted.link) collects, and a
page that shows which skills new postings ask for, by type of role.

Unlisted reads about 40,000 open jobs from company career pages every hour, and deletes each
job 14 days after it was posted. This project keeps a daily copy of what changed, so the
history survives, and models it into a star schema with dbt.

## What you get

| Table | One row per |
|---|---|
| `fact_job_posting` | job posting: company, location, dates, status, pay, job family |
| `bridge_job_skill` | job and skill it mentions |
| `fact_daily_open_jobs` | job and day it was in Unlisted (a daily snapshot) |
| `dim_job_history` | version of a job: a new version whenever a tracked field changes |
| `dim_company`, `dim_location`, `dim_skill`, `dim_date` | the dimensions |
| `mart_skill_weekly`, `mart_skill_trend`, `mart_workplace_weekly` | the numbers behind the page |

The page is in `site/`, and the dbt docs (every table, column, test and how they connect)
are published next to it.

## Run it

You need [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run pytest                     # builds the warehouse from made-up extracts and checks it

export UNLISTED_DATABASE_URL=postgresql://...
uv run hiring-warehouse extract   # copy what changed since the last extract
uv run dbt build                  # rebuild every table from data/extracts, run every test
uv run hiring-warehouse export    # write site/data for the page
python3 -m http.server --directory site 8000
```

## How it works

```
Unlisted Postgres --extract--> data/extracts/extract_date=YYYY-MM-DD/  (Parquet, kept in Git)
                                        |
                                    dbt build
                                        |
        staging (views) -> intermediate (history, lifecycle, job family) -> marts (star schema)
                                        |
                                 export -> site/
```

1. **Extract.** Read-only, in one consistent snapshot of Unlisted's database: every job
   whose `updated_at` moved since the last extract (plus an hour of overlap), the full
   company list, and the id of every job present. Skills are found in each description
   during the extract, and the description is then dropped, so an ordinary day's extract
   is a few hundred kilobytes.
2. **Build.** dbt rebuilds every table from all the extracts, from an empty database, every
   run. Job history (slowly changing dimension type 2) is worked out from the extracts with
   window functions rather than with dbt snapshots, which keep history only inside the
   database and so cannot be rebuilt.
3. **Test.** Every model has tests: unique and not-null keys, relationships between facts and
   dimensions, accepted values, and custom checks such as "every job has exactly one current
   version".
4. **Publish.** A GitHub Actions job runs all of this daily, commits the extract, and
   publishes the page and the dbt docs to GitHub Pages.

Skills come from [`seeds/skills.csv`](seeds/skills.csv): 85 skills, each with a regular
expression. Job families come from [`seeds/job_families.csv`](seeds/job_families.csv),
matched against job titles in priority order.

## Things to know about the data

- Unlisted covers companies whose career pages run on Greenhouse or Ashby. Big employers on
  other systems are missing, so this is a sample of the market, not all of it.
- A skill counts when its name appears in the title or description. "Python is a plus" and
  "you must know Python" count the same.
- About a quarter of titles match no job family and are counted as "Other".
- Unlisted deletes a job 14 days after posting whether it was filled or not. "Removed" means
  it aged out of Unlisted; only "closed" means the company took it down.
- History starts with the first extract. Trends need a few weeks to say much.

## Licence

The code is MIT licensed. Job postings belong to the companies that published them.
