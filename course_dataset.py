"""CSC111 Project: course dataset loading utilities."""

from __future__ import annotations

import csv
from pathlib import Path

from models import Course, normalize_course_number

CSV_SPLIT_CHAR = "|"
OPTION_SPLIT_CHAR = "/"
GROUP_SPLIT_CHAR = ";"
AND_SPLIT_CHAR = "&"
PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_COURSE_DATA_PATH = PROJECT_ROOT / "Datasets" / "CourseData.csv"


def _split_course_list(raw: str) -> list[str]:
    """Split a flat course list using ``/`` (and legacy `,`) separators."""
    if not raw:
        return []
    normalized = raw.replace(",", OPTION_SPLIT_CHAR)
    result = []
    for token in normalized.split(OPTION_SPLIT_CHAR):
        cleaned = token.strip()
        if cleaned:
            result.append(normalize_course_number(cleaned))
    return result


def _parse_prerequisite_groups(raw: str) -> list[list[set[str]]]:
    """Parse prerequisite text into groups of options.

    Format supported:
    - groups separated by ``;`` (`,` also treated as group separator)
    - options in each group separated by ``/``
    - courses joined by ``&`` must all be completed for that option

    Example:
    ``CSC236/CSC240; MAT135&MAT136/MAT137`` becomes:
    ``[[{'CSC236'}, {'CSC240'}], [{'MAT135', 'MAT136'}, {'MAT137'}]]``
    """
    if not raw:
        return []

    text = raw.replace(",", GROUP_SPLIT_CHAR)
    groups = []
    for group_text in text.split(GROUP_SPLIT_CHAR):
        group_text = group_text.strip()
        if not group_text:
            continue

        options = _parse_group_options(group_text)

        if options:
            groups.append(options)
    return groups


def _parse_group_options(group_text: str) -> list[set[str]]:
    """Parse one group string into option sets."""
    options = []
    for option_text in group_text.split(OPTION_SPLIT_CHAR):
        normalized_option = _parse_option_courses(option_text)
        if normalized_option and normalized_option not in options:
            options.append(normalized_option)
    return options


def _parse_option_courses(option_text: str) -> set[str]:
    """Parse one option string (possibly joined by ``&``) into a set."""
    cleaned_option = option_text.strip()
    if not cleaned_option:
        return set()

    required_courses = set()
    for part in cleaned_option.split(AND_SPLIT_CHAR):
        cleaned_part = part.strip()
        if cleaned_part:
            required_courses.add(normalize_course_number(cleaned_part))
    return required_courses


def load_course_catalog(
    csv_path: Path = DEFAULT_COURSE_DATA_PATH,
) -> dict[str, Course]:
    """Load course catalog from the project CSV.

    Returned dictionary keys are full course codes such as ``CSC148H1``.
    """
    courses = {}
    with csv_path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file, delimiter=CSV_SPLIT_CHAR)
        for row in reader:
            recommended = _split_course_list(row["Recommended"].strip())
            corequisite = _split_course_list(row["Corequisite"].strip())
            breadth_requirement = int(row["Breadth Requirement"].strip() or "0")
            course = Course(
                course_code=row["Course Code"].strip(),
                course_title=row["Course Title"].strip(),
                course_description=row["Course Description"].strip(),
                prerequisite_groups=_parse_prerequisite_groups(
                    row["Prerequisites"].strip()
                ),
                advisory={
                    "recommended": recommended,
                    "corequisite": corequisite,
                },
                exclusion=_split_course_list(row["Exclusion"].strip()),
                breadth_requirement=breadth_requirement,
            )
            courses[course.course_code] = course
    return courses


def build_course_number_index(
    courses: dict[str, Course],
) -> dict[str, list[Course]]:
    """Group catalog courses by normalized course number (e.g. ``CSC148``)."""
    grouped = {}
    for course in courses.values():
        course_number = normalize_course_number(course.course_code)
        grouped.setdefault(course_number, [])
        grouped[course_number].append(course)
    return grouped


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
