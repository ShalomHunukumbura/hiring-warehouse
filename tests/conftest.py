"""Builds three days of small made-up extracts and runs dbt over them.

What happens in them:

- 2026-10-01: jobs 1, 2 and 3 exist.
- 2026-10-02: job 1 is retitled, job 2 is touched with nothing we track changed,
  job 3 closes, job 4 is new.
- 2026-10-03: job 3 is gone (Unlisted pruned it); nothing else changed.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pytest

from hiring_warehouse.extract import COMPANY_TYPES, JOB_TYPES, _write

ROOT = Path(__file__).resolve().parents[1]


def _ts(day: str) -> datetime:
    return datetime.fromisoformat(f"{day}T09:00:00").replace(tzinfo=UTC)


def job(job_id: int, **changes: object) -> dict:
    row = {name: None for name in JOB_TYPES}
    row.update(
        id=job_id,
        ats="greenhouse",
        company_id=10 if job_id != 2 else 11,
        external_id=f"ext-{job_id}",
        title=f"Job {job_id}",
        remote=False,
        country="US",
        region="US",
        posted_at=_ts("2026-09-28"),
        first_seen_at=_ts("2026-09-29"),
        last_seen_at=_ts("2026-10-01"),
        updated_at=_ts("2026-10-01"),
        content_hash=f"h{job_id}",
    )
    row.update(changes)
    return row


COMPANIES = [
    {
        "id": 10,
        "name": "Acme",
        "ats": "greenhouse",
        "board_token": "acme",
        "slug": "acme",
        "enabled": True,
        "created_at": _ts("2026-09-01"),
    },
    {
        "id": 11,
        "name": "Globex",
        "ats": "greenhouse",
        "board_token": "globex",
        "slug": "globex",
        "enabled": True,
        "created_at": _ts("2026-09-01"),
    },
]

EXTRACTS = {
    "2026-10-01": {
        "jobs": [
            job(1, title="Data Engineer"),
            job(
                2,
                remote=True,
                remote_scope="global",
                open_to="anywhere",
                country=None,
                region=None,
                comp_min=100000,
                comp_max=150000,
                comp_currency="USD",
                comp_period="year",
            ),
            job(3, title="Analyst", posted_at=_ts("2026-09-30")),
        ],
        "skills": [(1, "Python"), (1, "SQL"), (2, "Go"), (3, "SQL"), (3, "Excel")],
        "present": [(1, True), (2, True), (3, True)],
    },
    "2026-10-02": {
        "jobs": [
            job(1, title="Senior Data Engineer", updated_at=_ts("2026-10-02")),
            job(
                2,
                remote=True,
                remote_scope="global",
                open_to="anywhere",
                country=None,
                region=None,
                comp_min=100000,
                comp_max=150000,
                comp_currency="USD",
                comp_period="year",
                last_seen_at=_ts("2026-10-02"),
                updated_at=_ts("2026-10-02"),
            ),
            job(
                3,
                title="Analyst",
                posted_at=_ts("2026-09-30"),
                closed_at=_ts("2026-10-02"),
                updated_at=_ts("2026-10-02"),
            ),
            job(
                4,
                title="Frontend Engineer",
                posted_at=_ts("2026-10-02"),
                first_seen_at=_ts("2026-10-02"),
                updated_at=_ts("2026-10-02"),
            ),
        ],
        "skills": [
            (1, "Python"),
            (1, "SQL"),
            (1, "dbt"),
            (2, "Go"),
            (3, "SQL"),
            (3, "Excel"),
            (4, "React"),
            (4, "TypeScript"),
        ],
        "present": [(1, True), (2, True), (3, False), (4, True)],
    },
    "2026-10-03": {
        "jobs": [],
        "skills": [],
        "present": [(1, True), (2, True), (4, True)],
    },
}


def write_extracts(folder: Path) -> None:
    with duckdb.connect() as conn:
        for day, extract in EXTRACTS.items():
            out = folder / f"extract_date={day}"
            out.mkdir(parents=True)
            _write(conn, extract["jobs"], JOB_TYPES, out / "jobs.parquet")
            _write(
                conn,
                [{"job_id": j, "skill": s} for j, s in extract["skills"]],
                {"job_id": "BIGINT", "skill": "VARCHAR"},
                out / "job_skills.parquet",
            )
            _write(conn, COMPANIES, COMPANY_TYPES, out / "companies.parquet")
            _write(
                conn,
                [{"id": j, "open": o} for j, o in extract["present"]],
                {"id": "BIGINT", "open": "BOOLEAN"},
                out / "present.parquet",
            )
            (out / "manifest.json").write_text(json.dumps({"watermark": f"{day}T12:00:00+00:00"}))


def dbt_build(extracts: Path, warehouse: Path, target: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "dbt",
            "build",
            "--vars",
            json.dumps({"extracts": str(extracts)}),
            "--target-path",
            str(target),
            "--log-path",
            str(target / "logs"),
        ],
        cwd=ROOT,
        env={**os.environ, "HW_WAREHOUSE": str(warehouse)},
        capture_output=True,
        text=True,
    )


@pytest.fixture(scope="session")
def warehouse(tmp_path_factory: pytest.TempPathFactory) -> duckdb.DuckDBPyConnection:
    tmp = tmp_path_factory.mktemp("warehouse")
    write_extracts(tmp / "extracts")
    result = dbt_build(tmp / "extracts", tmp / "warehouse.duckdb", tmp / "target")
    assert result.returncode == 0, result.stdout[-4000:]
    conn = duckdb.connect(str(tmp / "warehouse.duckdb"), read_only=True)
    yield conn
    conn.close()


@pytest.fixture
def newest_day() -> date:
    return date(2026, 10, 3)
