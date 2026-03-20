"""
Hub BFF-backed generation flow for the Streamlit admin UI.
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable

import requests
import streamlit as st


REQUEST_TYPE_BY_LABEL: dict[str, str] = {
    "Teacher Guide": "lesson_plan",
    "Lesson Plan": "lesson_plan",
    "Worksheet": "summary",
    "Student Worksheet": "summary",
    "Exam Paper": "quiz",
    "Quiz": "quiz",
    "Summary": "summary",
}

TERMINAL_JOB_STATES = {
    "completed",
    "cancelled",
    "canceled",
    "failed",
    "error",
    "rejected",
    "success",
    "succeeded",
}

SUCCESS_JOB_STATES = {
    "completed",
    "success",
    "succeeded",
}


class HubBffError(RuntimeError):
    """Raised when the Hub BFF request fails."""


def map_output_label_to_request_type(label: str) -> str:
    """Map a UI label to the backend request_type enum deterministically."""
    try:
        return REQUEST_TYPE_BY_LABEL[label]
    except KeyError as exc:
        supported = ", ".join(sorted(REQUEST_TYPE_BY_LABEL))
        raise ValueError(
            f"Unsupported output label '{label}'. Supported labels: {supported}."
        ) from exc


def normalize_job_state(status: str | None) -> str:
    """Normalize job statuses for reliable comparisons."""
    return (status or "unknown").strip().lower().replace("-", "_").replace(" ", "_")


def is_terminal_job_state(status: str | None) -> bool:
    """Return True when the job reached a terminal state."""
    return normalize_job_state(status) in TERMINAL_JOB_STATES


def is_success_job_state(status: str | None) -> bool:
    """Return True when the job completed successfully."""
    return normalize_job_state(status) in SUCCESS_JOB_STATES


def build_generation_payload(
    curriculum_id: str,
    competency_ids: list[str],
    output_label: str,
    constraints: dict[str, Any],
) -> dict[str, Any]:
    """Build the request body expected by the Hub BFF."""
    cleaned_constraints = {
        key: value
        for key, value in constraints.items()
        if value not in (None, "", [])
    }
    return {
        "curriculum_id": curriculum_id,
        "request_type": map_output_label_to_request_type(output_label),
        "competency_ids": competency_ids or None,
        "constraints": cleaned_constraints,
    }


class HubBffClient:
    """Small client for the Hub BFF generation endpoints."""

    def __init__(
        self,
        api_base: str | None = None,
        timeout_seconds: int = 15,
        session: requests.Session | None = None,
    ) -> None:
        configured_base = api_base or _read_api_base()
        self.api_base = configured_base.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()

    def submit_generation_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.session.post(
            f"{self.api_base}/api/hub/generation/jobs",
            json=payload,
            timeout=self.timeout_seconds,
        )
        return self._parse_response(response, "submit generation job")

    def fetch_generation_job(self, job_id: str) -> dict[str, Any]:
        response = self.session.get(
            f"{self.api_base}/api/hub/generation/jobs/{job_id}",
            timeout=self.timeout_seconds,
        )
        return self._parse_response(response, "load generation job status")

    def _parse_response(self, response: requests.Response, action: str) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise HubBffError(
                f"Hub BFF could not {action}: non-JSON response ({response.status_code})."
            ) from exc

        if response.ok:
            return payload

        detail = (
            payload.get("detail")
            or payload.get("message")
            or payload.get("error")
            or f"HTTP {response.status_code}"
        )
        raise HubBffError(f"Hub BFF could not {action}: {detail}")


def render_generation_admin_flow(
    engine: Any,
    fetch_curricula: Callable[[Any], list[dict[str, Any]]],
    fetch_competencies: Callable[[Any, str], list[dict[str, Any]]],
) -> None:
    """Render the Hub BFF-backed generation workflow."""
    st.markdown("## ✨ Create Resources")
    st.caption("Submit generation jobs through Hub BFF and track them to completion.")
    st.markdown("---")

    try:
        curricula = fetch_curricula(engine)
    except Exception as exc:
        st.error(f"Could not load curricula: {exc}")
        return

    if not curricula:
        st.warning("No active curricula are available yet.")
        return

    curriculum_options = {
        f"{item['country']} • {item['subject']} {item['grade']}": item["id"]
        for item in curricula
    }
    selected_label = st.selectbox("Active Curriculum", list(curriculum_options.keys()))
    selected_curriculum_id = curriculum_options[selected_label]

    try:
        competencies = fetch_competencies(engine, selected_curriculum_id)
    except Exception as exc:
        st.error(f"Could not load competencies for the selected curriculum: {exc}")
        return

    if not competencies:
        st.warning("The selected curriculum has no competencies to generate from.")
        return

    competency_label_to_id = {item["title"]: item["id"] for item in competencies}
    selected_titles = st.multiselect(
        "Learning Objectives",
        options=list(competency_label_to_id.keys()),
        default=list(competency_label_to_id.keys()),
        help="Choose the competencies the generated artifact must cover.",
    )

    st.markdown("### Generation Request")
    output_label = st.selectbox(
        "Output Type",
        options=["Teacher Guide", "Worksheet", "Exam Paper"],
        help="These labels map deterministically to the backend request_type enum.",
    )
    mapped_request_type = map_output_label_to_request_type(output_label)
    st.caption(f"`{output_label}` → backend `request_type=\"{mapped_request_type}\"`")

    col1, col2 = st.columns(2)
    with col1:
        duration = st.text_input("Duration", placeholder="e.g., 45 minutes")
        difficulty_level = st.select_slider(
            "Target Proficiency",
            options=["Foundational", "Proficient", "Advanced", "Expert"],
            value="Proficient",
            help="Adjusts vocabulary complexity and depth of analysis.",
        )
    with col2:
        language = st.text_input("Language", value="English")
        offline_friendly = st.checkbox("Offline Friendly", value=False)

    submit_disabled = not selected_titles
    if submit_disabled:
        st.info("Select at least one learning objective before submitting a job.")

    if st.button(
        "🚀 Submit Generation Job",
        type="primary",
        use_container_width=True,
        disabled=submit_disabled,
    ):
        selected_competency_ids = [
            competency_label_to_id[title] for title in selected_titles
        ]
        payload = build_generation_payload(
            curriculum_id=selected_curriculum_id,
            competency_ids=selected_competency_ids,
            output_label=output_label,
            constraints={
                "duration": duration,
                "difficulty_level": difficulty_level,
                "language": language,
                "offline_friendly": offline_friendly,
            },
        )

        try:
            client = HubBffClient()
            submission = client.submit_generation_job(payload)
            job_id = submission.get("job_id") or submission.get("id")
            if not job_id:
                raise HubBffError("Hub BFF response did not include a job_id.")

            st.session_state["generation_job"] = {
                "job_id": job_id,
                "payload": payload,
                "last_response": submission,
                "status": submission.get("status", "submitted"),
            }
        except Exception as exc:
            st.error(f"❌ Generation job submission failed: {exc}")

    _render_job_status_panel()


def _render_job_status_panel() -> None:
    job = st.session_state.get("generation_job")
    if not job:
        return

    st.markdown("---")
    st.markdown("### Job Status")

    response = job.get("last_response", {})
    payload = job.get("payload", {})
    status = response.get("status") or job.get("status") or "submitted"
    job_id = job["job_id"]

    st.code(
        f"Job ID: {job_id}\n"
        f"Request Type: {payload.get('request_type', 'unknown')}\n"
        f"State: {status}"
    )

    col1, col2 = st.columns([2, 1])
    with col1:
        st.json(payload)
    with col2:
        if st.button("🔄 Refresh Status", use_container_width=True):
            _poll_job_until_terminal(job_id)

    normalized_status = normalize_job_state(status)
    if is_success_job_state(normalized_status):
        result = response.get("result") or response.get("artifact") or {}
        st.success("✅ Generation completed successfully.")
        if result:
            st.json(result)
    elif is_terminal_job_state(normalized_status):
        error_message = (
            response.get("error")
            or response.get("detail")
            or response.get("message")
            or "The job reached a terminal failure state."
        )
        st.error(f"❌ Generation failed: {error_message}")
    else:
        st.info("⏳ Generation is still running. Use refresh to poll again.")


def _poll_job_until_terminal(job_id: str, interval_seconds: int = 2, max_polls: int = 15) -> None:
    client = HubBffClient()
    status_box = st.empty()

    for attempt in range(1, max_polls + 1):
        try:
            response = client.fetch_generation_job(job_id)
        except Exception as exc:
            status_box.error(f"❌ Could not poll job status: {exc}")
            return

        status = response.get("status", "unknown")
        st.session_state["generation_job"] = {
            **st.session_state.get("generation_job", {}),
            "job_id": job_id,
            "status": status,
            "last_response": response,
        }

        if is_terminal_job_state(status):
            status_box.success(f"Polling finished with terminal state: {status}")
            st.rerun()

        status_box.info(f"Polling attempt {attempt}/{max_polls}: current state `{status}`")
        time.sleep(interval_seconds)

    status_box.warning(
        "Job is still in progress after the current polling window. Refresh status to continue polling."
    )


def _read_api_base() -> str:
    try:
        configured = st.secrets.get("api_base")
    except Exception:
        configured = None
    return configured or os.getenv("HUB_BFF_API_BASE") or "http://localhost:8000"
