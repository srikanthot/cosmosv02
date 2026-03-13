import os
import uuid
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

_backend_port = os.getenv("BACKEND_PORT", "8000")
BACKEND_URL = os.getenv("BACKEND_URL", f"http://localhost:{_backend_port}").strip().rstrip("/")
FRONTEND_TITLE = os.getenv("FRONTEND_TITLE", "PSEG Tech Manual Chatbot Prototype")
APP_VERSION = "frontend-json-v3"
FEEDBACK_FORM_URL = os.getenv("FEEDBACK_FORM_URL", "").strip()

st.set_page_config(
    page_title=FRONTEND_TITLE,
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    :root {
        --navy: #1e3a5f;
        --navy-light: #2d5a87;
        --orange: #f26522;
        --bg: #f7f9fc;
        --card: #ffffff;
        --border: #e2e8f0;
    }

    .stApp {
        background: var(--bg) !important;
    }

    .main .block-container {
        padding: 1.2rem 1.5rem 2rem !important;
        max-width: 1150px;
    }

    section[data-testid="stSidebar"] {
        width: 280px !important;
        min-width: 280px !important;
        max-width: 280px !important;
        background: var(--card) !important;
        border-right: 1px solid #edf2f7;
    }

    [data-testid="stSidebarContent"] {
        padding-top: 1rem !important;
        padding-left: 0.9rem !important;
        padding-right: 0.9rem !important;
    }

    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatar-user"]) {
        background: linear-gradient(135deg, #eef4fb, #e3ecf7);
        border: 1px solid #d0dff0;
        border-left: 4px solid #4a90d9;
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin: 0.5rem 0;
    }

    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatar-assistant"]) {
        background: var(--card);
        border: 1px solid var(--border);
        border-left: 4px solid var(--navy);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin: 0.5rem 0;
    }

    [data-testid="stChatInput"] {
        border: 2px solid var(--border) !important;
        border-radius: 12px !important;
    }

    [data-testid="stChatInput"]:focus-within {
        border-color: var(--navy) !important;
    }

    .stButton > button {
        background: linear-gradient(135deg, var(--navy), var(--navy-light));
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
    }

    .feedback-box {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 0.75rem;
        margin-top: 0.5rem;
    }

    .feedback-link a {
        display: inline-block;
        background: #f26522;
        color: white !important;
        text-decoration: none;
        padding: 0.55rem 0.9rem;
        border-radius: 8px;
        font-weight: 600;
        margin-top: 0.45rem;
    }

    hr {
        border: none;
        height: 1px;
        background: #edf2f7;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = []

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())


def render_citations(citations: list) -> None:
    with st.expander(f"📚 Sources ({len(citations)})", expanded=False):
        for i, c in enumerate(citations, 1):
            source = c.get("source", "Unknown")
            title = c.get("title", "")
            section = c.get("section", "")
            page = c.get("page", "")
            url = c.get("url", "")
            chunk_id = c.get("chunk_id", "")

            display_name = title if title else source
            label = f"**{i}.** {display_name}"

            if title and title != source:
                label += f"  _(file: {source})_"
            if section:
                label += f"\n\n> {section}"
            if page:
                label += f" — p.{page}"
            if chunk_id:
                label += f"  `{chunk_id}`"

            if url:
                st.markdown(f"{label}  \n[View source]({url})")
            else:
                st.markdown(label)


def render_history() -> None:
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("citations"):
                render_citations(msg["citations"])


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("""
        <div style="text-align:center; padding: 0.5rem 0 0.35rem;">
            <svg viewBox="0 0 160 55" xmlns="http://www.w3.org/2000/svg"
                 style="height:48px; width:auto;">
                <circle cx="28" cy="28" r="24" fill="#f26522"/>
                <g fill="white">
                    <polygon points="28,8 29.5,17 26.5,17"/>
                    <polygon points="28,8 29.5,17 26.5,17" transform="rotate(30,28,28)"/>
                    <polygon points="28,8 29.5,17 26.5,17" transform="rotate(60,28,28)"/>
                    <polygon points="28,8 29.5,17 26.5,17" transform="rotate(90,28,28)"/>
                    <polygon points="28,8 29.5,17 26.5,17" transform="rotate(120,28,28)"/>
                    <polygon points="28,8 29.5,17 26.5,17" transform="rotate(150,28,28)"/>
                    <polygon points="28,8 29.5,17 26.5,17" transform="rotate(180,28,28)"/>
                    <polygon points="28,8 29.5,17 26.5,17" transform="rotate(210,28,28)"/>
                    <polygon points="28,8 29.5,17 26.5,17" transform="rotate(240,28,28)"/>
                    <polygon points="28,8 29.5,17 26.5,17" transform="rotate(270,28,28)"/>
                    <polygon points="28,8 29.5,17 26.5,17" transform="rotate(300,28,28)"/>
                    <polygon points="28,8 29.5,17 26.5,17" transform="rotate(330,28,28)"/>
                </g>
                <circle cx="28" cy="28" r="6" fill="white"/>
                <text x="62" y="36" font-family="Arial,sans-serif" font-size="26"
                      font-weight="bold" fill="#1e3a5f">PSEG</text>
            </svg>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**Tech Manual Agent Prototype**")
        st.caption("Powered by Azure AI · GCC High")
        st.caption(f"App version: {APP_VERSION}")
        st.markdown("---")

        st.markdown("**Backend Status**")
        try:
            r = requests.get(f"{BACKEND_URL}/health", timeout=4)
            if r.status_code == 200:
                st.success("Connected ✓")
            else:
                st.warning(f"HTTP {r.status_code}")
        except Exception as e:
            st.error(f"Unreachable: {e}")

        st.markdown("---")

        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.session_id = str(uuid.uuid4())
            st.rerun()

        st.markdown("---")

        st.markdown("**User Feedback**")
        st.markdown(
            """
            <div class="feedback-box">
                Share your expectations, usage pattern, and improvement ideas.
            </div>
            """,
            unsafe_allow_html=True,
        )

        if FEEDBACK_FORM_URL:
            st.markdown(
                f'<div class="feedback-link"><a href="{FEEDBACK_FORM_URL}" target="_blank">Open Feedback Form</a></div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("Add FEEDBACK_FORM_URL in environment variables to show a feedback form link.")

        st.markdown("---")
        st.caption(f"Session `{st.session_state.session_id[:8]}…`")


def render_header() -> None:
    st.markdown("""
    <div style="background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
                border-radius: 16px; padding: 1.1rem 1.6rem; margin-bottom: 1rem;
                border-bottom: 4px solid #f26522;
                box-shadow: 0 6px 20px rgba(30,58,95,0.12);">
        <div style="font-size:1.25rem; font-weight:700; color:white; margin-bottom:4px;">
            ⚡ PACG Tech Manual Agent Chatbot Prototype
        </div>
        <div style="font-size:0.87rem; color:rgba(255,255,255,0.85);">
            Ask questions against PSEG technical documentation.
            Answers are grounded in retrieved manual content with source citations.
        </div>
    </div>
    """, unsafe_allow_html=True)


def main() -> None:
    render_sidebar()
    render_header()
    render_history()

    if prompt := st.chat_input("Ask a question about PSEG technical manuals…"):
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            citations_captured = []
            full_answer = ""

            try:
                url = f"{BACKEND_URL}/chat"

                resp = requests.post(
                    url,
                    json={
                        "question": prompt,
                        "session_id": st.session_state.session_id,
                    },
                    headers={"Content-Type": "application/json"},
                    timeout=120,
                )

                if resp.status_code != 200:
                    full_answer = (
                        f"Backend error: HTTP {resp.status_code}\n\n"
                        f"Body:\n{resp.text}"
                    )
                    st.error(full_answer)
                else:
                    payload = resp.json()
                    full_answer = payload.get("answer", "").strip()
                    citations_captured = payload.get("citations", [])

                    if full_answer:
                        st.markdown(full_answer)
                    else:
                        full_answer = f"No answer text returned from backend.\n\nRaw payload:\n{payload}"
                        st.warning(full_answer)

                    if citations_captured:
                        st.markdown("---")
                        render_citations(citations_captured)

            except requests.exceptions.ConnectionError as e:
                full_answer = "Cannot connect to backend."
                st.error(f"{full_answer}\n\n{e}")

            except requests.exceptions.Timeout:
                full_answer = "Request timed out. Please try again."
                st.error(full_answer)

            except Exception as e:
                full_answer = f"Unexpected error: {e}"
                st.error(full_answer)

            st.session_state.messages.append({
                "role": "assistant",
                "content": full_answer,
                "citations": citations_captured,
            })

    st.markdown(
        '<div style="text-align:center; padding: 0.8rem 0; margin-top:1.2rem; '
        'color:#718096; font-size:0.76rem;">'
        'PACG Tech Manual Agent Chatbot Prototype · Powered by Azure AI · GCC High'
        '</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
