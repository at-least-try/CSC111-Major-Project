"""CSC111 Project: dataset composition helpers."""

from __future__ import annotations

from models import Course, CourseProfessorRatings, ProfessorProfile, normalize_course_number


def build_course_professor_rating_index(
    professor_profiles: list[ProfessorProfile],
) -> dict[str, CourseProfessorRatings]:
    """Build mapping: ``course_number -> {score: [professor names]}``."""
    index = {}
    for professor in professor_profiles:
        for course_number in professor.course_numbers:
            normalized = normalize_course_number(course_number)
            index.setdefault(normalized, CourseProfessorRatings(course_number=normalized))
            index[normalized].add_professor(
                professor_name=professor.full_name,
                score=professor.average_rating,
            )
    return index


def filter_index_to_catalog(
    course_rating_index: dict[str, CourseProfessorRatings],
    course_catalog: dict[str, Course],
) -> dict[str, CourseProfessorRatings]:
    """Filter ratings index to course numbers present in the local course catalog."""
    available_course_numbers = {
        normalize_course_number(course.course_code) for course in course_catalog.values()
    }
    return {
        course_number: ratings
        for course_number, ratings in course_rating_index.items()
        if course_number in available_course_numbers
    }

