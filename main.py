"""CSC111 Project: setup demo entrypoint.

Current milestone:
- load the local course dataset from ``Datasets/CourseData.csv``
- load/build ``Datasets/CourseProfessorRatings.csv`` from local CSV data
"""

from __future__ import annotations

from course_dataset import build_course_number_index, load_course_catalog
from rmp_course_dataset import (
    build_and_save_ratings_dataset,
    load_ratings_csv,
)
from web_app import create_app


def run_local_dataset_summary() -> tuple[int, int]:
    """Return (catalog_size, unique_course_number_count)."""
    catalog = load_course_catalog()
    grouped = build_course_number_index(catalog)
    return len(catalog), len(grouped)


def run_build_rmp_dataset() -> tuple[int, int]:
    """Build ratings dataset and return (profile_count, rated_course_count).

    ``profile_count`` is 0 because live scraping is disabled.
    """
    catalog = load_course_catalog()
    grouped = build_course_number_index(catalog)
    course_numbers = set(grouped)

    rating_index, profile_count = build_and_save_ratings_dataset(
        course_numbers=course_numbers
    )
    return profile_count, len(rating_index)


def run_load_rmp_dataset_summary(
) -> tuple[int, int, dict[str, dict[float, list[str]]]]:
    """Return summary of existing ratings CSV with a 10-course sample."""
    rating_index = load_ratings_csv()
    non_empty = [
        code
        for code in sorted(rating_index)
        if rating_index[code].professors_by_score
    ]
    sample = {}
    for course_number in non_empty[:10]:
        ratings = rating_index[course_number].professors_by_score
        sample[course_number] = ratings
    return len(rating_index), len(non_empty), sample


def run_web_app() -> None:
    """Run the website locally."""
    app = create_app()
    port = 5055
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    run_web_app()
