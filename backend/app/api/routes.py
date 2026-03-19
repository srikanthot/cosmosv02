"""FastAPI routes — thin routes delegating to AgentRuntime and chat_store.

Chat endpoints (backward-compatible):
  POST /chat/stream    — SSE streaming answer with citations
  POST /chat           — non-streaming JSON answer with citations
                         Uses AgentRuntime.run_once() directly; does NOT
                         parse SSE text to reconstruct the response.

Conversation management endpoints:
  GET    /conversations                        — list user's threads
  POST   /conversations                        — create new thread
  GET    /conversations/{thread_id}            — get one conversation metadata
  GET    /conversations/{thread_id}/messages   — ordered message history
  DELETE /conversations/{thread_id}            — soft delete
  PATCH  /conversations/{thread_id}            — rename title

Storage-unavailable behavior:
  Chat endpoints (POST /chat, POST /chat/stream) still work in degraded mode
  when storage is disabled — they generate answers but do not persist history.
  All conversation management endpoints return HTTP 503 when storage is
  disabled, since they are meaningless without a working storage backend.

Multi-user isolation:
  When the client supplies a session_id in a chat request, the route
  validates that the conversation exists for the resolved user BEFORE
  dispatching to AgentRuntime.  If the thread_id is not owned by this user,
  the route returns HTTP 404 immediately.  AgentRuntime performs a second
  defensive check as well.

  This approach keeps all HTTP error handling in the route layer and lets
  AgentRuntime remain decoupled from FastAPI exception types.

Identity is resolved per-request from headers via resolve_identity() and
injected as a FastAPI dependency — no auth logic lives in route handlers.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.agent_runtime.agent import AgentRuntime
from app.agent_runtime.session import AgentSession
from app.api.schemas import (
    ChatRequest,
    ConversationResponse,
    CreateConversationRequest,
    MessageResponse,
    UpdateConversationRequest,
)
from app.auth.identity import UserIdentity, resolve_identity
from app.storage import chat_store
from app.storage.cosmos_client import is_storage_enabled

logger = logging.getLogger(__name__)
router = APIRouter()

_runtime = AgentRuntime()

_STORAGE_DISABLED_503 = HTTPException(
    status_code=503,
    detail="Storage unavailable — Cosmos DB is not configured or failed to initialize.",
)


# ---------------------------------------------------------------------------
# Dependency — identity resolver
# ---------------------------------------------------------------------------

async def get_identity(request: Request) -> UserIdentity:
    """FastAPI dependency: resolve user identity from request headers."""
    return resolve_identity(request)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _conv_to_response(conv) -> ConversationResponse:
    return ConversationResponse(
        thread_id=conv.thread_id,
        user_id=conv.user_id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        last_message_at=conv.last_message_at,
        last_user_message_preview=conv.last_user_message_preview,
        last_assistant_message_preview=conv.last_assistant_message_preview,
        message_count=conv.message_count,
        is_deleted=conv.is_deleted,
    )


def _msg_to_response(msg) -> MessageResponse:
    return MessageResponse(
        id=msg.id,
        thread_id=msg.thread_id,
        role=msg.role,
        content=msg.content,
        citations=msg.citations,
        created_at=msg.created_at,
        sequence=msg.sequence,
        status=msg.status,
    )


def _make_session(body: ChatRequest) -> AgentSession:
    """Create an AgentSession from the request body, honouring session_id alias.

    Sets client_provided=True when the caller explicitly supplied a session_id
    so that AgentRuntime can distinguish between:
      - a client-provided thread_id that must already exist for this user, and
      - an auto-generated thread_id that should be created on first use.
    """
    session = AgentSession(question=body.question)
    if body.session_id:
        session.session_id = body.session_id
        session.client_provided = True
    return session


async def _assert_conversation_ownership(thread_id: str, user_id: str) -> None:
    """Raise HTTP 404 if the thread does not exist or is not owned by user_id.

    Using 404 (not 403) intentionally: we do not reveal whether the thread
    exists for a different user — the caller only learns it is not accessible
    to them.
    """
    if not is_storage_enabled():
        return  # no storage → no ownership to enforce
    conv = await chat_store.get_conversation(thread_id, user_id)
    if conv is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found or access denied.",
        )


def _q_preview(question: str, max_len: int = 80) -> str:
    """Return a truncated question safe for logging."""
    return question[:max_len] + "…" if len(question) > max_len else question


# ---------------------------------------------------------------------------
# Chat endpoints
# ---------------------------------------------------------------------------

@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequest,
    identity: UserIdentity = Depends(get_identity),
) -> StreamingResponse:
    """Stream a grounded answer with citations via Server-Sent Events."""
    logger.info(
        "POST /chat/stream | user=%s session=%s | q=%s",
        identity.user_id, body.session_id, _q_preview(body.question),
    )

    # Ownership check before starting the stream.  If the client supplied a
    # session_id that is not owned by this user, return 404 now — once the
    # StreamingResponse starts we can no longer return an HTTP error status.
    if body.session_id:
        await _assert_conversation_ownership(body.session_id, identity.user_id)

    session = _make_session(body)
    return StreamingResponse(
        _runtime.run_stream(body.question, session, identity),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/chat")
async def chat(
    body: ChatRequest,
    identity: UserIdentity = Depends(get_identity),
) -> dict:
    """Return a grounded answer and citations as normal JSON.

    Delegates directly to AgentRuntime.run_once() — no SSE parsing involved.
    """
    logger.info(
        "POST /chat | user=%s session=%s | q=%s",
        identity.user_id, body.session_id, _q_preview(body.question),
    )

    if body.session_id:
        await _assert_conversation_ownership(body.session_id, identity.user_id)

    session = _make_session(body)
    result = await _runtime.run_once(body.question, session, identity)
    return result


# ---------------------------------------------------------------------------
# Conversation management endpoints
# ---------------------------------------------------------------------------

@router.get("/conversations")
async def list_conversations(
    identity: UserIdentity = Depends(get_identity),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ConversationResponse]:
    """Return recent conversations for the resolved user, newest first."""
    if not is_storage_enabled():
        raise _STORAGE_DISABLED_503
    convs = await chat_store.list_conversations(identity.user_id, limit=limit)
    return [_conv_to_response(c) for c in convs]


@router.post("/conversations")
async def create_conversation(
    body: CreateConversationRequest,
    identity: UserIdentity = Depends(get_identity),
) -> ConversationResponse:
    """Create a new empty conversation thread and return its thread_id."""
    if not is_storage_enabled():
        raise _STORAGE_DISABLED_503

    thread_id = str(uuid.uuid4())
    title = body.title or "New Chat"
    conv = await chat_store.create_conversation(
        thread_id=thread_id,
        user_id=identity.user_id,
        user_name=identity.user_name,
        title=title,
    )
    if conv is None:
        raise HTTPException(status_code=503, detail="Storage unavailable")
    return _conv_to_response(conv)


@router.get("/conversations/{thread_id}")
async def get_conversation(
    thread_id: str,
    identity: UserIdentity = Depends(get_identity),
) -> ConversationResponse:
    """Return metadata for a single conversation thread."""
    if not is_storage_enabled():
        raise _STORAGE_DISABLED_503
    conv = await chat_store.get_conversation(thread_id, identity.user_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return _conv_to_response(conv)


@router.get("/conversations/{thread_id}/messages")
async def get_conversation_messages(
    thread_id: str,
    identity: UserIdentity = Depends(get_identity),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[MessageResponse]:
    """Return ordered message history for a thread.

    Ownership is enforced by get_messages_for_user() — if the conversation
    does not exist for this user the function returns [] and 404 is raised here.
    """
    if not is_storage_enabled():
        raise _STORAGE_DISABLED_503

    messages = await chat_store.get_messages_for_user(
        thread_id, identity.user_id, max_turns=limit
    )

    # If empty, confirm whether the conversation exists for this user.
    # An empty list can mean either "no messages yet" or "conversation not found".
    if not messages:
        conv = await chat_store.get_conversation(thread_id, identity.user_id)
        if conv is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

    return [_msg_to_response(m) for m in messages]


@router.delete("/conversations/{thread_id}")
async def delete_conversation(
    thread_id: str,
    identity: UserIdentity = Depends(get_identity),
) -> dict:
    """Soft-delete a conversation (marks is_deleted=true, does not remove data)."""
    if not is_storage_enabled():
        raise _STORAGE_DISABLED_503

    success = await chat_store.soft_delete_conversation(thread_id, identity.user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {"deleted": True, "thread_id": thread_id}


@router.patch("/conversations/{thread_id}")
async def update_conversation(
    thread_id: str,
    body: UpdateConversationRequest,
    identity: UserIdentity = Depends(get_identity),
) -> ConversationResponse:
    """Rename a conversation thread."""
    if not is_storage_enabled():
        raise _STORAGE_DISABLED_503

    success = await chat_store.update_conversation_title(
        thread_id, identity.user_id, body.title
    )
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conv = await chat_store.get_conversation(thread_id, identity.user_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return _conv_to_response(conv)
