"""CSC111 Project: course-to-professor ratings dataset pipeline.

This module builds and loads a CSV dataset with the structure:
- one row per course number (e.g. CSC148)
- a JSON dictionary mapping rating score -> list of professor names
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from models import CourseProfessorRatings
from Datasets.ratemyprof_scraper import (
    collect_professor_profiles_for_school_department,
)

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_RMP_CSV_PATH = PROJECT_ROOT / "Datasets" / "CourseProfessorRatings.csv"


def initialize_empty_rating_index(course_numbers: set[str]) -> dict[str, CourseProfessorRatings]:
    """Return an index with all course numbers present, even if no professor data exists."""
    return {
        course_number: CourseProfessorRatings(course_number=course_number)
        for course_number in sorted(course_numbers)
    }


def build_course_professor_ratings_from_scrape(
    course_numbers: set[str],
    department_substring: str = "computer science",
    page_size: int = 50,
    max_pages: int | None = 40,
    sleep_seconds: float = 0.2,
) -> tuple[dict[str, CourseProfessorRatings], int]:
    """Scrape RateMyProf and build course -> {score: [professors]} index.

    Returns:
    - populated course ratings index
    - number of professor profiles successfully scraped
    """
    profiles = collect_professor_profiles_for_school_department(
        department_substring=department_substring,
        page_size=page_size,
        max_pages=max_pages,
        sleep_seconds=sleep_seconds,
    )

    rating_index = initialize_empty_rating_index(course_numbers)
    for profile in profiles:
        for course_number in profile.course_numbers:
            if course_number in rating_index:
                rating_index[course_number].add_professor(
                    professor_name=profile.full_name,
                    score=profile.average_rating,
                )

    return rating_index, len(profiles)


def write_course_professor_ratings_csv(
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
            serializable = {f"{score:.1f}": sorted(names) for score, names in by_score.items()}
            writer.writerow(
                {
                    "course_number": course_number,
                    "professors_by_score_json": json.dumps(serializable, ensure_ascii=True),
                }
            )


def load_course_professor_ratings_csv(
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


def build_and_save_course_professor_ratings_dataset(
    course_numbers: set[str],
    output_path: Path = DEFAULT_RMP_CSV_PATH,
    department_substring: str = "computer science",
    page_size: int = 50,
    max_pages: int | None = 40,
    sleep_seconds: float = 0.2,
) -> tuple[dict[str, CourseProfessorRatings], int]:
    """Run full scrape -> map -> save pipeline in one call."""
    rating_index, profile_count = build_course_professor_ratings_from_scrape(
        course_numbers=course_numbers,
        department_substring=department_substring,
        page_size=page_size,
        max_pages=max_pages,
        sleep_seconds=sleep_seconds,
    )
    write_course_professor_ratings_csv(rating_index=rating_index, output_path=output_path)
    return rating_index, profile_count
