"""CSC111 Project: RateMyProf scraping helpers.

These utilities scrape publicly rendered page payloads from RateMyProf and
parse the embedded ``window.__RELAY_STORE__`` JSON blob.
"""

from __future__ import annotations

import base64
import json
import string
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

from models import ProfessorProfile, normalize_course_number

DEFAULT_SCHOOL_LEGACY_ID = 1484  # U of T St. George
RMP_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
RMP_GRAPHQL_URL = "https://www.ratemyprofessors.com/graphql"
RMP_GRAPHQL_AUTH = "Basic dGVzdDp0ZXN0"
TEACHER_SEARCH_QUERY = """
query TeacherSearch($query: TeacherSearchQuery!, $count: Int!, $cursor: String) {
  newSearch {
    teachers(query: $query, first: $count, after: $cursor) {
      edges {
        cursor
        node {
          legacyId
          firstName
          lastName
          department
          avgRating
          numRatings
          courseCodes {
            courseName
            courseCount
          }
        }
      }
      pageInfo {
        hasNextPage
        endCursor
      }
    }
  }
}
"""


class RateMyProfScrapeError(RuntimeError):
    """Raised when scraping/parsing RateMyProf payloads fails."""


def _fetch_html(url: str, timeout: float = 20.0) -> str:
    """Fetch HTML using a browser-like user-agent."""
    request = urllib.request.Request(url=url, headers={"User-Agent": RMP_USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise

        # Local Python installations sometimes miss CA bundles.
        unverified_context = ssl.create_default_context()
        unverified_context.check_hostname = False
        unverified_context.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(
            request, timeout=timeout, context=unverified_context
        ) as response:
            return response.read().decode("utf-8", errors="replace")


def _extract_relay_store(page_html: str) -> dict:
    """Extract ``window.__RELAY_STORE__`` from a page."""
    marker = "window.__RELAY_STORE__ = "
    start = page_html.find(marker)
    if start == -1:
        raise RateMyProfScrapeError("Unable to locate relay store payload.")

    payload_start = start + len(marker)
    decoder = json.JSONDecoder()
    try:
        payload, _ = decoder.raw_decode(page_html[payload_start:])
    except json.JSONDecodeError as exc:
        raise RateMyProfScrapeError("Relay store payload is not valid JSON.") from exc

    if not isinstance(payload, dict):
        raise RateMyProfScrapeError("Unexpected relay store payload shape.")
    return payload


def _post_graphql(payload: dict, timeout: float = 25.0) -> dict:
    """POST a GraphQL request and return parsed JSON response."""
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url=RMP_GRAPHQL_URL,
        data=body,
        method="POST",
        headers={
            "User-Agent": RMP_USER_AGENT,
            "Content-Type": "application/json",
            "Authorization": RMP_GRAPHQL_AUTH,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib.error.URLError as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc):
            raise
        unverified_context = ssl.create_default_context()
        unverified_context.check_hostname = False
        unverified_context.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(
            request, timeout=timeout, context=unverified_context
        ) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))

    if not isinstance(data, dict):
        raise RateMyProfScrapeError("Unexpected GraphQL response shape.")
    if "errors" in data:
        raise RateMyProfScrapeError(f"GraphQL returned errors: {data['errors']}")
    return data


def _school_node_id_from_legacy(school_legacy_id: int) -> str:
    """Convert numeric school id to RateMyProf GraphQL node id."""
    raw = f"School-{school_legacy_id}".encode("utf-8")
    return base64.b64encode(raw).decode("utf-8")


def _teacher_school_legacy_id(teacher: dict, relay_store: dict) -> int | None:
    """Return a teacher's school legacy id if present."""
    school_ref = teacher.get("school", {}).get("__ref")
    if not isinstance(school_ref, str):
        return None
    school_entity = relay_store.get(school_ref, {})
    if isinstance(school_entity, dict):
        return school_entity.get("legacyId")
    return None


def _extract_course_numbers(teacher: dict, relay_store: dict) -> set[str]:
    """Return normalized course numbers from a teacher payload."""
    result = set()
    course_refs = teacher.get("courseCodes", {}).get("__refs", [])
    for ref in course_refs:
        course_entity = relay_store.get(ref, {})
        if not isinstance(course_entity, dict):
            continue
        raw_course_name = course_entity.get("courseName", "")
        if isinstance(raw_course_name, str) and raw_course_name.strip():
            result.add(normalize_course_number(raw_course_name))
    return result


def search_professors_by_name(
    query: str,
    school_legacy_id: int = DEFAULT_SCHOOL_LEGACY_ID,
    require_department_substring: str = "computer science",
    max_results: int = 15,
) -> list[ProfessorProfile]:
    """Search RateMyProf and return candidate professor summaries.

    The result list is sorted by number of ratings descending.
    """
    encoded_query = urllib.parse.quote_plus(query)
    search_url = (
        f"https://www.ratemyprofessors.com/search/professors/"
        f"{school_legacy_id}?q={encoded_query}"
    )
    relay_store = _extract_relay_store(_fetch_html(search_url))

    matches = []
    for entity in relay_store.values():
        if not isinstance(entity, dict):
            continue
        if entity.get("__typename") != "Teacher":
            continue

        department = str(entity.get("department", ""))
        if require_department_substring.lower() not in department.lower():
            continue
        if _teacher_school_legacy_id(entity, relay_store) != school_legacy_id:
            continue

        first_name = str(entity.get("firstName", "")).strip()
        last_name = str(entity.get("lastName", "")).strip()
        full_name = f"{first_name} {last_name}".strip()
        if not full_name:
            continue

        matches.append(
            ProfessorProfile(
                legacy_id=int(entity.get("legacyId", 0)),
                full_name=full_name,
                department=department,
                average_rating=float(entity.get("avgRating", 0.0)),
                num_ratings=int(entity.get("numRatings", 0)),
                course_numbers=set(),
            )
        )

    matches.sort(key=lambda prof: prof.num_ratings, reverse=True)
    return matches[:max_results]


def fetch_professor_profile(legacy_professor_id: int) -> ProfessorProfile:
    """Fetch one professor profile, including taught course numbers."""
    page_url = f"https://www.ratemyprofessors.com/professor/{legacy_professor_id}"
    relay_store = _extract_relay_store(_fetch_html(page_url))

    teacher_payload = None
    for entity in relay_store.values():
        if isinstance(entity, dict) and entity.get("__typename") == "Teacher":
            if int(entity.get("legacyId", -1)) == legacy_professor_id:
                teacher_payload = entity
                break

    if teacher_payload is None:
        raise RateMyProfScrapeError(
            f"Professor {legacy_professor_id} not found in profile payload."
        )

    first_name = str(teacher_payload.get("firstName", "")).strip()
    last_name = str(teacher_payload.get("lastName", "")).strip()
    full_name = f"{first_name} {last_name}".strip()

    return ProfessorProfile(
        legacy_id=legacy_professor_id,
        full_name=full_name,
        department=str(teacher_payload.get("department", "")),
        average_rating=float(teacher_payload.get("avgRating", 0.0)),
        num_ratings=int(teacher_payload.get("numRatings", 0)),
        course_numbers=_extract_course_numbers(teacher_payload, relay_store),
    )


def collect_professor_profiles(
    name_queries: list[str],
    school_legacy_id: int = DEFAULT_SCHOOL_LEGACY_ID,
    max_matches_per_query: int = 3,
    sleep_seconds: float = 0.5,
) -> list[ProfessorProfile]:
    """Search for professor names, then fetch full profiles for each unique match."""
    seen_legacy_ids = set()
    profiles = []

    for query in name_queries:
        try:
            matches = search_professors_by_name(
                query=query,
                school_legacy_id=school_legacy_id,
                max_results=max_matches_per_query,
            )
        except (RateMyProfScrapeError, urllib.error.URLError, ValueError):
            continue

        for match in matches:
            if match.legacy_id in seen_legacy_ids:
                continue
            try:
                full_profile = fetch_professor_profile(match.legacy_id)
            except (RateMyProfScrapeError, urllib.error.URLError, ValueError):
                continue
            profiles.append(full_profile)
            seen_legacy_ids.add(match.legacy_id)
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

    return profiles


def default_professor_query_seeds() -> list[str]:
    """Return simple query seeds for collecting many candidate professors.

    This is intentionally simple for CSC111 scope: single letters and a few
    common digraphs. It does not guarantee complete recall of all professors.
    """
    seeds = list(string.ascii_lowercase)
    seeds.extend(["an", "ch", "da", "jo", "li", "ma", "mi", "sa", "ya", "zh"])
    return seeds


def collect_professor_profiles_for_school_department(
    school_legacy_id: int = DEFAULT_SCHOOL_LEGACY_ID,
    department_substring: str = "computer science",
    page_size: int = 50,
    max_pages: int | None = 30,
    sleep_seconds: float = 0.2,
) -> list[ProfessorProfile]:
    """Collect professor profiles for one school/department via GraphQL pagination.

    This method is used for the project dataset build because it can gather
    many more professors than text search alone while still staying simple.
    """
    school_node_id = _school_node_id_from_legacy(school_legacy_id)
    cursor = ""
    page_count = 0
    department_filter = department_substring.lower()
    seen_legacy_ids = set()
    profiles = []

    while True:
        payload = {
            "query": TEACHER_SEARCH_QUERY,
            "variables": {
                "query": {
                    "schoolID": school_node_id,
                    "fallback": True,
                    "text": "",
                },
                "count": page_size,
                "cursor": cursor,
            },
        }
        response = _post_graphql(payload)
        teachers = (
            response.get("data", {})
            .get("newSearch", {})
            .get("teachers", {})
        )

        edges = teachers.get("edges", [])
        for edge in edges:
            node = edge.get("node", {})
            if not isinstance(node, dict):
                continue
            legacy_id = int(node.get("legacyId", 0))
            if legacy_id <= 0 or legacy_id in seen_legacy_ids:
                continue
            department = str(node.get("department", ""))
            if department_filter not in department.lower():
                continue

            first_name = str(node.get("firstName", "")).strip()
            last_name = str(node.get("lastName", "")).strip()
            full_name = f"{first_name} {last_name}".strip()
            if not full_name:
                continue

            course_numbers = set()
            for item in node.get("courseCodes", []):
                if isinstance(item, dict):
                    raw_course = str(item.get("courseName", "")).strip()
                    if raw_course:
                        course_numbers.add(normalize_course_number(raw_course))

            profiles.append(
                ProfessorProfile(
                    legacy_id=legacy_id,
                    full_name=full_name,
                    department=department,
                    average_rating=float(node.get("avgRating", 0.0)),
                    num_ratings=int(node.get("numRatings", 0)),
                    course_numbers=course_numbers,
                )
            )
            seen_legacy_ids.add(legacy_id)

        page_info = teachers.get("pageInfo", {})
        has_next_page = bool(page_info.get("hasNextPage"))
        cursor = str(page_info.get("endCursor", ""))
        page_count += 1
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

        if not has_next_page or not cursor:
            break
        if max_pages is not None and page_count >= max_pages:
            break

    profiles.sort(key=lambda prof: prof.num_ratings, reverse=True)
    return profiles
