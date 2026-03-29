"""CSC111 Project: simple web app for course pathway visualization."""

from __future__ import annotations

from pathlib import Path

from flask import Flask, render_template_string, request
import plotly.graph_objects as go

from course_dataset import load_course_catalog
from models import CourseProfessorRatings, normalize_course_number
from prerequisite_graph import (
    Recommendation,
    build_prerequisite_graph,
    get_target_plan_nodes,
    get_unlocked_courses,
    recommend_next_courses,
)
from rmp_course_dataset import load_course_professor_ratings_csv

RATINGS_PATH = Path("Datasets/CourseProfessorRatings.csv")


def _parse_completed_input(raw: str) -> set[str]:
    """Parse comma-separated course codes into normalized course numbers."""
    tokens = [token.strip() for token in raw.replace(";", ",").split(",")]
    return {normalize_course_number(token) for token in tokens if token.strip()}


def _course_average_rating(
    course_number: str, ratings_index: dict[str, CourseProfessorRatings]
) -> float:
    """Return weighted average rating for one course or 0.0 if missing."""
    item = ratings_index.get(course_number)
    if item is None or not item.professors_by_score:
        return 0.0
    total = 0.0
    count = 0
    for score, names in item.professors_by_score.items():
        total += score * len(names)
        count += len(names)
    return total / count if count > 0 else 0.0


def _rating_summary(
    course_number: str, ratings_index: dict[str, CourseProfessorRatings]
) -> str:
    """Return short rating summary text for hover display."""
    average = _course_average_rating(course_number, ratings_index)
    if average <= 0:
        return "N/A"
    return f"{average:.2f}"


def _build_node_positions(nodes: list[str]) -> dict[str, tuple[float, float]]:
    """Build simple layered positions by course level."""
    groups = {}
    for node in nodes:
        level = node[3] if len(node) > 3 and node[3].isdigit() else "0"
        groups.setdefault(level, [])
        groups[level].append(node)

    positions = {}
    sorted_levels = sorted(groups)
    for level_index, level in enumerate(sorted_levels):
        level_nodes = sorted(groups[level])
        total = max(1, len(level_nodes))
        for idx, node in enumerate(level_nodes):
            x = idx / (total - 1) if total > 1 else 0.5
            y = -level_index
            positions[node] = (x, y)
    return positions


def _build_plot_html(
    graph,
    completed_courses: set[str],
    unlocked_courses: set[str],
    target_nodes: set[str],
    target_course: str | None,
    ratings_index: dict[str, CourseProfessorRatings],
) -> str:
    """Build Plotly HTML for prerequisite graph."""
    nodes = sorted(graph.nodes())
    positions = _build_node_positions(nodes)

    edge_x = []
    edge_y = []
    for source, target in graph.edges():
        x0, y0 = positions[source]
        x1, y1 = positions[target]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        line={"width": 0.8, "color": "#888"},
        hoverinfo="none",
        mode="lines",
    )

    node_x = []
    node_y = []
    node_text = []
    node_color = []
    node_hover = []
    for node in nodes:
        x, y = positions[node]
        node_x.append(x)
        node_y.append(y)
        node_text.append(node)

        if target_course is not None and node == target_course:
            node_color.append("#f39c12")
        elif node in completed_courses:
            node_color.append("#2ecc71")
        elif node in target_nodes:
            node_color.append("#f1c40f")
        elif node in unlocked_courses:
            node_color.append("#3498db")
        else:
            node_color.append("#bdc3c7")

        node_hover.append(
            (
                f"{node}"
                f"<br>Prerequisites: {len(list(graph.predecessors(node)))}"
                f"<br>Unlocks: {len(list(graph.successors(node)))}"
                f"<br>Average Rating: {_rating_summary(node, ratings_index)}"
            )
        )

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=node_text,
        textposition="top center",
        hovertext=node_hover,
        hoverinfo="text",
        marker={
            "size": 12,
            "color": node_color,
            "line": {"width": 0.8, "color": "#333"},
        },
    )

    figure = go.Figure(data=[edge_trace, node_trace])
    figure.update_layout(
        title="CSC Course Prerequisite Graph",
        showlegend=False,
        hovermode="closest",
        margin={"b": 20, "l": 20, "r": 20, "t": 40},
        xaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
        yaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
    )
    return figure.to_html(full_html=False, include_plotlyjs="cdn")


def create_app() -> Flask:
    """Create and configure the Flask app."""
    app = Flask(__name__)

    catalog = load_course_catalog()
    graph = build_prerequisite_graph(catalog)

    if RATINGS_PATH.exists():
        ratings_index = load_course_professor_ratings_csv(RATINGS_PATH)
    else:
        ratings_index = {}

    @app.route("/", methods=["GET"])
    def index() -> str:
        completed_raw = request.args.get("completed", "")
        target_raw = request.args.get("target", "")

        completed_courses = {
            course for course in _parse_completed_input(completed_raw) if course in graph
        }
        target_course = normalize_course_number(target_raw) if target_raw.strip() else None
        if target_course and target_course not in graph:
            target_course = None

        unlocked_courses = get_unlocked_courses(completed_courses, graph)
        target_nodes = (
            get_target_plan_nodes(target_course, graph) if target_course is not None else set()
        )
        recommendations = recommend_next_courses(
            completed_courses=completed_courses,
            graph=graph,
            ratings_index=ratings_index,
            limit=12,
        )

        plot_html = _build_plot_html(
            graph=graph,
            completed_courses=completed_courses,
            unlocked_courses=unlocked_courses,
            target_nodes=target_nodes,
            target_course=target_course,
            ratings_index=ratings_index,
        )
        return render_template_string(
            """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CSC Pathway Planner</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; background: #f8f9fb; color: #202124; }
    h1 { margin-bottom: 8px; }
    .panel { background: white; border: 1px solid #ddd; border-radius: 8px; padding: 14px; margin-bottom: 16px; }
    form { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    input { padding: 8px; border: 1px solid #bbb; border-radius: 6px; min-width: 260px; }
    button { padding: 8px 12px; border: 0; background: #1f6feb; color: white; border-radius: 6px; cursor: pointer; }
    .legend span { display: inline-block; margin-right: 12px; font-size: 13px; }
    .dot { width: 11px; height: 11px; border-radius: 50%; display: inline-block; margin-right: 4px; vertical-align: middle; }
    ul { margin-top: 8px; }
    li { margin-bottom: 4px; }
  </style>
</head>
<body>
  <h1>CSC Pathway Planner</h1>
  <p>Enter completed courses and an optional target course. Example completed input: <code>CSC108, CSC148, CSC165</code></p>

  <div class="panel">
    <form method="get">
      <input name="completed" value="{{ completed_raw }}" placeholder="Completed courses (comma separated)">
      <input name="target" value="{{ target_raw }}" placeholder="Target course (optional, e.g. CSC373)">
      <button type="submit">Update</button>
    </form>
  </div>

  <div class="panel legend">
    <span><span class="dot" style="background:#2ecc71;"></span>Completed</span>
    <span><span class="dot" style="background:#3498db;"></span>Unlocked</span>
    <span><span class="dot" style="background:#f1c40f;"></span>Target Path</span>
    <span><span class="dot" style="background:#f39c12;"></span>Target</span>
    <span><span class="dot" style="background:#bdc3c7;"></span>Locked</span>
  </div>

  <div class="panel">
    <b>Graph Summary:</b>
    {{ graph_nodes }} nodes, {{ graph_edges }} prerequisite edges,
    {{ completed_count }} completed, {{ unlocked_count }} unlocked.
  </div>

  <div class="panel">
    <h3 style="margin-top: 0;">Recommended Next Courses</h3>
    {% if recommendations %}
    <ul>
      {% for rec in recommendations %}
      <li><b>{{ rec.course_number }}</b> | score {{ "%.2f"|format(rec.score) }} |
          avg rating {{ "%.2f"|format(rec.average_rating) if rec.average_rating > 0 else "N/A" }} |
          unlocks {{ rec.unlock_count }}</li>
      {% endfor %}
    </ul>
    {% else %}
    <p>No recommendations yet. Try marking some completed courses.</p>
    {% endif %}
  </div>

  <div class="panel">
    {{ plot_html|safe }}
  </div>
</body>
</html>
            """,
            completed_raw=completed_raw,
            target_raw=target_raw,
            graph_nodes=graph.number_of_nodes(),
            graph_edges=graph.number_of_edges(),
            completed_count=len(completed_courses),
            unlocked_count=len(unlocked_courses),
            recommendations=recommendations,
            plot_html=plot_html,
        )

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
