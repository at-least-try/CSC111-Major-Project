"""CSC111 Project: course dataset loading utilities."""

from __future__ import annotations

import csv
from pathlib import Path

from models import Course, normalize_course_number

CSV_SPLIT_CHAR = "|"
LIST_SPLIT_CHAR = ","
DEFAULT_COURSE_DATA_PATH = Path("Datasets/CourseData.csv")


def _split_optional_list(raw: str) -> list[str]:
    """Return comma-separated values with empty entries removed."""
    if not raw:
        return []
    return [item.strip() for item in raw.split(LIST_SPLIT_CHAR) if item.strip()]


def load_course_catalog(csv_path: Path = DEFAULT_COURSE_DATA_PATH) -> dict[str, Course]:
    """Load course catalog from the project CSV.

    Returned dictionary keys are full course codes such as ``CSC148H1``.
    """
    courses = {}
    with csv_path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file, delimiter=CSV_SPLIT_CHAR)
        for row in reader:
            course = Course(
                course_code=row["Course Code"].strip(),
                course_title=row["Course Title"].strip(),
                course_description=row["Course Description"].strip(),
                prerequisites=_split_optional_list(row["Prerequisites"].strip()),
                recommended=_split_optional_list(row["Recommended"].strip()),
                corequisite=_split_optional_list(row["Corequisite"].strip()),
                exclusion=_split_optional_list(row["Exclusion"].strip()),
                breadth_requirement=int(row["Breadth Requirement"].strip() or "0"),
            )
            courses[course.course_code] = course
    return courses


def build_course_number_index(courses: dict[str, Course]) -> dict[str, list[Course]]:
    """Group catalog courses by normalized course number (e.g. ``CSC148``)."""
    grouped = {}
    for course in courses.values():
        course_number = normalize_course_number(course.course_code)
        grouped.setdefault(course_number, [])
        grouped[course_number].append(course)
    return grouped
