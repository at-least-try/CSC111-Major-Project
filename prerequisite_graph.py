"""CSC111 Project: prerequisite graph and planning helpers.

This module keeps the graph/recommendation logic simple:
- one directed graph node per normalized course number (e.g. CSC148)
- directed edge A -> B means A is a prerequisite for B
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import networkx as nx

from models import Course, CourseProfessorRatings, normalize_course_number


@dataclass(frozen=True)
class Recommendation:
    """A single recommended next course with a simple score breakdown."""

    course_number: str
    score: float
    unlock_count: int
    average_rating: float


def build_prerequisite_graph(catalog: dict[str, Course]) -> nx.DiGraph:
    """Build a prerequisite graph from course catalog data."""
    graph = nx.DiGraph()
    for course in catalog.values():
        graph.add_node(normalize_course_number(course.course_code), requirements=[])

    for course in catalog.values():
        target = normalize_course_number(course.course_code)
        existing_requirements = graph.nodes[target].get("requirements", [])
        if not existing_requirements and course.prerequisite_groups:
            graph.nodes[target]["requirements"] = course.prerequisite_groups

        for group in course.prerequisite_groups:
            for option in group:
                for source in option:
                    if source in graph and source != target:
                        graph.add_edge(source, target)

    graph.graph["equivalent_map"] = _build_equivalent_map(catalog, set(graph.nodes))
    graph.graph["exclusion_map"] = build_exclusion_map(catalog, set(graph.nodes))

    return graph


def _requirements_met(
    prerequisite_groups: list[list[set[str]]], completed_courses: set[str]
) -> bool:
    """Return whether completed courses satisfy grouped prerequisite rules."""
    for group in prerequisite_groups:
        group_satisfied = False
        for option in group:
            if option.issubset(completed_courses):
                group_satisfied = True
                break
        if not group_satisfied:
            return False
    return True


def _build_equivalent_map(
    catalog: dict[str, Course], available_courses: set[str]
) -> dict[str, set[str]]:
    """Build map of equivalent-course sets from ``/`` prerequisite groups."""
    equivalent_map = {course: set() for course in available_courses}
    for course in catalog.values():
        for group in course.prerequisite_groups:
            group_courses = []
            for option in group:
                if len(option) == 1:
                    only_course = next(iter(option))
                    if only_course in available_courses:
                        group_courses.append(only_course)
            if len(group_courses) > 1:
                for first, second in combinations(sorted(set(group_courses)), 2):
                    equivalent_map[first].add(second)
                    equivalent_map[second].add(first)
    return equivalent_map


def build_exclusion_map(
    catalog: dict[str, Course], available_courses: set[str]
) -> dict[str, set[str]]:
    """Build map of course exclusions from catalog data."""
    exclusion_map = {course: set() for course in available_courses}
    for course in catalog.values():
        course_number = normalize_course_number(course.course_code)
        if course_number not in available_courses:
            continue
        for excluded in course.exclusion:
            if excluded in available_courses and excluded != course_number:
                exclusion_map[course_number].add(excluded)
                exclusion_map[excluded].add(course_number)
    return exclusion_map


def get_unlocked_courses(completed_courses: set[str], graph: nx.DiGraph) -> set[str]:
    """Return courses whose prerequisites are all completed."""
    unlocked = set()
    for course in graph.nodes:
        if course in completed_courses:
            continue
        requirements = graph.nodes[course].get("requirements", [])
        if _requirements_met(requirements, completed_courses):
            unlocked.add(course)
    return unlocked


def course_average_rating(
    course_number: str, ratings_index: dict[str, CourseProfessorRatings]
) -> float:
    """Return average score for one course from score buckets."""
    course_ratings = ratings_index.get(course_number)
    if course_ratings is None or not course_ratings.professors_by_score:
        return 0.0

    total = 0.0
    count = 0
    for score, names in course_ratings.professors_by_score.items():
        total += score * len(names)
        count += len(names)
    return total / count if count > 0 else 0.0


def recommend_next_courses(
    completed_courses: set[str],
    graph: nx.DiGraph,
    ratings_index: dict[str, CourseProfessorRatings],
    limit: int = 12,
) -> list[Recommendation]:
    """Recommend next courses using a simple score.

    Score = (average rating * 2.0) + unlock_count
    """
    unlocked = get_unlocked_courses(completed_courses, graph)
    equivalent_map = graph.graph.get("equivalent_map", {})
    exclusion_map = graph.graph.get("exclusion_map", {})
    excluded_courses = set()
    for completed in completed_courses:
        excluded_courses.update(exclusion_map.get(completed, set()))

    recommendations = []
    for course in unlocked:
        if course in excluded_courses:
            continue
        equivalent_courses = equivalent_map.get(course, set())
        if equivalent_courses.intersection(completed_courses):
            continue
        unlock_count = len(set(graph.successors(course)) - completed_courses)
        average_rating = course_average_rating(course, ratings_index)
        score = (average_rating * 2.0) + unlock_count
        recommendations.append(
            Recommendation(
                course_number=course,
                score=score,
                unlock_count=unlock_count,
                average_rating=average_rating,
            )
        )

    recommendations.sort(key=lambda rec: rec.score, reverse=True)
    return recommendations[:limit]


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
