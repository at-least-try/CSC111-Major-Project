"""CSC111 Project: course-to-professor ratings dataset helpers.

This module loads and writes a CSV dataset with the structure:
- one row per course number (e.g. CSC148)
- a JSON dictionary mapping rating score -> list of professor names
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from models import CourseProfessorRatings

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_RMP_CSV_PATH = PROJECT_ROOT / "Datasets" / "CourseProfessorRatings.csv"


def initialize_empty_rating_index(
    course_numbers: set[str],
) -> dict[str, CourseProfessorRatings]:
    """Return an index with all course numbers present.

    Courses with no professor data still get an empty entry.
    """
    return {
        course_number: CourseProfessorRatings(course_number=course_number)
        for course_number in sorted(course_numbers)
    }


def build_ratings_from_scrape(
    course_numbers: set[str],
) -> tuple[dict[str, CourseProfessorRatings], int]:
    """Build a ratings index from existing CSV data.

    Returns:
    - populated course ratings index containing all requested courses
    - profile count (always 0, since scraping is disabled)
    """
    rating_index = initialize_empty_rating_index(course_numbers)
    existing_index = {}
    if DEFAULT_RMP_CSV_PATH.exists():
        existing_index = load_ratings_csv(DEFAULT_RMP_CSV_PATH)

    for course_number in rating_index:
        if course_number in existing_index:
            rating_index[course_number] = existing_index[course_number]

    return rating_index, 0


def write_ratings_csv(
    rating_index: dict[str, CourseProfessorRatings],
    output_path: Path = DEFAULT_RMP_CSV_PATH,
) -> None:
    """Write course professor ratings to CSV."""
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["course_number", "professors_by_score_json"],
        )
        writer.writeheader()
        for course_number in sorted(rating_index):
            by_score = rating_index[course_number].professors_by_score
            serializable = {
                f"{score:.1f}": sorted(names)
                for score, names in by_score.items()
            }
            writer.writerow(
                {
                    "course_number": course_number,
                    "professors_by_score_json": json.dumps(
                        serializable, ensure_ascii=True
                    ),
                }
            )


def load_ratings_csv(
    input_path: Path = DEFAULT_RMP_CSV_PATH,
) -> dict[str, CourseProfessorRatings]:
    """Load course professor ratings CSV into typed data objects."""
    rating_index = {}
    with input_path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            course_number = row["course_number"].strip()
            payload = row["professors_by_score_json"].strip()
            parsed = json.loads(payload) if payload else {}

            course_ratings = CourseProfessorRatings(course_number=course_number)
            for score_str, names in parsed.items():
                score = float(score_str)
                course_ratings.professors_by_score[score] = sorted(list(names))
            rating_index[course_number] = course_ratings

    return rating_index


def build_and_save_ratings_dataset(
    course_numbers: set[str],
    output_path: Path = DEFAULT_RMP_CSV_PATH,
) -> tuple[dict[str, CourseProfessorRatings], int]:
    """Build ratings dataset from existing CSV and save normalized output.
    """
    rating_index, profile_count = build_ratings_from_scrape(
        course_numbers=course_numbers,
    )
    write_ratings_csv(rating_index=rating_index, output_path=output_path)
    return rating_index, profile_count


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
