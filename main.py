"""CSC111 Project: setup demo entrypoint.

Current milestone:
- load the local course dataset from ``Datasets/CourseData.csv``
- scrape RateMyProf and build/load ``Datasets/CourseProfessorRatings.csv``
"""

from __future__ import annotations

from course_dataset import build_course_number_index, load_course_catalog
from rmp_course_dataset import (
    build_and_save_course_professor_ratings_dataset,
    load_course_professor_ratings_csv,
)
from web_app import create_app


def run_local_dataset_summary() -> None:
    """Print basic summary of the local course dataset."""
    catalog = load_course_catalog()
    grouped = build_course_number_index(catalog)
    print(f"Loaded {len(catalog)} courses from Datasets/CourseData.csv.")
    print(f"Unique normalized course numbers: {len(grouped)}.")


def run_build_rmp_dataset() -> None:
    """Build ratings dataset for all catalog course numbers and write CSV."""
    catalog = load_course_catalog()
    grouped = build_course_number_index(catalog)
    course_numbers = set(grouped)

    rating_index, profile_count = build_and_save_course_professor_ratings_dataset(
        course_numbers=course_numbers
    )
    print(f"Scraped {profile_count} professor profiles from RateMyProf.")
    print(f"Wrote Datasets/CourseProfessorRatings.csv for {len(rating_index)} courses.")


def run_load_rmp_dataset_summary() -> None:
    """Load existing ratings CSV and print a small sample."""
    rating_index = load_course_professor_ratings_csv()
    print(f"Loaded Datasets/CourseProfessorRatings.csv rows: {len(rating_index)}")
    non_empty = [c for c in sorted(rating_index) if rating_index[c].professors_by_score]
    print(f"Courses with at least one professor rating: {len(non_empty)}")
    for course_number in non_empty[:10]:
        ratings = rating_index[course_number].professors_by_score
        print(f"{course_number}: {ratings}")


def run_web_app() -> None:
    """Run the website locally."""
    app = create_app()
    app.run(debug=True)


if __name__ == "__main__":
    run_local_dataset_summary()

    # Uncomment to build the ratings dataset from live scraping:
    # run_build_rmp_dataset()

    # Uncomment to load/inspect an already-built ratings dataset:
    # run_load_rmp_dataset_summary()

    # Uncomment to run the web app:
    # run_web_app()
