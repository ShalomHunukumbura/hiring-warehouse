"""Writes the small JSON files the trends page reads, and Parquet copies of the marts."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

DOWNLOADS = [
    "fact_job_posting",
    "bridge_job_skill",
    "dim_company",
    "dim_location",
    "dim_skill",
    "mart_skill_weekly",
    "mart_skill_trend",
    "mart_workplace_weekly",
]


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, separators=(",", ":"), default=str) + "\n")


def _share(value: object) -> float | None:
    return None if value is None else round(float(value), 5)


def export(warehouse: Path, out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(warehouse), read_only=True) as conn:
        for table in DOWNLOADS:
            conn.execute(
                f"COPY {table} TO '{out / table}.parquet' (FORMAT parquet, COMPRESSION zstd)"
            )

        newest, first, extracts = conn.execute(
            "SELECT max(extract_date), min(extract_date), count(DISTINCT extract_date) "
            "FROM staging.stg_unlisted__present"
        ).fetchone()
        open_now = conn.execute(
            "SELECT count(*) FROM fact_daily_open_jobs WHERE snapshot_date = ? AND is_open",
            [newest],
        ).fetchone()[0]
        new_7, remote_7 = conn.execute(
            "SELECT count(*), count(*) FILTER (WHERE l.workplace = 'Remote') "
            "FROM fact_job_posting f JOIN dim_location l USING (location_key) "
            "WHERE f.posted_on > ? - 7",
            [newest],
        ).fetchone()
        families = conn.execute(
            "SELECT job_family, max(family_postings_recent) AS n FROM mart_skill_trend "
            "GROUP BY 1 ORDER BY (job_family = 'All jobs') DESC, n DESC"
        ).fetchall()
        _write_json(
            out / "summary.json",
            {
                "newest_extract": newest,
                "first_extract": first,
                "extracts": extracts,
                "open_jobs": open_now,
                "new_postings_7d": new_7,
                "remote_share_7d": _share(remote_7 / new_7 if new_7 else None),
                "families": [{"name": name, "postings_28d": n} for name, n in families],
            },
        )

        trend: dict[str, list[dict]] = {}
        for family, skill, category, n, share, previous, change in conn.execute(
            "SELECT job_family, skill, category, postings_recent, share_recent, share_previous, "
            "share_change FROM mart_skill_trend ORDER BY job_family, rank_recent, skill"
        ).fetchall():
            trend.setdefault(family, []).append(
                {
                    "skill": skill,
                    "category": category,
                    "postings": n,
                    "share": _share(share),
                    "previous": _share(previous),
                    "change": _share(change),
                }
            )
        _write_json(out / "trend.json", trend)

        weekly: dict[str, dict] = {}
        for family, week, complete, postings, skill, share in conn.execute(
            "SELECT job_family, week_start, is_complete_week, postings_in_week, skill, share "
            "FROM mart_skill_weekly ORDER BY job_family, week_start, skill"
        ).fetchall():
            entry = weekly.setdefault(
                family, {"weeks": [], "complete": [], "postings": [], "skills": {}}
            )
            if not entry["weeks"] or entry["weeks"][-1] != week.isoformat():
                entry["weeks"].append(week.isoformat())
                entry["complete"].append(complete)
                entry["postings"].append(postings)
            entry["skills"].setdefault(skill, []).append(_share(share))
        _write_json(out / "weekly.json", weekly)

        _write_json(
            out / "workplace.json",
            [
                {"week": week, "workplace": workplace, "reach": reach or None, "postings": n}
                for week, workplace, reach, n in conn.execute(
                    "SELECT week_start, workplace, remote_reach, postings "
                    "FROM mart_workplace_weekly ORDER BY 1, 2, 3"
                ).fetchall()
            ],
        )
    return out
