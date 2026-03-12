"""PSEG Tech Manual Agent — Streamlit chat UI."""

import json
import os
import uuid

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

_backend_port = os.getenv("BACKEND_PORT", "8000")
BACKEND_URL = os.getenv("BACKEND_URL", f"http://localhost:{_backend_port}")
FRONTEND_TITLE = os.getenv("FRONTEND_TITLE", "PSEG Tech Manual Agent")

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

    .stApp { background: var(--bg) !important; }

    .main .block-container {
        padding: 1.5rem 2rem 2rem !important;
        max-width: 1200px;
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

    [data-testid="stSidebar"] { background: var(--card) !important; }

    .stSpinner > div { border-top-color: var(--orange) !important; }
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
                label += f"\n\n  > {section}"
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
        st.markdown("**Tech Manual Agent**")
        st.caption("Powered by Azure AI · GCC High")
        st.markdown("---")

        st.markdown("**Backend Status**")
        try:
            r = requests.get(f"{BACKEND_URL}/health", timeout=4)
            if r.status_code == 200:
                st.success("Connected ✓")
            else:
                st.warning(f"HTTP {r.status_code}")
        except Exception:
            st.error("Unreachable")

        st.markdown("---")

        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.session_id = str(uuid.uuid4())
            st.rerun()

        st.markdown("---")
        st.caption(f"Session `{st.session_state.session_id[:8]}…`")


def render_header() -> None:
    st.markdown("""
    <div style="background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
                border-radius: 16px; padding: 1.25rem 2rem; margin-bottom: 1.25rem;
                border-bottom: 4px solid #f26522;">
        <div style="font-size:1.3rem; font-weight:700; color:white; margin-bottom:4px;">
            ⚡ Tech Manual Agent
        </div>
        <div style="font-size:0.88rem; color:rgba(255,255,255,0.85);">
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
            full_answer = ""
            citations_captured = []

            try:
                resp = requests.post(
                    f"{BACKEND_URL}/chat/stream",
                    json={
                        "question": prompt,
                        "session_id": st.session_state.session_id,
                    },
                    headers={
                        "Accept": "text/event-stream",
                        "Content-Type": "application/json",
                    },
                    stream=True,
                    timeout=120,
                    allow_redirects=False,
                )

                history_info = []
                for h in resp.history:
                    history_info.append({
                        "status_code": h.status_code,
                        "method": h.request.method,
                        "url": h.url,
                        "location": h.headers.get("Location"),
                    })

                request_method = getattr(resp.request, "method", "<unknown>")
                request_url = getattr(resp.request, "url", "<unknown>")

                if resp.status_code >= 400:
                    try:
                        error_body = resp.text[:1500]
                    except Exception:
                        error_body = "<no response body>"

                    full_answer = (
                        f"Backend error: HTTP {resp.status_code}\n\n"
                        f"Final request method: {request_method}\n\n"
                        f"Final request URL: {request_url}\n\n"
                        f"Response URL: {resp.url}\n\n"
                        f"Redirect history: {history_info}\n\n"
                        f"Response headers: {dict(resp.headers)}\n\n"
                        f"Response body:\n{error_body}"
                    )
                    st.error(full_answer)
                else:
                    full_answer = (
                        f"Request reached backend successfully.\n\n"
                        f"Final request method: {request_method}\n\n"
                        f"Final request URL: {request_url}\n\n"
                        f"Response URL: {resp.url}\n\n"
                        f"Redirect history: {history_info}\n\n"
                        f"Status: {resp.status_code}\n\n"
                        f"Content-Type: {resp.headers.get('Content-Type')}"
                    )
                    st.success(full_answer)

            except Exception as e:
                full_answer = f"Unexpected error: {e}"
                st.error(full_answer)

            st.session_state.messages.append({
                "role": "assistant",
                "content": full_answer,
                "citations": citations_captured,
            })

    st.markdown(
        '<div style="text-align:center; padding: 1rem 0; margin-top:1.5rem; '
        'color:#718096; font-size:0.78rem;">'
        'PSEG Tech Manual Agent · Powered by Azure AI · GCC High'
        '</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
