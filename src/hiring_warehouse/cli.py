"""hiring-warehouse: keep the history of Unlisted's job postings."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from . import __version__


def cmd_extract(args: argparse.Namespace) -> int:
    from .extract import extract

    url = os.environ.get("UNLISTED_DATABASE_URL")
    if not url:
        print("set UNLISTED_DATABASE_URL to Unlisted's Postgres connection string", file=sys.stderr)
        return 2
    result = extract(url, args.root, args.today, args.root / "seeds" / "skills.csv")
    print(
        f"extract: {result.jobs} changed jobs, {result.skills} job skills, "
        f"{result.companies} companies, {result.present} jobs present -> {result.folder}"
    )
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    from .export import export

    print(f"exports in {export(args.root / 'warehouse.duckdb', args.root / 'site' / 'data')}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hiring-warehouse", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="project folder")
    commands = parser.add_subparsers(dest="command", required=True)

    p = commands.add_parser("extract", help="copy what changed in Unlisted since the last extract")
    p.add_argument(
        "--today",
        type=date.fromisoformat,
        default=datetime.now(UTC).date(),
        help="date to file the extract under (UTC)",
    )
    p.set_defaults(run=cmd_extract)

    p = commands.add_parser("export", help="write the trends page's data from the warehouse")
    p.set_defaults(run=cmd_export)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.run(args)
