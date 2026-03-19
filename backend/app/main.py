"""FastAPI application entry point for the PSEG Tech Manual Agent."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config.settings import ALLOWED_ORIGINS, CORS_ALLOW_CREDENTIALS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and tear down shared resources (Cosmos DB client)."""
    from app.storage.cosmos_client import close_cosmos, init_cosmos

    logger.info("Starting up — initializing Cosmos DB storage...")
    await init_cosmos()
    logger.info("Startup complete.")
    yield
    logger.info("Shutting down — closing Cosmos DB client...")
    await close_cosmos()
    logger.info("Shutdown complete.")


app = FastAPI(
    title="PSEG Tech Manual Agent",
    description=(
        "Agent-pattern RAG chatbot for GCC High. "
        "Hybrid Azure AI Search + Azure OpenAI, streamed SSE with structured citations. "
        "Persistent chat history via Azure Cosmos DB."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — production-safe:
#   ALLOWED_ORIGINS="*"         → wildcard, credentials disabled (browser-safe)
#   ALLOWED_ORIGINS=<explicit>  → named origins, credentials enabled
# Both modes are set automatically from the ALLOWED_ORIGINS env var.
# See settings.py for the derivation logic.
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health() -> dict:
    """Simple health-check endpoint — includes storage status."""
    from app.storage.cosmos_client import is_storage_enabled

    return {
        "status": "ok",
        "storage": "cosmos" if is_storage_enabled() else "in-memory",
    }


@app.get("/health/cosmos")
async def health_cosmos() -> dict:
    """Detailed Cosmos DB health check — verifies connectivity to DB and containers.

    Returns success/failure JSON with database and container names.
    Never exposes secrets.
    """
    from app.config.settings import (
        COSMOS_CONVERSATIONS_CONTAINER,
        COSMOS_DATABASE,
        COSMOS_ENDPOINT,
        COSMOS_MESSAGES_CONTAINER,
    )
    from app.storage.cosmos_client import (
        get_conversations_container,
        get_messages_container,
        is_storage_enabled,
    )

    if not COSMOS_ENDPOINT:
        return {
            "status": "disabled",
            "reason": "COSMOS_ENDPOINT not configured",
            "database": COSMOS_DATABASE,
            "conversations_container": COSMOS_CONVERSATIONS_CONTAINER,
            "messages_container": COSMOS_MESSAGES_CONTAINER,
        }

    if not is_storage_enabled():
        return {
            "status": "error",
            "reason": "Cosmos client failed to initialize — check startup logs",
            "database": COSMOS_DATABASE,
            "conversations_container": COSMOS_CONVERSATIONS_CONTAINER,
            "messages_container": COSMOS_MESSAGES_CONTAINER,
        }

    # Probe both containers with a lightweight point-read that will 404 but confirms
    # the container is reachable.
    errors: list[str] = []
    for label, container in [
        ("conversations", get_conversations_container()),
        ("messages", get_messages_container()),
    ]:
        try:
            await container.read_item(item="__health_probe__", partition_key="__probe__")
        except Exception as exc:
            # 404 means the container is reachable (item just doesn't exist — expected).
            # Any other exception indicates a connectivity or auth problem.
            msg = str(exc)
            if "404" not in msg and "NotFound" not in msg:
                errors.append(f"{label}: {type(exc).__name__}: {msg[:120]}")

    if errors:
        return {
            "status": "error",
            "reason": "; ".join(errors),
            "database": COSMOS_DATABASE,
            "conversations_container": COSMOS_CONVERSATIONS_CONTAINER,
            "messages_container": COSMOS_MESSAGES_CONTAINER,
        }

    return {
        "status": "ok",
        "database": COSMOS_DATABASE,
        "conversations_container": COSMOS_CONVERSATIONS_CONTAINER,
        "messages_container": COSMOS_MESSAGES_CONTAINER,
    }
