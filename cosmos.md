You are modifying ONLY the backend of this repository.

Repository context
- This repo is a streaming RAG chatbot with:
  - backend/ -> FastAPI backend
  - frontend/ -> temporary Streamlit frontend used for testing
- The backend already owns:
  - retrieval from Azure AI Search
  - LLM orchestration
  - confidence gate
  - citations
  - streaming responses
- The current memory is in-memory only and must be replaced/supplemented with persistent chat history.
- Do NOT modify the frontend in this task.
- Do NOT redesign the RAG logic unless needed for clean history integration.

Primary goal
Turn the existing backend into a production-oriented persistent chatbot backend that supports:
1. per-user conversation ownership
2. multiple chat threads per user
3. persistent message history across backend restarts
4. future frontend sidebar history like ChatGPT
5. current Streamlit frontend compatibility for testing
6. current /chat and /chat/stream compatibility

Important product behavior to support
I want the backend to support this experience:
- A user starts a chat thread
- The user asks follow-up questions in the same thread
- The backend remembers prior turns in that thread
- The user can start “New Chat”
- Old chats remain stored
- Later, the frontend can fetch the user’s past threads and reopen them
- Later, when real auth is added, the same person should be able to come back days later and see their threads
- For now, the backend must still work locally without real auth

Backend design requirements

A. Preserve current backend responsibilities
Keep the backend responsible for:
- RAG retrieval
- prompt/context orchestration
- answer generation
- citations
- streaming
- conversation continuity
- chat persistence

Do NOT move any of that logic to the frontend.

B. Add persistent chat storage
Implement persistent history using Azure Cosmos DB.

Use TWO logical entities:
1. conversations
2. messages

Use either separate containers or a clean design that behaves like separate collections for:
- one user -> many conversations
- one conversation/thread -> many messages

Recommended model:
Conversation fields:
- id
- thread_id
- user_id
- user_name
- title
- created_at
- updated_at
- last_message_at
- last_user_message_preview
- last_assistant_message_preview
- message_count
- is_deleted
- metadata

Message fields:
- id
- thread_id
- user_id
- role
- content
- citations
- created_at
- sequence
- status
- metadata

Important rules:
- thread_id is one chat thread
- user_id is the owner of the thread
- one user can have many thread_ids
- “New Chat” means new thread_id for same user_id
- history must survive backend restart
- citations should be saved along with assistant messages

C. Add identity abstraction now, without blocking on real auth
Create a clean backend identity resolver module.

Create something like:
- backend/app/auth/identity.py

This module must return a normalized identity object:
- user_id
- user_name
- auth_source
- is_authenticated

Resolution rules:
1. If App Service auth headers exist later, support:
   - X-MS-CLIENT-PRINCIPAL-ID => durable user_id
   - X-MS-CLIENT-PRINCIPAL-NAME => display name / email
2. If no real auth headers exist:
   - use X-Debug-User-Id header if present
   - else use DEFAULT_LOCAL_USER_ID from env
   - else fallback to "anonymous"
3. Keep this logic isolated from routes so future auth changes do not require route rewrites.

Do NOT force real authentication in this task.
Just make backend ready for it.

D. Cosmos auth design
Support two Cosmos auth modes from env:
1. key-based auth for local/dev now
2. managed identity / DefaultAzureCredential later

Add config support for:
- COSMOS_AUTH_MODE=key or managed_identity
- COSMOS_ENDPOINT
- COSMOS_KEY
- COSMOS_DATABASE
- COSMOS_CONVERSATIONS_CONTAINER
- COSMOS_MESSAGES_CONTAINER
- COSMOS_AUTO_CREATE_CONTAINERS
- COSMOS_HISTORY_MAX_TURNS
- DEFAULT_LOCAL_USER_ID
- COSMOS_ENABLE_TTL
- COSMOS_TTL_SECONDS

Implementation rules:
- If COSMOS_AUTH_MODE=key, use endpoint + key
- If COSMOS_AUTH_MODE=managed_identity, use endpoint + DefaultAzureCredential
- Use a single Cosmos client instance for app lifetime
- Keep initialization clean and reusable

E. Add storage layer
Create clean backend storage modules, for example:
- backend/app/storage/cosmos_client.py
- backend/app/storage/chat_store.py
- backend/app/storage/models.py

Responsibilities:
- initialize cosmos client
- create/get database and containers if enabled
- create conversation
- list conversations by user
- get conversation by thread_id
- get messages by thread_id
- append user message
- append assistant message
- soft delete conversation
- update title / metadata if needed

Do NOT scatter Cosmos calls across route handlers.
Keep the routes thin.

F. Add conversation APIs
Add backend endpoints for future history UI.

Implement:
1. GET /conversations
   - returns recent conversations for resolved user
   - order by last_message_at desc
   - support optional limit query param
   - exclude deleted threads by default

2. GET /conversations/{thread_id}/messages
   - returns messages for a thread in ascending sequence
   - validate ownership if user context exists

3. POST /conversations
   - creates a new empty conversation for resolved user
   - returns thread_id and title
   - if title is not supplied, use "New Chat"

4. DELETE /conversations/{thread_id}
   - soft delete only

Optional:
5. PATCH /conversations/{thread_id}
   - rename title

Keep current endpoints working:
- POST /chat
- POST /chat/stream
- GET /health

G. Keep existing request compatibility
Current frontend testing flow already uses question + session_id style behavior.
Preserve compatibility.

Rules:
- if request contains session_id, treat it as thread_id
- if session_id is missing, create a new thread_id
- add user_id metadata internally, but do not break old frontend payloads
- responses should include session_id/thread_id in a backward-compatible way

H. Chat persistence flow
For both /chat and /chat/stream, use this sequence:

1. Resolve identity
2. Resolve thread_id
3. Load last N turns from storage for that thread
4. Persist the new user message BEFORE generation
5. Run current RAG retrieval and answer generation
6. Persist final assistant message and citations AFTER generation
7. For streaming:
   - accumulate streamed text
   - save final assistant message when complete
   - if stream errors, optionally save partial/error status

Do NOT rely on module-level in-memory dict as the source of truth anymore.
If temporary in-memory session structures are still needed internally by current agent code, they must be hydrated from persistent history first.

I. Integrate with current agent framework cleanly
The repo currently uses Agent Framework concepts and in-memory history.
Refactor carefully.

Goal:
- preserve current multi-turn RAG behavior
- replace/supplement volatile memory with Cosmos-backed history

If the existing Agent Framework history provider can be cleanly swapped, do it.
If not, create a clean adapter:
- load the most recent N turns from Cosmos
- convert them into the format expected by the agent pipeline
- inject them in one place only

Do NOT do ugly string concatenation directly inside routes.
Keep this reusable and clean.

J. History window and memory loading
Add env setting:
- COSMOS_HISTORY_MAX_TURNS=12

When generating the next answer:
- load only the latest N turns for that thread
- preserve order
- keep retrieval/context logic intact
- do not send entire lifetime history every time

K. Sequence/order handling
Implement stable message ordering.
Each message must have a sequence value within a thread.

Requirements:
- GET /conversations/{thread_id}/messages returns messages in correct order
- sequence handling should be reliable
- avoid race issues as much as practical

A simple practical approach is acceptable if implemented cleanly.

L. Title behavior
For first message in a thread:
- auto-generate a thread title from the first user message
- do not make another LLM call just for title
- truncate intelligently

Example:
question: "what are the steps to be followed for the maintenance of the 22.5 kVA transformer?"
title could become:
"Maintenance of 22.5 kVA transformer"

M. Logging and observability
Improve logs for:
- user_id
- thread_id
- number of prior turns loaded
- conversation create/load
- message save success/failure
- stream completion
- citation persistence
- storage init errors

Do NOT log secrets.

N. Error handling
Handle clearly:
- Cosmos auth failures
- container/database init failures
- failed history load
- failed message write
- failed conversation lookup
- stream persistence issues

Do not leak secrets in responses.

O. Dependencies
Update backend requirements to include what is needed for Cosmos + identity support, for example:
- azure-cosmos
- azure-identity

Keep other existing dependencies intact.

P. Config and examples
Update settings and env example files.
Create or update:
- backend/.env.example if appropriate
- any backend settings module

Include example values for:
- COSMOS_AUTH_MODE
- COSMOS_ENDPOINT
- COSMOS_KEY
- COSMOS_DATABASE
- COSMOS_CONVERSATIONS_CONTAINER
- COSMOS_MESSAGES_CONTAINER
- COSMOS_AUTO_CREATE_CONTAINERS
- COSMOS_HISTORY_MAX_TURNS
- DEFAULT_LOCAL_USER_ID
- COSMOS_ENABLE_TTL
- COSMOS_TTL_SECONDS

Q. Local development support
The backend must work locally with:
- key-based Cosmos auth
- current Streamlit tester frontend
- optional X-Debug-User-Id header for simulating different users

This is important:
I want to test the whole backend locally first, verify:
- answer quality
- citations
- follow-up continuity
- thread reopening behavior
- multiple threads per user

R. Future-ready behavior
Do NOT fully implement production auth in this task.
But make the backend ready so later we can plug in:
- App Service auth headers
- Entra-based user identity
- per-user thread history
- frontend sidebar thread loading

S. What NOT to do
- Do NOT modify the frontend in this task
- Do NOT remove current RAG/citation functionality
- Do NOT hardcode secrets
- Do NOT tightly couple the design to only one auth mode
- Do NOT make the frontend talk directly to Cosmos DB
- Do NOT keep history only in memory

T. Deliverables after making changes
After code changes, provide:
1. List of all created/modified backend files
2. Full updated code for every changed file
3. Summary of architecture changes
4. Sample backend/.env values for local testing
5. Local run commands
6. Manual test plan
7. Any assumptions made

U. Manual test plan to support
After implementation, I want to be able to run these tests:

1. Start backend locally
2. Start temporary Streamlit frontend locally
3. Ask a first question with a fixed session_id/thread_id
4. Ask a follow-up with same session_id and confirm continuity
5. Ask another follow-up and confirm citations still appear
6. Restart backend
7. Ask another follow-up with same session_id and confirm continuity still works
8. Use a different X-Debug-User-Id and confirm the threads are separated
9. Create a new chat and confirm new thread_id is generated
10. Call GET /conversations and verify prior threads are listed
11. Call GET /conversations/{thread_id}/messages and verify full ordered history
12. Confirm deleted conversations do not show in default list results

V. Repo-aware implementation hint
This repo already has backend orchestration and currently uses in-memory history.
Do not rewrite the whole app.
Refactor around the current backend architecture and preserve the existing API behavior wherever possible.

Now inspect the current backend codebase under backend/ and implement these changes end-to-end.
