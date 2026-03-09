"""PSEG Tech Manual Agent — Streamlit chat UI.

Connects to the FastAPI backend via Server-Sent Events (SSE).
Tokens stream live into the chat bubble. Citations arrive as a named
SSE event at the end and render as a collapsible "Sources" panel.
Keepalive ping events are consumed silently.
"""

import json
import os
import uuid
from typing import Generator

import requests
import sseclient
import streamlit as st
from dotenv import load_dotenv

load_dotenv(override=True)

_backend_port = os.getenv("BACKEND_PORT", "8000")
BACKEND_URL = os.getenv("BACKEND_URL", f"http://localhost:{_backend_port}")

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PSEG Tech Manual Agent",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ─────────────────────────────────────────────────────────────────
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

    /* User message bubble */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatar-user"]) {
        background: linear-gradient(135deg, #eef4fb, #e3ecf7);
        border: 1px solid #d0dff0;
        border-left: 4px solid #4a90d9;
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin: 0.5rem 0;
    }

    /* Assistant message bubble */
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

    hr { border: none; height: 1px; background: #edf2f7; margin: 1rem 0; }
</style>
""", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())


# ── SSE consumer ──────────────────────────────────────────────────────────────
def _token_stream(
    sse_response: requests.Response,
    citations_out: list,
) -> Generator[str, None, None]:
    """Consume an SSE response and yield decoded text tokens.

    Citations are captured in *citations_out* as a side effect when the
    named ``citations`` event arrives. Keepalive ``ping`` events are ignored.
    Stops when ``[DONE]`` is received.
    """
    client = sseclient.SSEClient(sse_response)
    for event in client.events():
        if event.event == "citations":
            try:
                data = json.loads(event.data)
                citations_out.extend(data.get("citations", []))
            except json.JSONDecodeError:
                pass
        elif event.event == "ping":
            # Keepalive — discard silently
            continue
        elif event.data == "[DONE]":
            break
        else:
            # Decode the \\n encoding the backend uses for newlines in SSE
            yield event.data.replace("\\n", "\n")


# ── Helpers ────────────────────────────────────────────────────────────────────
def render_citations(citations: list) -> None:
    """Render citations as a collapsible expander panel."""
    with st.expander(f"📚 Sources ({len(citations)})", expanded=False):
        for i, c in enumerate(citations, 1):
            source = c.get("source", "Unknown")
            title = c.get("title", "")
            section = c.get("section", "")
            page = c.get("page", "")
            url = c.get("url", "")
            chunk_id = c.get("chunk_id", "")

            # Show title if available; fall back to source filename
            display_name = title if title else source
            label = f"**{i}.** {display_name}"
            # Show filename separately if it differs from the title
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
    """Render all previous messages from session state."""
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("citations"):
                render_citations(msg["citations"])


# ── Sidebar ────────────────────────────────────────────────────────────────────
def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("""
        <div style="text-align:center; padding: 0.75rem 0 0.5rem;">
            <svg viewBox="0 0 160 55" xmlns="http://www.w3.org/2000/svg"
                 style="height:50px; width:auto;">
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


# ── Header ─────────────────────────────────────────────────────────────────────
def render_header() -> None:
    st.markdown("""
    <div style="background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
                border-radius: 16px; padding: 1.25rem 2rem; margin-bottom: 1.25rem;
                border-bottom: 4px solid #f26522;
                box-shadow: 0 6px 20px rgba(30,58,95,0.12);">
        <div style="font-size:1.3rem; font-weight:700; color:white; margin-bottom:4px;">
            ⚡ Tech Manual Agent
        </div>
        <div style="font-size:0.88rem; color:rgba(255,255,255,0.85);">
            Ask questions against PSEG technical documentation.
            Answers are grounded in retrieved manual content with source citations.
        </div>
    </div>
    """, unsafe_allow_html=True)


# ── Main ───────────────────────────────────────────────────────────────────────
def main() -> None:
    render_sidebar()
    render_header()
    render_history()

    if prompt := st.chat_input("Ask a question about PSEG technical manuals…"):
        # Show user message immediately
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Stream assistant response
        with st.chat_message("assistant"):
            citations_captured: list = []
            full_answer: str = ""

            try:
                resp = requests.post(
                    f"{BACKEND_URL}/chat/stream",
                    json={
                        "question": prompt,
                        "session_id": st.session_state.session_id,
                    },
                    stream=True,
                    timeout=120,
                )
                resp.raise_for_status()

                # st.write_stream renders tokens live and returns the full text
                full_answer = st.write_stream(
                    _token_stream(resp, citations_captured)
                ) or ""

                if citations_captured:
                    st.markdown("---")
                    render_citations(citations_captured)

            except requests.exceptions.ConnectionError:
                full_answer = (
                    f"Cannot connect to backend at `{BACKEND_URL}`. Is it running?"
                )
                st.error(full_answer)

            except requests.exceptions.Timeout:
                full_answer = "Request timed out. Please try again."
                st.error(full_answer)

            except requests.exceptions.HTTPError as e:
                full_answer = f"Backend error: {e}"
                st.error(full_answer)

            except Exception as e:
                full_answer = f"Unexpected error: {e}"
                st.error(full_answer)

            # Persist to session state for history rendering
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
