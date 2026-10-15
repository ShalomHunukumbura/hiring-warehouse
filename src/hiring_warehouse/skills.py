"""Finds skills in job text, using the dictionary in seeds/skills.csv.

dbt loads the same file as the skill dimension, so the list of skills lives in one place.
"""

from __future__ import annotations

import csv
import html
import re
from dataclasses import dataclass
from pathlib import Path

TAG = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class Skill:
    name: str
    category: str
    pattern: re.Pattern[str]
    # Words from the pattern. A match always contains at least one of them, so when none
    # is in the text we can skip the regex, which is the slow part.
    hints: tuple[str, ...]


def _alternatives(pattern: str) -> list[str]:
    """Split a pattern on the | that are not inside brackets."""
    parts, depth, start, i = [], 0, 0, 0
    while i < len(pattern):
        char = pattern[i]
        if char == "\\":
            i += 1
        elif char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
        elif char == "|" and depth == 0:
            parts.append(pattern[start:i])
            start = i + 1
        i += 1
    return [*parts, pattern[start:]]


def _hints(pattern: str) -> tuple[str, ...]:
    hints: list[str] = []
    for alternative in _alternatives(pattern):
        text = re.sub(r"\\.", " ", alternative.lower())  # drop escapes such as \b and \+
        text = re.sub(r"[a-z0-9]\?", " ", text)  # an optional letter may be absent
        words = re.findall(r"[a-z0-9]+", text)
        # Prefer words of two or more letters: a single letter such as "c" is in every text.
        hints += [w for w in words if len(w) > 1] or words
    return tuple(dict.fromkeys(hints))


def load_skills(path: Path) -> list[Skill]:
    with path.open(newline="") as f:
        return [
            Skill(
                row["skill"],
                row["category"],
                re.compile(row["pattern"], 0 if row["case_sensitive"] == "true" else re.I),
                _hints(row["pattern"]),
            )
            for row in csv.DictReader(f)
        ]


def find_skills(skills: list[Skill], title: str, description_html: str | None) -> list[str]:
    """Names of the skills mentioned in the title or description, in dictionary order.

    Each skill is its own search, so overlapping mentions all count: "React Native"
    finds both React and React Native, and "Python/Go" finds both languages.
    """
    text = f"{title}\n{html_to_text(description_html)}"
    lower = text.lower()
    return [
        skill.name
        for skill in skills
        if any(hint in lower for hint in skill.hints) and skill.pattern.search(text)
    ]


def html_to_text(description_html: str | None) -> str:
    """Tags become line breaks, so "<li>Go</li><li>Python</li>" reads as two lines."""
    if not description_html:
        return ""
    return html.unescape(TAG.sub("\n", description_html))
