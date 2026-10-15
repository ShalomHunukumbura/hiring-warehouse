"""Checks what dbt built from the made-up extracts in conftest.py."""

from datetime import date


def rows(conn, sql):
    return conn.execute(sql).fetchall()


def test_a_retitled_job_gets_a_second_version(warehouse):
    assert rows(
        warehouse,
        "SELECT version_number, title, valid_from, valid_to, is_current "
        "FROM dim_job_history WHERE job_id = 1 ORDER BY version_number",
    ) == [
        (1, "Data Engineer", date(2026, 10, 1), date(2026, 10, 2), False),
        (2, "Senior Data Engineer", date(2026, 10, 2), None, True),
    ]


def test_a_touch_that_changes_nothing_tracked_is_not_a_version(warehouse):
    # Job 2 is in both extracts, but only last_seen_at moved.
    assert rows(warehouse, "SELECT count(*) FROM dim_job_history WHERE job_id = 2") == [(1,)]


def test_closing_is_a_new_version(warehouse):
    assert rows(
        warehouse,
        "SELECT is_closed, valid_from FROM dim_job_history WHERE job_id = 3 ORDER BY valid_from",
    ) == [(False, date(2026, 10, 1)), (True, date(2026, 10, 2))]


def test_lifecycle(warehouse):
    assert rows(
        warehouse,
        "SELECT job_id, status, posted_on, closed_on, removed_on, days_to_close "
        "FROM fact_job_posting ORDER BY job_id",
    ) == [
        (1, "open", date(2026, 9, 28), None, None, None),
        (2, "open", date(2026, 9, 28), None, None, None),
        (3, "closed", date(2026, 9, 30), date(2026, 10, 2), date(2026, 10, 3), 2),
        (4, "open", date(2026, 10, 2), None, None, None),
    ]


def test_skills_come_from_the_newest_extract(warehouse):
    assert rows(warehouse, "SELECT skill FROM bridge_job_skill WHERE job_id = 1 ORDER BY 1") == [
        ("Python",),
        ("SQL",),
        ("dbt",),
    ]


def test_remote_job_location(warehouse):
    assert rows(
        warehouse,
        "SELECT l.workplace, l.remote_reach FROM fact_job_posting f "
        "JOIN dim_location l USING (location_key) WHERE f.job_id = 2",
    ) == [("Remote", "Worldwide")]


def test_pay_is_yearly_usd(warehouse):
    assert rows(
        warehouse,
        "SELECT pay_min_usd_yearly, pay_max_usd_yearly FROM fact_job_posting WHERE job_id = 2",
    ) == [(100000, 150000)]


def test_daily_snapshot_counts_open_jobs(warehouse):
    assert rows(
        warehouse,
        "SELECT snapshot_date, count(*) FILTER (WHERE is_open) FROM fact_daily_open_jobs "
        "GROUP BY 1 ORDER BY 1",
    ) == [(date(2026, 10, 1), 3), (date(2026, 10, 2), 3), (date(2026, 10, 3), 3)]


def test_skill_share_per_week(warehouse):
    # The week of 28 September holds all four jobs. SQL is in jobs 1 and 3. The newest
    # extract is 3 October, so the week (to 4 October) is not complete yet.
    assert rows(
        warehouse,
        "SELECT postings_with_skill, postings_in_week, round(share, 4), is_complete_week "
        "FROM mart_skill_weekly WHERE week_start = DATE '2026-09-28' AND skill = 'SQL' "
        "AND job_family = 'All jobs'",
    ) == [(2, 4, 0.5, False)]
