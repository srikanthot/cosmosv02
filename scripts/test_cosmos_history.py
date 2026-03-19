"""Standalone Cosmos DB history smoke test.

Verifies connectivity to Azure Cosmos DB and exercises the full
conversation + message persistence flow without starting the FastAPI server.

Usage (from repo root):
    cd backend
    python ../scripts/test_cosmos_history.py

Requires backend/.env to be populated with Cosmos credentials.

Test user:  local-dev
Thread ID:  thread_test_001
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# ── Make sure backend/app is importable ──────────────────────────────────────
BACKEND_ROOT = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

# Load .env from backend/
from dotenv import load_dotenv
load_dotenv(BACKEND_ROOT / ".env", override=True)

# ── Now import application modules ───────────────────────────────────────────
from app.config.settings import (
    COSMOS_CONVERSATIONS_CONTAINER,
    COSMOS_DATABASE,
    COSMOS_ENDPOINT,
    COSMOS_MESSAGES_CONTAINER,
)
from app.storage.cosmos_client import close_cosmos, init_cosmos, is_storage_enabled
from app.storage import chat_store

# ── Test constants ────────────────────────────────────────────────────────────
TEST_USER_ID  = "local-dev"
TEST_USERNAME = "Local Dev User"
TEST_THREAD   = "thread_test_001"
SEP = "-" * 60


def ok(msg: str) -> None:
    print(f"  [OK]  {msg}")


def fail(msg: str) -> None:
    print(f"  [FAIL] {msg}")
    sys.exit(1)


def section(title: str) -> None:
    print(f"\n{SEP}\n{title}\n{SEP}")


async def run() -> None:
    # ── 0. Config check ───────────────────────────────────────────────────────
    section("0. Configuration")
    print(f"  COSMOS_ENDPOINT              = {COSMOS_ENDPOINT or '(not set)'}")
    print(f"  COSMOS_DATABASE              = {COSMOS_DATABASE}")
    print(f"  COSMOS_CONVERSATIONS_CONTAINER = {COSMOS_CONVERSATIONS_CONTAINER}")
    print(f"  COSMOS_MESSAGES_CONTAINER    = {COSMOS_MESSAGES_CONTAINER}")

    if not COSMOS_ENDPOINT:
        fail("COSMOS_ENDPOINT is not set in backend/.env — cannot connect")

    # ── 1. Initialize client ──────────────────────────────────────────────────
    section("1. Initialize Cosmos client")
    await init_cosmos()

    if not is_storage_enabled():
        fail(
            "Cosmos client failed to initialize. "
            "Check COSMOS_ENDPOINT, COSMOS_KEY, and that the database/containers exist."
        )
    ok("Client initialized — both containers reachable")

    # ── 2. Upsert conversation ────────────────────────────────────────────────
    section("2. Create / upsert conversation")
    conv = await chat_store.create_conversation(
        thread_id=TEST_THREAD,
        user_id=TEST_USER_ID,
        user_name=TEST_USERNAME,
        title="Test Conversation",
        metadata={"source": "test-script", "rag_enabled": True},
    )
    if conv is None:
        fail("create_conversation returned None — storage may be disabled or unreachable")
    ok(f"Conversation upserted: id={conv.id}  title={conv.title!r}")

    # ── 3. Read conversation back ─────────────────────────────────────────────
    section("3. Read conversation back")
    fetched = await chat_store.get_conversation(TEST_THREAD, TEST_USER_ID)
    if fetched is None:
        fail("get_conversation returned None — document not found after upsert")
    ok(f"Fetched: id={fetched.id}  user_id={fetched.user_id}  title={fetched.title!r}")

    # ── 4. Append user message ────────────────────────────────────────────────
    section("4. Append user message")
    user_msg = await chat_store.append_user_message(
        thread_id=TEST_THREAD,
        user_id=TEST_USER_ID,
        content="How do I reset the relay panel safely?",
    )
    if user_msg is None:
        fail("append_user_message returned None")
    ok(f"User message saved: id={user_msg.id}  seq={user_msg.sequence}  role={user_msg.role}")

    # ── 5. Append assistant message with citations ────────────────────────────
    section("5. Append assistant message with citations")
    citations = [
        {
            "source_id": "manual-001",
            "file_name": "switchgear_manual.pdf",
            "chunk_id": "chunk-000245",
            "title": "Panel Reset Procedure",
            "page": 42,
            "snippet": (
                "Before performing a reset, isolate upstream power "
                "and verify lockout/tagout conditions."
            ),
            "score": 0.93,
        }
    ]
    asst_msg = await chat_store.append_assistant_message(
        thread_id=TEST_THREAD,
        user_id=TEST_USER_ID,
        content=(
            "Based on section 4.2, isolate power first and confirm lockout "
            "before opening the panel."
        ),
        citations=citations,
        status="completed",
        metadata={"source": "test-script", "model": "gpt-4.1"},
    )
    if asst_msg is None:
        fail("append_assistant_message returned None")
    ok(
        f"Assistant message saved: id={asst_msg.id}  seq={asst_msg.sequence}  "
        f"citations={len(asst_msg.citations)}"
    )

    # ── 6. Read messages back ─────────────────────────────────────────────────
    section("6. Read messages back")
    messages = await chat_store.get_messages_for_user(TEST_THREAD, TEST_USER_ID, max_turns=50)
    if not messages:
        fail("get_messages_for_user returned empty — expected at least 2 messages")
    ok(f"Retrieved {len(messages)} message(s) in sequence order:")
    for m in messages:
        cit_count = len(m.citations)
        print(
            f"    seq={m.sequence}  role={m.role:<10}  "
            f"status={m.status}  citations={cit_count}  "
            f"preview={m.content[:60]!r}"
        )

    # ── 7. List conversations ─────────────────────────────────────────────────
    section("7. List conversations for user")
    convs = await chat_store.list_conversations(TEST_USER_ID, limit=10)
    ok(f"Found {len(convs)} conversation(s) for user={TEST_USER_ID!r}:")
    for c in convs:
        print(
            f"    thread={c.thread_id}  title={c.title!r}  "
            f"msgs={c.message_count}  deleted={c.is_deleted}"
        )

    # ── 8. Verify updated conversation metadata ───────────────────────────────
    section("8. Verify conversation metadata was updated")
    updated = await chat_store.get_conversation(TEST_THREAD, TEST_USER_ID)
    if updated is None:
        fail("get_conversation returned None after appending messages")
    ok(f"message_count = {updated.message_count}")
    ok(f"last_user_message_preview = {updated.last_user_message_preview!r}")
    ok(f"last_assistant_message_preview = {updated.last_assistant_message_preview!r}")

    # ── Cleanup ───────────────────────────────────────────────────────────────
    await close_cosmos()

    # ── Summary ───────────────────────────────────────────────────────────────
    section("RESULT")
    print("  All checks passed.")
    print(f"  Conversation persisted in Cosmos DB:")
    print(f"    Database:   {COSMOS_DATABASE}")
    print(f"    Container:  {COSMOS_CONVERSATIONS_CONTAINER}  →  id={TEST_THREAD}")
    print(f"    Container:  {COSMOS_MESSAGES_CONTAINER}  →  {len(messages)} message(s)")
    print()
    print("  To verify persistence: re-run this script (data should still be there).")
    print("  To verify in Azure Portal: open Data Explorer and browse the containers.")


if __name__ == "__main__":
    asyncio.run(run())
