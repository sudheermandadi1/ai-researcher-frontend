
import uuid

import requests
import streamlit as st


BACKEND_BASE_URL = (
    "https://eonjx2ovw4.execute-api.eu-central-1.amazonaws.com"
)

RESEARCH_URL = f"{BACKEND_BASE_URL}/research"
WORKFLOW_URL = f"{BACKEND_BASE_URL}/workflow"
HEALTH_URL = f"{BACKEND_BASE_URL}/health"

REQUEST_TIMEOUT = 25


st.set_page_config(
    page_title="AI Research Assistant",
    page_icon="🔬",
    layout="wide",
)


# --------------------------------------------------
# 1. Session ID Management
# --------------------------------------------------

if "session_id" not in st.session_state:
    url_session_id = st.query_params.get("session_id")

    if url_session_id:
        st.session_state.session_id = url_session_id
    else:
        new_id = str(uuid.uuid4())
        st.session_state.session_id = new_id
        st.query_params["session_id"] = new_id


if "messages" not in st.session_state:
    st.session_state.messages = []

if "original_topic" not in st.session_state:
    st.session_state.original_topic = ""

if "previous_result" not in st.session_state:
    st.session_state.previous_result = None


# --------------------------------------------------
# 2. API Helper Functions
# --------------------------------------------------

def check_backend_health():
    try:
        response = requests.get(
            HEALTH_URL,
            timeout=10,
        )

        response.raise_for_status()

        return response.json().get("status") == "ok"

    except requests.RequestException:
        return False


def get_workflow(session_id):
    response = requests.get(
        f"{WORKFLOW_URL}/{session_id}",
        timeout=15,
    )

    if response.status_code == 404:
        return None

    response.raise_for_status()
    return response.json()


def call_research_api(user_response: str):
    payload = {
        "session_id": st.session_state.session_id,
        "user_input": user_response,
        "recipient_email": None,
    }

    response = requests.post(
        RESEARCH_URL,
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    return response.json()


def send_report_email(recipient_email: str):
    payload = {
        "session_id": st.session_state.session_id,
        "user_input": "",
        "recipient_email": recipient_email,
    }

    response = requests.post(
        RESEARCH_URL,
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    return response.json()


# --------------------------------------------------
# 3. Restore Previous Workflow
# --------------------------------------------------

if st.session_state.previous_result is None:
    try:
        data = get_workflow(st.session_state.session_id)

        if data:
            st.session_state.original_topic = data["original_topic"]
            st.session_state.previous_result = data["workflow"]

    except requests.RequestException as e:
        st.warning(f"Could not restore previous workflow: {e}")


# --------------------------------------------------
# 4. Display Workflow Results
# --------------------------------------------------

def display_workflow_result(workflow):

    status = workflow.get("status")

    if status == "needs_clarification":

        st.subheader("I need a little more information")

        questions = workflow.get("clarifying_questions", [])

        for index, question in enumerate(questions, start=1):
            st.markdown(f"**{index}.** {question}")

    elif status == "awaiting_selection":

        st.subheader("Proposed research searches")

        searches = workflow.get("proposed_searches", [])

        for search in searches:
            st.markdown(
                f"**Search {search['id']}**: {search['query']}"
            )

            st.caption(search.get("reason", ""))

        st.info(
            "Enter the IDs of the searches you want to approve. "
            "For example: 1, 2, 4"
        )

    elif status == "awaiting_email":

        st.success("Your research report is ready.")

        summary = workflow.get("short_summary", "")
        report = workflow.get("markdown_report", "")
        questions = workflow.get("follow_up_questions", [])

        if summary:
            st.subheader("Research summary")
            st.write(summary)

        if report:
            st.subheader("Complete research report")

            with st.expander("View complete report", expanded=True):
                st.markdown(report)

            st.download_button(
                label="Download Markdown report",
                data=report,
                file_name="research_report.md",
                mime="text/markdown",
            )

        if questions:
            st.subheader("Possible follow-up questions")

            for question in questions:
                st.markdown(f"- {question}")

    elif status == "completed":

        st.success("Research report email process completed.")

        email_status = workflow.get("email_status", "")

        if email_status:
            st.info(email_status)


# --------------------------------------------------
# 5. Main Layout and Sidebar
# --------------------------------------------------

st.title("🔬 AI Research Assistant")

st.write(
    "Enter a research topic. The AI agents will clarify your "
    "requirements, plan searches, conduct research, generate a "
    "report, and optionally email it to you as a PDF."
)


with st.sidebar:

    st.header("Backend Connection")

    if check_backend_health():
        st.success("Backend connected")
    else:
        st.error("Backend unavailable")

    st.divider()

    st.header("Workflow")

    st.caption(
        f"Session ID: `{st.session_state.session_id[:8]}...`"
    )

    if st.session_state.original_topic:

        st.write("**Research topic:**")

        st.write(st.session_state.original_topic)

    if st.button("Start a new research project"):

        new_id = str(uuid.uuid4())

        st.session_state.session_id = new_id
        st.query_params["session_id"] = new_id

        st.session_state.messages = []
        st.session_state.original_topic = ""
        st.session_state.previous_result = None

        st.rerun()


# --------------------------------------------------
# 6. Chat History
# --------------------------------------------------

for message in st.session_state.messages:

    with st.chat_message(message["role"]):
        st.markdown(message["content"])


current_status = None

if st.session_state.previous_result:

    current_status = st.session_state.previous_result.get("status")


# --------------------------------------------------
# 7. Email Delivery
# --------------------------------------------------

if current_status == "awaiting_email":

    st.divider()

    st.subheader("Email your research report")

    with st.form("email_form"):

        recipient_email = st.text_input(
            "Recipient email address",
            placeholder="example@email.com",
        )

        send_email = st.form_submit_button(
            "Generate PDF and send email"
        )

    if send_email:

        if not recipient_email.strip():

            st.error("Please enter an email address.")

        else:

            try:

                with st.spinner(
                    "Generating PDF and sending your research report..."
                ):

                    data = send_report_email(
                        recipient_email.strip()
                    )

                workflow = data["workflow"]

                st.session_state.previous_result = workflow

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": workflow.get(
                        "email_status",
                        "Email workflow completed.",
                    ),
                })

                st.rerun()

            except requests.HTTPError as e:

                st.error(
                    f"Backend HTTP error: {e.response.status_code}"
                )

                st.code(e.response.text)

            except requests.RequestException as e:

                st.error(f"Backend request failed: {e}")

            except Exception as e:

                st.error(f"Something went wrong: {e}")


# --------------------------------------------------
# 8. Research Chat
# --------------------------------------------------

elif current_status != "completed":

    user_input = st.chat_input(
        "Enter your research topic or response..."
    )

    if user_input:

        st.session_state.messages.append({
            "role": "user",
            "content": user_input,
        })

        try:

            with st.spinner(
                "AI agents are processing your request..."
            ):

                data = call_research_api(user_input)

            st.session_state.original_topic = data["original_topic"]

            workflow = data["workflow"]

            st.session_state.previous_result = workflow

            status = workflow.get("status", "")

            if status == "needs_clarification":

                assistant_message = (
                    "I need some additional information "
                    "before planning the research."
                )

            elif status == "awaiting_selection":

                assistant_message = (
                    "I have prepared the proposed searches. "
                    "Please select the searches you want me to use."
                )

            elif status == "awaiting_email":

                assistant_message = (
                    "The research report has been generated. "
                    "You can review it below and enter your email "
                    "address to receive the PDF."
                )

            elif status == "completed":

                assistant_message = (
                    workflow.get("email_status")
                    or "The workflow has been completed."
                )

            else:

                assistant_message = (
                    "The workflow returned an unknown status."
                )

            st.session_state.messages.append({
                "role": "assistant",
                "content": assistant_message,
            })

            st.rerun()

        except requests.HTTPError as e:

            st.error(
                f"Backend HTTP error: {e.response.status_code}"
            )

            st.code(e.response.text)

        except requests.RequestException as e:

            st.error(f"Backend request failed: {e}")

        except Exception as e:

            st.error(f"Something went wrong: {e}")


# --------------------------------------------------
# 9. Display Current Workflow Output
# --------------------------------------------------

if st.session_state.previous_result:

    st.divider()

    display_workflow_result(
        st.session_state.previous_result
    )
