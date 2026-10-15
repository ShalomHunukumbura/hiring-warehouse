"""Copies what changed in Unlisted's database since the last extract.

Unlisted deletes jobs 14 days after they are posted. Each extract keeps the rows that
changed, so the history survives here after Unlisted throws it away.

An extract is a folder, data/extracts/extract_date=YYYY-MM-DD/, holding:

- jobs.parquet        every job added or changed since the last extract (no descriptions)
- job_skills.parquet  the skills found in those jobs' descriptions
- companies.parquet   every company, in full (it is small)
- present.parquet     the id of every job in Unlisted right now, and whether it is open
- manifest.json       when it ran, the watermark, and row counts
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb
import psycopg
from psycopg.rows import dict_row

from .skills import find_skills, load_skills

# Each extract re-reads this much time before the previous watermark. A sync transaction
# that began before our snapshot but committed after it stamps updated_at earlier than the
# watermark, and without the overlap its rows would be skipped for good. Rows read twice
# are harmless: dbt only starts a new version when something tracked changed.
OVERLAP = timedelta(hours=1)

JOB_COLUMNS = [
    "id",
    "ats",
    "company_id",
    "external_id",
    "title",
    "department",
    "team",
    "employment_type",
    "location_raw",
    "country",
    "region",
    "remote",
    "remote_scope",
    "open_to",
    "comp_min",
    "comp_max",
    "comp_currency",
    "comp_period",
    "exp_min_years",
    "exp_max_years",
    "posted_at",
    "first_seen_at",
    "last_seen_at",
    "closed_at",
    "updated_at",
    "content_hash",
]
COMPANY_COLUMNS = ["id", "name", "ats", "board_token", "slug", "enabled", "created_at"]

# Column types for the Parquet files. Spelled out so an empty extract has the same
# schema as a full one.
JOB_TYPES = {
    "id": "BIGINT",
    "ats": "VARCHAR",
    "company_id": "BIGINT",
    "external_id": "VARCHAR",
    "title": "VARCHAR",
    "department": "VARCHAR",
    "team": "VARCHAR",
    "employment_type": "VARCHAR",
    "location_raw": "VARCHAR",
    "country": "VARCHAR",
    "region": "VARCHAR",
    "remote": "BOOLEAN",
    "remote_scope": "VARCHAR",
    "open_to": "VARCHAR",
    "comp_min": "DECIMAL(14,2)",
    "comp_max": "DECIMAL(14,2)",
    "comp_currency": "VARCHAR",
    "comp_period": "VARCHAR",
    "exp_min_years": "SMALLINT",
    "exp_max_years": "SMALLINT",
    "posted_at": "TIMESTAMPTZ",
    "first_seen_at": "TIMESTAMPTZ",
    "last_seen_at": "TIMESTAMPTZ",
    "closed_at": "TIMESTAMPTZ",
    "updated_at": "TIMESTAMPTZ",
    "content_hash": "VARCHAR",
}
COMPANY_TYPES = {
    "id": "BIGINT",
    "name": "VARCHAR",
    "ats": "VARCHAR",
    "board_token": "VARCHAR",
    "slug": "VARCHAR",
    "enabled": "BOOLEAN",
    "created_at": "TIMESTAMPTZ",
}


@dataclass
class Result:
    folder: Path
    jobs: int
    skills: int
    companies: int
    present: int


def extracts_dir(root: Path) -> Path:
    return root / "data" / "extracts"


def last_watermark(root: Path) -> datetime | None:
    """The watermark of the newest extract, or None if there are none yet."""
    manifests = sorted(extracts_dir(root).glob("extract_date=*/manifest.json"))
    if not manifests:
        return None
    return datetime.fromisoformat(json.loads(manifests[-1].read_text())["watermark"])


def _select(columns: list[str]) -> str:
    # ats is a Postgres enum; read it as plain text.
    return ", ".join("ats::text AS ats" if c == "ats" else c for c in columns)


def _write(conn: duckdb.DuckDBPyConnection, rows: list[dict], types: dict, path: Path) -> None:
    """Write rows to Parquet with the given column types.

    Inserting row by row into DuckDB is slow, so the rows go through a JSON-lines file
    that DuckDB reads in one go.
    """
    staging = path.with_suffix(".jsonl")
    with staging.open("w") as f:
        for row in rows:
            f.write(json.dumps({name: row[name] for name in types}, default=str) + "\n")
    columns = "{" + ", ".join(f"'{name}': '{kind}'" for name, kind in types.items()) + "}"
    order = "id" if "id" in types else ", ".join(types)
    conn.execute(
        f"COPY (SELECT * FROM read_json('{staging}', format = 'newline_delimited', "
        f"columns = {columns}) ORDER BY {order}) "
        f"TO '{path}' (FORMAT parquet, COMPRESSION zstd)"
    )
    staging.unlink()


def extract(database_url: str, root: Path, today: date, skills_csv: Path) -> Result:
    skills = load_skills(skills_csv)
    previous = last_watermark(root)
    since = previous - OVERLAP if previous else None
    folder = extracts_dir(root) / f"extract_date={today.isoformat()}"
    if folder.exists():
        raise SystemExit(f"{folder} already exists; one extract a day")

    # Read-only, and one snapshot of the database for all four queries, so the changed
    # rows and the list of present jobs agree with each other.
    with psycopg.connect(database_url, row_factory=dict_row) as db:
        db.read_only = True
        db.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        # A server-side cursor streams the changed jobs in batches. Each description is
        # read, searched for skills and dropped, so they are never all in memory at once.
        jobs: list[dict] = []
        job_skills: list[dict] = []
        with db.transaction():
            with db.cursor() as cur:
                cur.execute("SELECT now() AS now")
                watermark = cur.fetchone()["now"]
            with db.cursor(name="changed_jobs") as stream:
                stream.itersize = 2000
                stream.execute(
                    f"SELECT {_select(JOB_COLUMNS)}, description_html "
                    "FROM jobs WHERE (%(since)s::timestamptz IS NULL OR updated_at > %(since)s) "
                    "AND updated_at <= %(watermark)s ORDER BY id",
                    {"since": since, "watermark": watermark},
                )
                for job in stream:
                    description = job.pop("description_html")
                    job_skills += [
                        {"job_id": job["id"], "skill": name}
                        for name in find_skills(skills, job["title"], description)
                    ]
                    jobs.append(job)
            with db.cursor() as cur:
                cur.execute(f"SELECT {_select(COMPANY_COLUMNS)} FROM companies")
                companies = cur.fetchall()
                cur.execute("SELECT id, closed_at IS NULL AS open FROM jobs ORDER BY id")
                present = cur.fetchall()

    # Write into a temporary folder, then rename, so a crash never leaves half an extract.
    tmp = folder.with_name(folder.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    with duckdb.connect() as conn:
        _write(conn, jobs, JOB_TYPES, tmp / "jobs.parquet")
        _write(
            conn, job_skills, {"job_id": "BIGINT", "skill": "VARCHAR"}, tmp / "job_skills.parquet"
        )
        _write(conn, companies, COMPANY_TYPES, tmp / "companies.parquet")
        _write(conn, present, {"id": "BIGINT", "open": "BOOLEAN"}, tmp / "present.parquet")
    (tmp / "manifest.json").write_text(
        json.dumps(
            {
                "extract_date": today.isoformat(),
                "extracted_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "since": since.isoformat() if since else None,
                "watermark": watermark.isoformat(),
                "rows": {
                    "jobs": len(jobs),
                    "job_skills": len(job_skills),
                    "companies": len(companies),
                    "present": len(present),
                },
            },
            indent=2,
        )
        + "\n"
    )
    os.replace(tmp, folder)
    return Result(folder, len(jobs), len(job_skills), len(companies), len(present))
