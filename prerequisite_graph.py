"""CSC111 Project: prerequisite graph and planning helpers.

This module keeps the graph/recommendation logic simple:
- one directed graph node per normalized course number (e.g. CSC148)
- directed edge A -> B means A is a prerequisite for B
"""

from __future__ import annotations

from dataclasses import dataclass

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
        graph.add_node(normalize_course_number(course.course_code))

    for course in catalog.values():
        target = normalize_course_number(course.course_code)
        for prereq in course.prerequisites:
            source = normalize_course_number(prereq)
            if source in graph and source != target:
                graph.add_edge(source, target)

    return graph


def get_unlocked_courses(completed_courses: set[str], graph: nx.DiGraph) -> set[str]:
    """Return courses whose prerequisites are all completed."""
    unlocked = set()
    for course in graph.nodes:
        if course in completed_courses:
            continue
        prerequisites = set(graph.predecessors(course))
        if prerequisites.issubset(completed_courses):
            unlocked.add(course)
    return unlocked


def get_target_plan_nodes(target_course: str, graph: nx.DiGraph) -> set[str]:
    """Return target and all prerequisite ancestors for that target."""
    if target_course not in graph:
        return set()
    return set(nx.ancestors(graph, target_course)) | {target_course}


def _course_average_rating(
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
    recommendations = []
    for course in unlocked:
        unlock_count = len(set(graph.successors(course)) - completed_courses)
        average_rating = _course_average_rating(course, ratings_index)
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

