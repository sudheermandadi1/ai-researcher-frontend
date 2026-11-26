
import uuid

import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="AI Research Assistant",
    page_icon="🔬",
    layout="wide",
)


# ============================================================
# CONFIGURATION
# ============================================================

try:
    BACKEND_URL = st.secrets["BACKEND_URL"].rstrip("/")
except (KeyError, FileNotFoundError):
    BACKEND_URL = "http://127.0.0.1:8000"

REQUEST_TIMEOUT = 60
REFRESH_INTERVAL = 5000

TERMINAL_STATUSES = {
    "completed",
    "failed",
}

SUPPORTED_STATUSES = {
    "queued",
    "running",
    "needs_clarification",
    "awaiting_selection",
    "awaiting_email",
    "completed",
    "failed",
}


# ============================================================
# API HELPERS
# ============================================================

def get_error_message(response):
    try:
        data = response.json()

        if isinstance(data, dict):
            detail = data.get("detail") or data.get("message")

            if detail:
                return str(detail)

        return response.text or f"HTTP {response.status_code}"

    except ValueError:
        return response.text or f"HTTP {response.status_code}"


def api_get(path):
    try:
        response = requests.get(
            f"{BACKEND_URL}{path}",
            timeout=REQUEST_TIMEOUT,
        )

        if not response.ok:
            raise requests.HTTPError(
                get_error_message(response),
                response=response,
            )

        return response.json()

    except requests.Timeout as exc:
        raise requests.Timeout(
            "The backend request timed out."
        ) from exc

    except requests.ConnectionError as exc:
        raise requests.ConnectionError(
            "Could not connect to the backend."
        ) from exc

    except ValueError as exc:
        raise ValueError(
            "The backend returned an invalid JSON response."
        ) from exc


def api_post(path, payload):
    try:
        response = requests.post(
            f"{BACKEND_URL}{path}",
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )

        if not response.ok:
            raise requests.HTTPError(
                get_error_message(response),
                response=response,
            )

        return response.json()

    except requests.Timeout as exc:
        raise requests.Timeout(
            "The backend request timed out."
        ) from exc

    except requests.ConnectionError as exc:
        raise requests.ConnectionError(
            "Could not connect to the backend."
        ) from exc

    except ValueError as exc:
        raise ValueError(
            "The backend returned an invalid JSON response."
        ) from exc


def get_idempotency_key(state_key):
    if state_key not in st.session_state:
        st.session_state[state_key] = str(uuid.uuid4())

    return st.session_state[state_key]


def clear_idempotency_key(state_key):
    st.session_state.pop(state_key, None)


def reset_workflow_session():
    st.session_state.session_id = None

    for key in (
        "clarification_idempotency_key",
        "selection_idempotency_key",
        "email_idempotency_key",
    ):
        clear_idempotency_key(key)


def display_api_error(exc):
    st.error(str(exc))


# ============================================================
# SESSION STATE
# ============================================================

if "session_id" not in st.session_state:
    st.session_state.session_id = None


# ============================================================
# HEADER
# ============================================================

st.title("🔬 AI Research Assistant")

st.caption(
    "Research planning, search approval, technical reports "
    "and email delivery."
)


# ============================================================
# NEW RESEARCH
# ============================================================

if not st.session_state.session_id:

    with st.form("research_form"):

        topic = st.text_area(
            "What would you like to research?",
            placeholder=(
                "Example: Compare modern LLM quantization "
                "methods and their deployment trade-offs."
            ),
            height=120,
        )

        submitted = st.form_submit_button(
            "Start Research",
            type="primary",
            use_container_width=True,
        )

    if submitted:

        topic = topic.strip()

        if len(topic) < 3:
            st.error(
                "Please enter a research topic containing "
                "at least 3 characters."
            )

        else:

            session_id = str(uuid.uuid4())

            try:
                result = api_post(
                    "/research",
                    {
                        "session_id": session_id,
                        "user_input": topic,
                    },
                )

                st.session_state.session_id = (
                    result["session_id"]
                )

                st.success(
                    result.get(
                        "message",
                        "Research submitted successfully.",
                    )
                )

                st.rerun()

            except requests.RequestException as exc:

                display_api_error(exc)

                st.warning(
                    "The request may have reached the backend. "
                    "Check the backend before submitting another "
                    "research request."
                )

            except ValueError as exc:
                display_api_error(exc)

            except (KeyError, TypeError):
                st.error(
                    "The backend returned an unexpected response."
                )

    st.stop()


# ============================================================
# WORKFLOW HEADER
# ============================================================

session_id = st.session_state.session_id

col1, col2 = st.columns([4, 1])

with col1:
    st.subheader("Research Conversation")

with col2:
    if st.button(
        "Refresh",
        use_container_width=True,
    ):
        st.rerun()


# ============================================================
# FETCH WORKFLOW DATA
# ============================================================

try:

    workflow_response = api_get(
        f"/workflow/{session_id}"
    )

    history_response = api_get(
        f"/workflow/{session_id}/messages"
    )

except (
    requests.RequestException,
    ValueError,
) as exc:

    display_api_error(exc)
    st.stop()


status = workflow_response.get("status")

workflow = (
    workflow_response.get("workflow")
    or {}
)


if status not in SUPPORTED_STATUSES:

    st.error(
        f"Unexpected workflow status: {status}"
    )

    st.stop()


# ============================================================
# WORKFLOW STATUS
# ============================================================

status_colors = {
    "queued": "🟡",
    "running": "🔵",
    "needs_clarification": "🟠",
    "awaiting_selection": "🟠",
    "awaiting_email": "🟠",
    "completed": "🟢",
    "failed": "🔴",
}

st.caption(
    f"Status: {status_colors.get(status, '⚪')} **{status}**"
)


# ============================================================
# CHAT HISTORY
# ============================================================

st.divider()

st.subheader("Conversation")

messages = history_response.get("messages", [])

if not messages:

    st.info(
        "No conversation messages are available yet."
    )

else:

    for message in messages:

        role = message.get("role", "assistant")

        with st.chat_message(
            "user" if role == "user" else "assistant"
        ):

            st.markdown(
                message.get("content", "")
            )


# ============================================================
# CLARIFICATION FORM
# ============================================================

if status == "needs_clarification":

    st.divider()

    st.subheader(
        "A few more details are needed"
    )

    questions = workflow.get(
        "clarifying_questions",
        [],
    )

    if not questions:

        st.warning(
            "The workflow requires clarification, "
            "but no questions were provided."
        )

    else:

        with st.form("clarification_form"):

            answers = []

            for index, question in enumerate(questions):

                answer = st.text_area(
                    question,
                    key=f"clarification_{session_id}_{index}",
                )

                answers.append(answer)

            submitted = st.form_submit_button(
                "Submit Answers",
                type="primary",
            )

        if submitted:

            if any(
                not answer.strip()
                for answer in answers
            ):

                st.error(
                    "Please answer every question."
                )

            else:

                key_name = "clarification_idempotency_key"

                payload = {
                    "answers": answers,
                    "idempotency_key": get_idempotency_key(
                        key_name
                    ),
                }

                try:

                    api_post(
                        f"/workflow/{session_id}/clarification",
                        payload,
                    )

                    clear_idempotency_key(key_name)

                    st.success(
                        "Clarification answers submitted."
                    )

                    st.rerun()

                except requests.RequestException as exc:

                    display_api_error(exc)

                    st.info(
                        "You can retry using the same "
                        "idempotency key."
                    )


# ============================================================
# SEARCH SELECTION
# ============================================================

elif status == "awaiting_selection":

    st.divider()

    st.subheader(
        "Approve Research Searches"
    )

    proposed_searches = workflow.get(
        "proposed_searches",
        [],
    )

    if not proposed_searches:

        st.warning(
            "No proposed searches were found."
        )

    else:

        with st.form("search_selection_form"):

            selected_ids = []

            for item in proposed_searches:

                selected = st.checkbox(
                    f'{item["id"]}. {item["query"]}',
                    value=True,
                    key=(
                        f'search_{session_id}_{item["id"]}'
                    ),
                )

                if item.get("reason"):

                    st.caption(
                        item["reason"]
                    )

                if selected:

                    selected_ids.append(
                        item["id"]
                    )

            submitted = st.form_submit_button(
                "Approve Selected Searches",
                type="primary",
            )

        if submitted:

            if not selected_ids:

                st.error(
                    "Select at least one search."
                )

            else:

                key_name = "selection_idempotency_key"

                payload = {
                    "selected_search_ids": selected_ids,
                    "idempotency_key": get_idempotency_key(
                        key_name
                    ),
                }

                try:

                    api_post(
                        f"/workflow/{session_id}/selection",
                        payload,
                    )

                    clear_idempotency_key(key_name)

                    st.success(
                        "Selected searches submitted."
                    )

                    st.rerun()

                except requests.RequestException as exc:

                    display_api_error(exc)

                    st.info(
                        "Retrying will reuse the same "
                        "idempotency key."
                    )


# ============================================================
# EXECUTIVE SUMMARY
# ============================================================

if workflow.get("short_summary"):

    st.divider()

    st.subheader(
        "Executive Summary"
    )

    st.markdown(
        workflow["short_summary"]
    )


# ============================================================
# RESEARCH REPORT
# ============================================================

if workflow.get("markdown_report"):

    st.divider()

    st.subheader(
        "Research Report"
    )

    st.markdown(
        workflow["markdown_report"]
    )

    st.download_button(
        "Download Markdown Report",
        data=workflow["markdown_report"],
        file_name="research_report.md",
        mime="text/markdown",
        use_container_width=True,
    )


# ============================================================
# FOLLOW-UP QUESTIONS
# ============================================================

follow_up_questions = workflow.get(
    "follow_up_questions",
    [],
)

if follow_up_questions:

    st.divider()

    st.subheader(
        "Suggested Follow-up Questions"
    )

    for question in follow_up_questions:

        st.markdown(
            f"- {question}"
        )


# ============================================================
# EMAIL CONFIRMATION
# ============================================================

if status == "awaiting_email":

    st.divider()

    st.subheader(
        "Email Research Report"
    )

    with st.form("email_form"):

        recipient = st.text_input(
            "Recipient email address",
        )

        confirm = st.checkbox(
            "I confirm that I want to send this report."
        )

        submitted = st.form_submit_button(
            "Send Research Report",
            type="primary",
        )

    if submitted:

        if not recipient.strip():

            st.error(
                "Enter a recipient email address."
            )

        elif not confirm:

            st.error(
                "Please confirm email delivery."
            )

        else:

            key_name = "email_idempotency_key"

            payload = {
                "recipient_email": recipient.strip(),
                "confirm_send": True,
                "idempotency_key": get_idempotency_key(
                    key_name
                ),
            }

            try:

                api_post(
                    f"/workflow/{session_id}/email",
                    payload,
                )

                clear_idempotency_key(key_name)

                st.success(
                    "Email delivery submitted."
                )

                st.rerun()

            except requests.RequestException as exc:

                display_api_error(exc)

                st.warning(
                    "If the request may have reached the backend, "
                    "retry using the same idempotency key."
                )


# ============================================================
# QUEUED / RUNNING / FAILED / COMPLETED
# ============================================================

if status in ("queued", "running"):

    st.info(
        "Your research is being processed."
    )

elif status == "completed":

    st.success(
        "Research workflow completed."
    )

elif status == "failed":

    st.error(
        workflow_response.get("error_message")
        or "The research workflow failed."
    )


# ============================================================
# AUTOMATIC REFRESH
# ============================================================

if status not in TERMINAL_STATUSES:

    st_autorefresh(
        interval=REFRESH_INTERVAL,
        key=f"workflow_auto_refresh_{session_id}",
    )


# ============================================================
# NEW RESEARCH SESSION
# ============================================================

st.divider()

if st.button(
    "Start a New Research Session",
    use_container_width=True,
):

    reset_workflow_session()

    st.rerun()
