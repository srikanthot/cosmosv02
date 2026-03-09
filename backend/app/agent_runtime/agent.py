"""AgentRuntime — Microsoft Agent Framework SDK orchestrator.

Architecture (replaces the hand-rolled LLM loop with official SDK primitives):

  POST /chat/stream
       ↓
  routes.py              thin: validate → create session → call runtime
       ↓
  AgentRuntime.run_stream()
    1. retrieve()         embed query → hybrid Azure AI Search (VectorizedQuery)
    2. GATE               abort early if evidence count or avg score too low
    3. rag_provider       store pre-retrieved results in session.state
    4. af_agent.run()     Agent Framework ChatAgent → AzureOpenAIChatClient
                            • InMemoryHistoryProvider  multi-turn memory
                            • RagContextProvider.before_run()  injects chunks
                            • LLM streams tokens via ResponseStream
    5. SSE stream         yield tokens + keepalive pings
    6. CitationProvider   dedup + emit structured citations event
       ↓
  SSE stream → Streamlit UI

Why Agent Framework?
  - AzureOpenAIChatClient owns the Azure OpenAI connection (API-key auth).
  - ChatAgent (via as_agent()) handles prompt assembly, history, and streaming.
  - RagContextProvider.before_run() is the official SDK hook for RAG injection.
  - InMemoryHistoryProvider maintains multi-turn memory locally.
  - Azure AI Foundry Managed Agents are unavailable in GCC High — this pattern
    gives the same architecture without the managed service.
"""

import asyncio
import json
import logging
import time
from collections.abc import AsyncGenerator

from agent_framework import AgentSession as AFAgentSession

from app.agent_runtime.citation_provider import build_citations
from app.agent_runtime.session import AgentSession
from app.api.schemas import CitationsPayload
from app.config.settings import MIN_AVG_SCORE, MIN_RERANKER_SCORE, MIN_RESULTS, TOP_K, TRACE_MODE
from app.llm.af_agent_factory import af_agent, rag_provider
from app.tools.retrieval_tool import retrieve

logger = logging.getLogger(__name__)

# Emit a keepalive ping every N seconds to prevent proxy / browser SSE timeout.
_PING_INTERVAL_SECONDS = 20

# Per conversation-session cache of Agent Framework sessions.
# Keyed by the session_id from the HTTP request (our AgentSession.session_id).
# InMemoryHistoryProvider stores message history inside each AFAgentSession.state,
# giving multi-turn memory for the lifetime of the process.
_af_sessions: dict[str, AFAgentSession] = {}


def _sse_data(payload: str) -> str:
    """Encode a string as an SSE data line.

    Newlines inside *payload* are replaced by the literal ``\\n`` so SSE's
    blank-line event boundary is never confused with content newlines.
    The Streamlit frontend decodes them back before rendering.
    """
    return f"data: {payload.replace(chr(10), chr(92) + 'n')}\n\n"


def _sse_event(event_name: str, payload: str) -> str:
    """Encode a named SSE event."""
    return f"event: {event_name}\ndata: {payload}\n\n"


class AgentRuntime:
    """Orchestrates the full retrieve → gate → generate → cite pipeline.

    Uses the Microsoft Agent Framework SDK for LLM invocation, context
    injection (RagContextProvider), and conversation memory
    (InMemoryHistoryProvider).
    """

    async def run_stream(
        self,
        question: str,
        session: AgentSession,
        top_k: int = TOP_K,
    ) -> AsyncGenerator[str, None]:
        """Execute the pipeline and yield SSE-formatted strings.

        This is an async generator — pass it directly to FastAPI's
        StreamingResponse.  Each yielded string is a complete SSE line.

        Yields
        ------
        str
            SSE strings: token data lines, named events (citations, ping),
            and the final ``[DONE]`` sentinel.
        """
        logger.info(
            "AgentRuntime.run_stream | session=%s | question=%s",
            session.session_id, question,
        )

        # ── 1. RETRIEVE — hybrid Azure AI Search (keyword + VectorizedQuery) ──
        # Runs in a thread to avoid blocking the async event loop.
        try:
            results: list[dict] = await asyncio.to_thread(
                retrieve, question, top_k=top_k
            )
        except Exception:
            logger.exception("Retrieval failed")
            yield _sse_data(
                "I'm sorry — an error occurred while searching the knowledge base. "
                "Please try again."
            )
            yield _sse_event("citations", json.dumps({"citations": []}))
            yield _sse_data("[DONE]")
            return

        # ── 2. GATE — confidence check ────────────────────────────────────────
        # When semantic reranker is active, gate on reranker_score (0-4 scale).
        # Otherwise gate on base RRF/hybrid score (0.01-0.033 scale).
        has_reranker = bool(results) and results[0].get("reranker_score") is not None
        if has_reranker:
            avg_effective = (
                sum(r.get("reranker_score") or 0 for r in results) / len(results)
            )
            gate_threshold = MIN_RERANKER_SCORE
        else:
            avg_effective = (
                sum(r["score"] for r in results) / len(results) if results else 0.0
            )
            gate_threshold = MIN_AVG_SCORE

        if TRACE_MODE:
            logger.info(
                "TRACE | n_results=%d  avg_effective=%.4f  gate=(>=%d results, >=%.3f)  "
                "semantic_reranker=%s",
                len(results), avg_effective, MIN_RESULTS, gate_threshold, has_reranker,
            )

        if len(results) < MIN_RESULTS or avg_effective < gate_threshold:
            logger.info(
                "Gate: insufficient evidence (n=%d avg=%.4f threshold_n=%d threshold=%.3f)",
                len(results), avg_effective, MIN_RESULTS, gate_threshold,
            )
            yield _sse_data(
                "I don't have enough evidence from the technical manuals to answer "
                "your question confidently.\n\n"
                "Could you provide more detail — for example, the equipment name, "
                "model number, or the specific procedure you are looking for?"
            )
            yield _sse_event(
                "citations",
                CitationsPayload(citations=[]).model_dump_json(),
            )
            yield _sse_data("[DONE]")
            return

        # ── 3. Get or create Agent Framework session (multi-turn memory) ──────
        af_session = _af_sessions.get(session.session_id)
        if af_session is None:
            af_session = af_agent.create_session()
            _af_sessions[session.session_id] = af_session

        # ── 4. Hand pre-retrieved results to RagContextProvider ───────────────
        # RagContextProvider.before_run() reads from session.state and injects
        # the chunks as grounded context — no double Search call.
        rag_provider.store_results(af_session, results)

        # ── 5. GENERATE — stream via Agent Framework ChatAgent ────────────────
        # af_agent.run(stream=True) returns a ResponseStream (AsyncIterable).
        # Each AgentResponseUpdate carries the streamed token in .text.
        last_ping_at = time.monotonic()
        answer_buf: list[str] = []
        try:
            async for update in af_agent.run(
                question, stream=True, session=af_session
            ):
                now = time.monotonic()
                if now - last_ping_at >= _PING_INTERVAL_SECONDS:
                    yield _sse_event("ping", "keepalive")
                    last_ping_at = now

                if update.text:
                    answer_buf.append(update.text)
                    yield _sse_data(update.text)

        except Exception:
            logger.exception("LLM streaming failed")
            yield _sse_data(
                "\n\nI'm sorry — an error occurred while generating the answer. "
                "Please try again."
            )

        # ── 6. CITE — only emit citations if the agent actually used sources ──
        # If the answer contains [N] citation markers or a "Sources:" section
        # the model drew from the retrieved context; otherwise it couldn't
        # answer from the manuals and citations would be misleading.
        answer_text = "".join(answer_buf)
        used_sources = "Sources:" in answer_text or "[1]" in answer_text
        citations = build_citations(results) if used_sources else []
        yield _sse_event("citations", CitationsPayload(citations=citations).model_dump_json())
        yield _sse_data("[DONE]")
