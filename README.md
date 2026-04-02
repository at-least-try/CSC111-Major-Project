# CSC111 Major Project

Course pathway planner for UofT CS with prerequisite graph visualization and RateMyProf-based course rating signals.

## Project Structure

- `Datasets/CourseData.csv`: course and prerequisite dataset
- `Datasets/CourseProfessorRatings.csv`: generated course-to-professor ratings dataset
- `Datasets/ratemyprof_scraper.py`: RateMyProf scraping utilities
- `course_dataset.py`: loads and normalizes course dataset
- `rmp_course_dataset.py`: builds/loads ratings dataset
- `prerequisite_graph.py`: graph construction + unlock/recommendation logic
- `web_app.py`: Flask + Plotly web interface
- `main.py`: helper entrypoints
- `report/`: report template and working draft
- `Information/`: handout/proposal PDFs

## Setup

1. Install Python 3.13.5 (course target version).
2. Install dependencies:

```bash
python3 -m pip install --user -r requirements.txt
```

## Run

### 1. (Optional) Rebuild ratings dataset from live RateMyProf

```bash
python3 -c "from main import run_build_rmp_dataset; run_build_rmp_dataset()"
```

This writes `Datasets/CourseProfessorRatings.csv`.

### 2. Launch the website

```bash
python3 main.py
```

Open `http://127.0.0.1:5055`.

Note: if you open `http://127.0.0.1:5000` and see HTTP 403, that is a different local service already using port 5000.

Use:
- `completed`: comma-separated courses, e.g. `CSC108, CSC148, CSC165`
- `connected_only`: set to `1` to show only courses with graph connections

## Quick checks

- Dataset summary:

```bash
python3 -c "from main import run_local_dataset_summary; print(run_local_dataset_summary())"
```

- Ratings summary:

```bash
python3 -c "from main import run_load_rmp_dataset_summary; print(run_load_rmp_dataset_summary())"
```

## PythonTA

Run PythonTA with the project config:

```bash
python3 -m python_ta -c python_ta_config.cfg web_app.py prerequisite_graph.py course_dataset.py models.py rmp_course_dataset.py Datasets/ratemyprof_scraper.py main.py
```
