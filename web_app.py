"""CSC111 Project: simple web app for course pathway visualization."""

from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, render_template_string, request
import plotly.graph_objects as go

from course_dataset import load_course_catalog
from models import CourseProfessorRatings, normalize_course_number
from prerequisite_graph import (
    build_prerequisite_graph,
    course_average_rating,
    get_unlocked_courses,
    recommend_next_courses,
)
from rmp_course_dataset import load_course_professor_ratings_csv

PROJECT_ROOT = Path(__file__).resolve().parent
RATINGS_PATH = PROJECT_ROOT / "Datasets" / "CourseProfessorRatings.csv"


def _parse_completed_input(raw: str) -> set[str]:
    """Parse comma-separated course codes into normalized course numbers."""
    tokens = [token.strip() for token in raw.replace(";", ",").split(",")]
    return {normalize_course_number(token) for token in tokens if token.strip()}


def _format_prerequisite_groups(
    prerequisite_groups: list[list[set[str]]], completed_courses: set[str]
) -> str:
    """Return HTML text for grouped prerequisites with completion coloring."""
    if not prerequisite_groups:
        return "None"

    group_lines = []
    for index, group in enumerate(prerequisite_groups, start=1):
        group_has_completed_course = False
        option_html = []
        for option in group:
            is_option_met = option.issubset(completed_courses)
            option_color = "#1f8f3a" if is_option_met else "#c62828"
            token_html = []
            for course in sorted(option):
                is_completed = course in completed_courses
                if is_completed:
                    group_has_completed_course = True
                token_color = "#1f8f3a" if is_completed else "#c62828"
                token_html.append(f"<span style='color:{token_color};'>{course}</span>")
            option_text = " &amp; ".join(token_html)
            option_html.append(f"<span style='color:{option_color};'><b>{option_text}</b></span>")

        group_bg = "#e6f4ea" if group_has_completed_course else "#fdecea"
        group_border = "#81c995" if group_has_completed_course else "#f28b82"
        group_line = (
            f"<span style='display:inline-block;padding:2px 6px;border-radius:6px;"
            f"background:{group_bg};border:1px solid {group_border};'>"
            f"G{index}: {' <b> OR </b> '.join(option_html)}</span>"
        )
        group_lines.append(group_line)

    return "<br>".join(group_lines)


def _course_year(course_number: str) -> int:
    """Return course year inferred from first digit in code."""
    for char in course_number:
        if char.isdigit():
            return int(char)
    return 0


def _build_excluded_by(
    completed_courses: set[str], exclusion_map: dict[str, set[str]]
) -> dict[str, set[str]]:
    """Return a map: course -> completed courses that exclude it."""
    excluded_by = {}
    for origin in completed_courses:
        for excluded in exclusion_map.get(origin, set()):
            if excluded == origin:
                continue
            excluded_by.setdefault(excluded, set()).add(origin)
    return excluded_by


def _spread_layer_nodes(layer_nodes: list[str]) -> dict[str, float]:
    """Return evenly spaced x-positions in [0, 1] for one row of nodes."""
    if not layer_nodes:
        return {}
    if len(layer_nodes) == 1:
        return {layer_nodes[0]: 0.5}

    margin = 0.06
    gap = (1.0 - 2 * margin) / (len(layer_nodes) - 1)
    return {node: margin + index * gap for index, node in enumerate(layer_nodes)}


def _average_x(neighbors: list[str], x_positions: dict[str, float], fallback: float) -> float:
    """Return average x-position for neighbors or fallback if empty."""
    if not neighbors:
        return fallback
    return sum(x_positions.get(node, 0.5) for node in neighbors) / len(neighbors)


def _build_node_positions(graph, nodes: list[str]) -> dict[str, tuple[float, float]]:
    """Build layered positions by year using a simple crossing-reduction pass."""
    rows = {}
    for node in nodes:
        year = _course_year(node)
        rows.setdefault(year, []).append(node)

    years = sorted(rows)
    ordered_rows = {year: sorted(rows[year]) for year in years}

    x_positions = {}
    for year in years:
        x_positions.update(_spread_layer_nodes(ordered_rows[year]))

    for _ in range(6):
        for year in years:
            reordered = sorted(
                ordered_rows[year],
                key=lambda node: (
                    _average_x(
                        list(graph.predecessors(node)),
                        x_positions,
                        x_positions.get(node, 0.5),
                    ),
                    node,
                ),
            )
            ordered_rows[year] = reordered
            x_positions.update(_spread_layer_nodes(reordered))

        for year in reversed(years):
            reordered = sorted(
                ordered_rows[year],
                key=lambda node: (
                    _average_x(
                        list(graph.successors(node)),
                        x_positions,
                        x_positions.get(node, 0.5),
                    ),
                    node,
                ),
            )
            ordered_rows[year] = reordered
            x_positions.update(_spread_layer_nodes(reordered))

    positions = {}
    max_year = max(years) if years else 0
    for year in years:
        y = (max_year - year) * 1.55
        for node in ordered_rows[year]:
            positions[node] = (x_positions[node], y)
    return positions


def _build_plot_html(
    graph,
    completed_courses: set[str],
    unlocked_courses: set[str],
    ratings_index: dict[str, CourseProfessorRatings],
    excluded_by: dict[str, set[str]],
) -> str:
    """Build Plotly HTML for prerequisite graph."""
    nodes = sorted(graph.nodes())
    positions = _build_node_positions(graph, nodes)

    edge_traces = []
    for source, target in sorted(graph.edges()):
        x0, y0 = positions[source]
        x1, y1 = positions[target]
        edge_traces.append(
            go.Scatter(
                x=[x0, x1],
                y=[y0, y1],
                line={
                    "width": 1.0,
                    "color": "rgba(120, 120, 120, 0.45)",
                },
                visible=False,
                meta={"source": source, "target": target},
                hoverinfo="none",
                mode="lines",
            )
        )

    node_x = []
    node_y = []
    node_labels = []
    node_codes = []
    node_color = []
    node_hover = []
    for node in nodes:
        x, y = positions[node]
        node_x.append(x)
        node_y.append(y)
        node_codes.append(node)

        is_completed = node in completed_courses
        is_excluded = node in excluded_by and node not in completed_courses
        if is_completed:
            node_color.append("#1b8f3f")
            node_labels.append(node)
            status = "Completed"
        elif is_excluded:
            node_color.append("#d9534f")
            node_labels.append(f"{node}<br>EXCLUDED")
            excluded_from = ", ".join(sorted(excluded_by.get(node, set())))
            status = f"Excluded by: {excluded_from}"
        elif node in unlocked_courses:
            node_color.append("#3498db")
            node_labels.append(node)
            status = "Unlocked"
        else:
            node_color.append("#bdc3c7")
            node_labels.append(node)
            status = "Locked"

        average_rating = course_average_rating(node, ratings_index)
        rating_text = f"{average_rating:.2f}" if average_rating > 0 else "N/A"

        node_hover.append(
            (
                f"{node}"
                f"<br>Status: {status}"
                f"<br>Prerequisites: {len(list(graph.predecessors(node)))}"
                f"<br>Unlocks: {len(list(graph.successors(node)))}"
                f"<br>Average Rating: {rating_text}"
                f"<br><br><b>Requirement Groups</b><br>"
                f"{_format_prerequisite_groups(graph.nodes[node].get('requirements', []), completed_courses)}"
            )
        )

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=node_labels,
        customdata=node_codes,
        textposition="top center",
        hovertext=node_hover,
        hoverinfo="text",
        marker={
            "size": 16,
            "color": node_color,
            "line": {"width": 1.0, "color": "#2f2f2f"},
        },
        textfont={"size": 11},
    )

    figure = go.Figure(data=[*edge_traces, node_trace])
    year_rows = sorted({_course_year(node) for node in nodes})
    max_year = max(year_rows) if year_rows else 0
    row_annotations = []
    for year in year_rows:
        y = (max_year - year) * 1.55
        row_annotations.append(
            {
                "x": -0.02,
                "y": y,
                "text": f"{year}00 level",
                "showarrow": False,
                "font": {"size": 11, "color": "#5f6368"},
                "xanchor": "right",
                "yanchor": "middle",
            }
        )

    figure.update_layout(
        title="CSC Course Prerequisite Graph",
        showlegend=False,
        hovermode="closest",
        clickmode="event",
        margin={"b": 20, "l": 40, "r": 20, "t": 45},
        xaxis={
            "showgrid": False,
            "zeroline": False,
            "showticklabels": False,
            "range": [-0.06, 1.03],
        },
        yaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
        annotations=row_annotations,
    )
    return figure.to_html(
        full_html=False,
        include_plotlyjs="cdn",
        div_id="course-graph",
    )


def _connected_subgraph(graph):
    """Return subgraph containing only nodes with at least one edge."""
    connected_nodes = [node for node in graph.nodes if graph.degree(node) > 0]
    return graph.subgraph(connected_nodes).copy()


def _serialize_completed(completed_courses: set[str]) -> str:
    """Serialize completed course set to comma-separated string."""
    return ",".join(sorted(completed_courses))


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
        connected_only = request.args.get("connected_only", "0") == "1"

        completed_courses = {
            course for course in _parse_completed_input(completed_raw) if course in graph
        }
        exclusion_map = graph.graph.get("exclusion_map", {})
        excluded_by = _build_excluded_by(completed_courses, exclusion_map)
        blocked_courses = {
            course
            for course, origins in excluded_by.items()
            if origins and course not in completed_courses
        }

        unlocked_courses = get_unlocked_courses(completed_courses, graph) - blocked_courses
        recommendations = recommend_next_courses(
            completed_courses=completed_courses,
            graph=graph,
            ratings_index=ratings_index,
            limit=12,
        )
        recommendations = [
            rec for rec in recommendations if rec.course_number not in blocked_courses
        ]
        display_graph = _connected_subgraph(graph) if connected_only else graph

        plot_html = _build_plot_html(
            graph=display_graph,
            completed_courses=completed_courses,
            unlocked_courses=unlocked_courses,
            ratings_index=ratings_index,
            excluded_by=excluded_by,
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
    form { margin: 0; }
    .legend span { display: inline-block; margin-right: 12px; font-size: 13px; }
    .dot { width: 11px; height: 11px; border-radius: 50%; display: inline-block; margin-right: 4px; vertical-align: middle; }
    ul { margin-top: 8px; }
    li { margin-bottom: 4px; }
  </style>
</head>
<body>
  <h1>CSC Pathway Planner</h1>
  <p>Click course nodes to mark completed/incomplete.</p>

  <div class="panel legend">
    <span><span class="dot" style="background:#1b8f3f;"></span>Completed</span>
    <span><span class="dot" style="background:#d9534f;"></span>Excluded</span>
    <span><span class="dot" style="background:#3498db;"></span>Unlocked</span>
    <span><span class="dot" style="background:#bdc3c7;"></span>Locked</span>
  </div>

  <div class="panel">
    <b>Graph Summary:</b>
    {{ graph_nodes }} nodes, {{ graph_edges }} prerequisite edges,
    {{ completed_count }} completed, {{ unlocked_count }} unlocked,
    {{ excluded_count }} excluded.
  </div>

  <div class="panel">
    <form method="get" id="control-form">
      <input type="hidden" id="completed-input" name="completed" value="{{ completed_csv }}">
      <input type="hidden" id="connected-only-input" name="connected_only" value="{{ '1' if connected_only else '0' }}">
    </form>
    <div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin-bottom:8px;">
      <b>Graph View</b>
      <label style="font-size:13px;display:flex;align-items:center;gap:6px;">
        <input type="checkbox" id="connected-only-checkbox" {% if connected_only %}checked{% endif %}>
        Show only connected courses
      </label>
    </div>
    <p id="status-message" style="min-height:16px;margin:0 0 8px 0;font-size:12px;color:#5f6368;">
      Click a node once to show links (red = prerequisites, green = unlocks). Click the same node again to toggle completion.
    </p>
    {{ plot_html|safe }}
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

  <script>
    (function () {
      const graphDiv = document.getElementById("course-graph");
      const form = document.getElementById("control-form");
      const completedInput = document.getElementById("completed-input");
      const connectedOnlyCheckbox = document.getElementById("connected-only-checkbox");
      const connectedOnlyInput = document.getElementById("connected-only-input");
      const connectedStorageKey = "csc111_connected_only";
      const completedStorageKey = "csc111_completed_courses";
      const selectedNodeStorageKey = "csc111_selected_node";
      const blockedCourses = new Set({{ blocked_courses_json|safe }});
      const statusMessage = document.getElementById("status-message");
      let selectedNode = localStorage.getItem(selectedNodeStorageKey);
      let suppressNextDocumentClear = false;
      if (!graphDiv || !form || !completedInput || !connectedOnlyCheckbox || !connectedOnlyInput || !graphDiv.on) {
        return;
      }
      const defaultStatusText = "Click a node once to show links (red = prerequisites, green = unlocks). Click the same node again to toggle completion.";
      const nodeTraceIndex = graphDiv.data.length - 1;
      const nodeTrace = graphDiv.data[nodeTraceIndex];
      const nodeCodes = Array.isArray(nodeTrace.customdata) ? nodeTrace.customdata : [];
      const nodeIndexByCode = new Map();
      nodeCodes.forEach(function (code, idx) { nodeIndexByCode.set(code, idx); });
      const baseNodeColors = (
        nodeTrace.marker &&
        Array.isArray(nodeTrace.marker.color)
      ) ? [...nodeTrace.marker.color] : [];
      const baseNodeSizes = baseNodeColors.map(() => 16);
      const baseNodeOpacity = baseNodeColors.map(() => 1.0);
      const baseTextColors = baseNodeColors.map(() => "#202124");
      const fadedNodeColor = "#d7dbe1";
      const fadedTextColor = "#b0b7c3";
      if (selectedNode && !nodeIndexByCode.has(selectedNode)) {
        selectedNode = null;
        localStorage.removeItem(selectedNodeStorageKey);
      }

      function setStatus(text, color) {
        if (!statusMessage) {
          return;
        }
        statusMessage.textContent = text;
        statusMessage.style.color = color;
      }

      function parseCompleted(text) {
        const parts = text.split(",").map(x => x.trim()).filter(x => x.length > 0);
        return new Set(parts);
      }

      function serializeCompleted(setValue) {
        return Array.from(setValue).sort().join(",");
      }

      function setConnectionVisibility(activeNode) {
        if (!window.Plotly || !graphDiv.data || graphDiv.data.length <= 1) {
          return;
        }
        const edgeIndices = [];
        const visibleValues = [];
        const lineColors = [];
        const lineWidths = [];
        const connectedNodes = new Set();
        for (let i = 0; i < graphDiv.data.length - 1; i++) {
          const trace = graphDiv.data[i];
          const meta = trace.meta || {};
          let showEdge = false;
          if (activeNode !== null && meta.target === activeNode) {
            showEdge = true;
            connectedNodes.add(meta.source);
            lineColors.push("#d9534f");
            lineWidths.push(2.0);
          } else if (activeNode !== null && meta.source === activeNode) {
            showEdge = true;
            connectedNodes.add(meta.target);
            lineColors.push("#2e7d32");
            lineWidths.push(2.0);
          } else {
            lineColors.push("rgba(120, 120, 120, 0.45)");
            lineWidths.push(1.0);
          }
          edgeIndices.push(i);
          visibleValues.push(showEdge);
        }
        if (edgeIndices.length > 0) {
          window.Plotly.restyle(
            graphDiv,
            {"visible": visibleValues, "line.color": lineColors, "line.width": lineWidths},
            edgeIndices
          );
        }

        const nodeColors = [...baseNodeColors];
        const nodeSizes = [...baseNodeSizes];
        const nodeOpacity = [...baseNodeOpacity];
        const textColors = [...baseTextColors];
        if (activeNode !== null) {
          const focusNodes = new Set(connectedNodes);
          focusNodes.add(activeNode);
          for (let i = 0; i < nodeOpacity.length; i++) {
            const code = nodeCodes[i];
            if (!focusNodes.has(code)) {
              nodeColors[i] = fadedNodeColor;
              textColors[i] = fadedTextColor;
              nodeOpacity[i] = 0.28;
            } else {
              nodeColors[i] = baseNodeColors[i];
              textColors[i] = baseTextColors[i];
              nodeOpacity[i] = 1.0;
            }
          }
        }

        if (nodeTraceIndex >= 0) {
          window.Plotly.restyle(
            graphDiv,
            {
              "marker.color": [nodeColors],
              "marker.size": [nodeSizes],
              "marker.opacity": [nodeOpacity],
              "textfont.color": [textColors]
            },
            [nodeTraceIndex]
          );
        }
      }

      function clearSelectedNodeAndHideLines() {
        selectedNode = null;
        localStorage.removeItem(selectedNodeStorageKey);
        setConnectionVisibility(null);
        setStatus(defaultStatusText, "#5f6368");
      }

      let shouldSubmit = false;
      const urlParams = new URLSearchParams(window.location.search);
      if (urlParams.has("completed")) {
        localStorage.setItem(completedStorageKey, completedInput.value);
      } else {
        const savedCompleted = localStorage.getItem(completedStorageKey);
        if (savedCompleted !== null && savedCompleted !== completedInput.value) {
          completedInput.value = savedCompleted;
          shouldSubmit = true;
        }
      }

      if (urlParams.has("connected_only")) {
        localStorage.setItem(connectedStorageKey, connectedOnlyCheckbox.checked ? "1" : "0");
      } else {
        const savedConnected = localStorage.getItem(connectedStorageKey);
        if (savedConnected === "0" || savedConnected === "1") {
          const savedChecked = savedConnected === "1";
          if (savedChecked !== connectedOnlyCheckbox.checked) {
            connectedOnlyCheckbox.checked = savedChecked;
            connectedOnlyInput.value = savedChecked ? "1" : "0";
            shouldSubmit = true;
          }
        }
      }

      if (shouldSubmit) {
        form.submit();
        return;
      }

      if (selectedNode) {
        setConnectionVisibility(selectedNode);
        setStatus(
          "Showing links for " + selectedNode + " (red = prerequisites, green = unlocks). Click again to toggle completion.",
          "#5f6368"
        );
      } else {
        setConnectionVisibility(null);
        setStatus(defaultStatusText, "#5f6368");
      }

      connectedOnlyCheckbox.addEventListener("change", function () {
        connectedOnlyInput.value = connectedOnlyCheckbox.checked ? "1" : "0";
        localStorage.setItem(connectedStorageKey, connectedOnlyInput.value);
        form.submit();
      });

      graphDiv.on("plotly_click", function (eventData) {
        suppressNextDocumentClear = true;
        window.setTimeout(function () { suppressNextDocumentClear = false; }, 0);

        if (!eventData || !eventData.points || eventData.points.length === 0) {
          return;
        }
        const clicked = eventData.points[0].customdata;
        if (!clicked) {
          return;
        }

        if (selectedNode !== clicked) {
          selectedNode = clicked;
          localStorage.setItem(selectedNodeStorageKey, selectedNode);
          setConnectionVisibility(clicked);
          setStatus(
            "Showing links for " + clicked + " (red = prerequisites, green = unlocks). Click again to toggle completion.",
            "#5f6368"
          );
          return;
        }

        const completed = parseCompleted(completedInput.value);
        if (!completed.has(clicked) && blockedCourses.has(clicked)) {
          setStatus(clicked + " is excluded by a completed course.", "#b3261e");
          return;
        }

        localStorage.setItem(selectedNodeStorageKey, selectedNode);
        if (completed.has(clicked)) {
          completed.delete(clicked);
        } else {
          completed.add(clicked);
        }
        setStatus("Updating course completion...", "#5f6368");
        completedInput.value = serializeCompleted(completed);
        localStorage.setItem(completedStorageKey, completedInput.value);
        connectedOnlyInput.value = connectedOnlyCheckbox.checked ? "1" : "0";
        form.submit();
      });

      document.addEventListener("click", function (event) {
        if (suppressNextDocumentClear || selectedNode === null) {
          return;
        }
        const target = event.target;
        if (target instanceof Element) {
          const clickedNodePoint = target.closest(".point, .textpoint");
          if (clickedNodePoint && graphDiv.contains(clickedNodePoint)) {
            return;
          }
        }
        clearSelectedNodeAndHideLines();
      });
    })();
  </script>
</body>
</html>
            """,
            completed_csv=_serialize_completed(completed_courses),
            connected_only=connected_only,
            graph_nodes=display_graph.number_of_nodes(),
            graph_edges=display_graph.number_of_edges(),
            completed_count=len(completed_courses),
            unlocked_count=len(unlocked_courses),
            excluded_count=len(blocked_courses),
            recommendations=recommendations,
            plot_html=plot_html,
            blocked_courses_json=json.dumps(sorted(blocked_courses)),
        )

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5050, debug=False, use_reloader=False)
