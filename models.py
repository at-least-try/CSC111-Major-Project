"""CSC111 Project: core data models.

This module defines typed data containers used by the course dataset loader,
RateMyProf scraper, and downstream recommendation/visualization steps.
"""

from __future__ import annotations

from dataclasses import dataclass


def normalize_course_number(course_code: str) -> str:
    """Return a normalized course number such as ``CSC148``.

    This helper maps formats like ``CSC148H1`` and ``csc148`` to a shared
    course-number key used by the ratings index.
    """
    cleaned = "".join(ch for ch in course_code.upper() if ch.isalnum())
    if len(cleaned) >= 6 and cleaned[:3].isalpha() and cleaned[3:6].isdigit():
        return cleaned[:6]
    return cleaned


@dataclass(frozen=True)
class Course:
    """A course from the U of T course dataset."""

    course_code: str
    course_title: str
    course_description: str
    prerequisite_groups: list[list[set[str]]]
    recommended: list[str]
    corequisite: list[str]
    exclusion: list[str]
    breadth_requirement: int

    @property
    def course_number(self) -> str:
        """Return normalized course number, e.g. ``CSC148``."""
        return normalize_course_number(self.course_code)


@dataclass(frozen=True)
class ProfessorProfile:
    """A professor profile scraped from RateMyProf."""

    legacy_id: int
    full_name: str
    department: str
    average_rating: float
    num_ratings: int
    course_numbers: set[str]


class CourseProfessorRatings:
    """Ratings grouped by score for one course number.

    Required structure from your spec:
    - ``course_number`` (e.g. ``CSC148``)
    - ``professors_by_score`` where keys are rating scores (1-5 range) and
      values are professor names with that score.
    """

    def __init__(
        self, course_number: str, professors_by_score: dict[float, list[str]] | None = None
    ) -> None:
        """Initialize rating buckets for one course."""
        self.course_number = course_number
        self.professors_by_score = professors_by_score if professors_by_score is not None else {}

    def add_professor(self, professor_name: str, score: float) -> None:
        """Add one professor to the bucket keyed by score."""
        rounded_score = round(score, 1)
        self.professors_by_score.setdefault(rounded_score, [])
        if professor_name not in self.professors_by_score[rounded_score]:
            self.professors_by_score[rounded_score].append(professor_name)


if __name__ == '__main__':
    import doctest
    doctest.testmod()

    import python_ta
    python_ta.check_all(config={
        'max-line-length': 120,
        'extra-imports': [
            'dataclasses', 'itertools', 'csv', 'json', 'pathlib', 'base64',
            'string', 'ssl', 'time', 'urllib.error', 'urllib.parse', 'urllib.request', 'os',
            'networkx', 'flask', 'plotly.graph_objects',
            'models', 'course_dataset', 'prerequisite_graph',
            'rmp_course_dataset', 'ratemyprof_scraper', 'web_app'
        ],
        'allowed-io': [
            'load_course_catalog',
            'write_course_professor_ratings_csv',
            'load_course_professor_ratings_csv',
            '_fetch_html',
            '_post_graphql'
        ]
    })
