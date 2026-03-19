"""Cosmos DB async client — single instance shared for the app lifetime.

Auth modes (controlled by COSMOS_AUTH_MODE env var):
  "key"              → COSMOS_ENDPOINT + COSMOS_KEY  (local / dev)
  "managed_identity" → COSMOS_ENDPOINT + DefaultAzureCredential (production)

Call init_cosmos() once at app startup (FastAPI lifespan).
Call close_cosmos() at app shutdown — closes both the CosmosClient and the
  managed-identity credential (if applicable) to release transport resources.
Use get_conversations_container() / get_messages_container() everywhere else.

Container layout (must already exist when COSMOS_AUTO_CREATE_CONTAINERS=false):
  conversations — partitioned by /user_id
  messages      — partitioned by /thread_id

Startup verification:
  When COSMOS_AUTO_CREATE_CONTAINERS=false, the module probes both containers
  with a lightweight read after creating the client objects.  If the containers
  are unreachable, storage is disabled with a clear error log rather than
  silently succeeding and failing at first query time.

If COSMOS_ENDPOINT is not configured the module silently disables storage so
the app degrades gracefully to in-memory-only mode.
"""

from __future__ import annotations

import logging

from azure.cosmos.exceptions import CosmosHttpResponseError

logger = logging.getLogger(__name__)

# Module-level singletons — populated by init_cosmos()
_client = None
_credential = None          # stored so close_cosmos() can close it cleanly
_conversations_container = None
_messages_container = None


async def init_cosmos() -> None:
    """Initialize Cosmos DB client and containers. Call once at app startup."""
    global _client, _credential, _conversations_container, _messages_container

    from app.config.settings import (
        COSMOS_AUTH_MODE,
        COSMOS_AUTO_CREATE_CONTAINERS,
        COSMOS_CONVERSATIONS_CONTAINER,
        COSMOS_DATABASE,
        COSMOS_ENABLE_TTL,
        COSMOS_ENDPOINT,
        COSMOS_KEY,
        COSMOS_MESSAGES_CONTAINER,
        COSMOS_TTL_SECONDS,
    )

    if not COSMOS_ENDPOINT:
        logger.warning(
            "cosmos_client: COSMOS_ENDPOINT not configured — "
            "persistent chat storage disabled. "
            "Set COSMOS_ENDPOINT (and COSMOS_KEY or use managed identity) to enable."
        )
        return

    # Log host only — never log keys or full connection strings.
    try:
        from urllib.parse import urlparse
        _host = urlparse(COSMOS_ENDPOINT).hostname or COSMOS_ENDPOINT
    except Exception:
        _host = "<endpoint>"

    try:
        if COSMOS_AUTH_MODE == "managed_identity":
            from azure.cosmos.aio import CosmosClient
            from azure.identity.aio import DefaultAzureCredential

            # Store credential at module level so close_cosmos() can close it.
            _credential = DefaultAzureCredential()
            _client = CosmosClient(COSMOS_ENDPOINT, credential=_credential)
            logger.info(
                "cosmos_client: initialized with DefaultAzureCredential | host=%s", _host
            )
        else:
            from azure.cosmos.aio import CosmosClient

            if not COSMOS_KEY:
                logger.error(
                    "cosmos_client: COSMOS_AUTH_MODE=key but COSMOS_KEY is not set — "
                    "storage disabled"
                )
                return
            _client = CosmosClient(COSMOS_ENDPOINT, credential=COSMOS_KEY)
            logger.info("cosmos_client: initialized with key auth | host=%s", _host)

        ttl = COSMOS_TTL_SECONDS if COSMOS_ENABLE_TTL else None

        if COSMOS_AUTO_CREATE_CONTAINERS:
            from azure.cosmos import PartitionKey

            db = await _client.create_database_if_not_exists(id=COSMOS_DATABASE)
            logger.info("cosmos_client: database ready — %s", COSMOS_DATABASE)

            _conversations_container = await db.create_container_if_not_exists(
                id=COSMOS_CONVERSATIONS_CONTAINER,
                partition_key=PartitionKey(path="/user_id"),
                default_ttl=ttl,
            )
            _messages_container = await db.create_container_if_not_exists(
                id=COSMOS_MESSAGES_CONTAINER,
                partition_key=PartitionKey(path="/thread_id"),
                default_ttl=ttl,
            )
            logger.info(
                "cosmos_client: containers ready — conversations=%s  messages=%s",
                COSMOS_CONVERSATIONS_CONTAINER,
                COSMOS_MESSAGES_CONTAINER,
            )
        else:
            # Expect containers to already exist (created manually in Azure Portal).
            db = _client.get_database_client(COSMOS_DATABASE)
            _conversations_container = db.get_container_client(COSMOS_CONVERSATIONS_CONTAINER)
            _messages_container = db.get_container_client(COSMOS_MESSAGES_CONTAINER)

            # Verify containers are actually reachable — get_container_client() is
            # synchronous and makes no network call, so we must probe explicitly.
            # container.read() reads container properties (lightweight — no documents).
            # A 404 means the container doesn't exist; any other error is connectivity.
            # To enable fail-fast in production, replace the logger.error calls below
            # with `raise` after the log statement.
            probe_ok = True
            for label, container, container_name in [
                ("conversations", _conversations_container, COSMOS_CONVERSATIONS_CONTAINER),
                ("messages", _messages_container, COSMOS_MESSAGES_CONTAINER),
            ]:
                try:
                    await container.read()
                except CosmosHttpResponseError as exc:
                    logger.error(
                        "cosmos_client: %s container '%s' not reachable (HTTP %d) — "
                        "check that database '%s' and container exist. Storage disabled.",
                        label, container_name, exc.status_code, COSMOS_DATABASE,
                    )
                    probe_ok = False
                    break
                except Exception as exc:
                    logger.error(
                        "cosmos_client: %s container '%s' probe failed — %s: %s. "
                        "Check network/auth. Storage disabled.",
                        label, container_name, type(exc).__name__, str(exc)[:200],
                    )
                    probe_ok = False
                    break

            if not probe_ok:
                _conversations_container = None
                _messages_container = None
                return

            logger.info(
                "cosmos_client: containers verified — conversations=%s  messages=%s",
                COSMOS_CONVERSATIONS_CONTAINER,
                COSMOS_MESSAGES_CONTAINER,
            )

    except Exception:
        logger.exception(
            "cosmos_client: initialization failed — storage disabled. "
            "Check COSMOS_ENDPOINT, COSMOS_KEY, and network connectivity."
        )
        _client = None
        _credential = None
        _conversations_container = None
        _messages_container = None


async def close_cosmos() -> None:
    """Close the Cosmos DB client and managed-identity credential (if any).

    Both the CosmosClient and DefaultAzureCredential hold internal HTTP
    transport sessions.  Closing them cleanly avoids resource-leak warnings
    on shutdown.
    """
    global _client, _credential
    if _client is not None:
        await _client.close()
        _client = None
        logger.info("cosmos_client: CosmosClient closed")
    if _credential is not None:
        try:
            await _credential.close()
        except Exception:
            logger.debug("cosmos_client: credential close raised (non-fatal)", exc_info=True)
        _credential = None
        logger.info("cosmos_client: credential closed")


def get_conversations_container():
    """Return the conversations ContainerProxy, or None if storage is disabled."""
    return _conversations_container


def get_messages_container():
    """Return the messages ContainerProxy, or None if storage is disabled."""
    return _messages_container


def is_storage_enabled() -> bool:
    """Return True only when both containers are ready and verified."""
    return _conversations_container is not None and _messages_container is not None
