# PSEG Tech Manual Agent

A streaming RAG chatbot for PSEG field technicians. Ask questions against internal technical manuals and get grounded, citation-backed answers in real time.

**Stack:** FastAPI · Azure AI Search (hybrid + vector) · Azure OpenAI (GCC High) · Microsoft Agent Framework SDK · Azure Cosmos DB · Streamlit

---

## Microsoft Agent Framework SDK

This repo uses the **Microsoft Agent Framework SDK** (`agent-framework-core==1.0.0rc3`) for all LLM orchestration:

| SDK primitive | Role in this repo |
|---|---|
| `AzureOpenAIChatClient` | Azure OpenAI connection (API-key auth, GCC High endpoint) |
| `client.as_agent()` | Creates the `PSEGTechManualAgent` ChatAgent |
| `RagContextProvider(BaseContextProvider)` | Injects retrieved Azure AI Search chunks via `before_run()` |
| `InMemoryHistoryProvider` | Warm-session multi-turn memory (in-process) |
| `CosmosHistoryProvider` | Cold-start history injection from Cosmos DB on first turn per process restart |
| `agent.run(stream=True)` → `ResponseStream` | Streams tokens to the SSE pipeline |

---

## Why not Azure AI Foundry Managed Agents?

Azure AI Foundry Managed Agents (and Azure AI Agent Service) are **not available in Azure Government (GCC High)**. This repo implements the same architectural pattern using the Microsoft Agent Framework SDK directly — `AzureOpenAIChatClient` + `ChatAgent` + `ContextProvider` + `InMemoryHistoryProvider` — without requiring the managed service.

---

## How it works

The FastAPI route is intentionally thin. It validates the request, creates a session, and hands off to `AgentRuntime.run_stream()`. All orchestration lives in `agent_runtime/`.

```
POST /chat/stream
        ↓
    routes.py              thin: validate → create session → call runtime
        ↓
  AgentRuntime             owns orchestration
    1. RetrievalTool       embed query → hybrid search Azure AI Search
    2. GATE                abort early if evidence count or avg score too low
    3. rag_provider        store results in session.state (no double Search call)
    4. af_agent.run()      Agent Framework ChatAgent (AzureOpenAIChatClient)
         • InMemoryHistoryProvider.before_run()   load conversation history
         • RagContextProvider.before_run()        inject chunks as instructions
         • LLM streams tokens via ResponseStream
    5. SSE stream          yield tokens + keepalive pings
    6. CitationProvider    dedup + emit structured citations event
        ↓
  SSE stream → Streamlit UI
```

**Hybrid search:** The index has no built-in vectorizer, so `aoai_embeddings.embed()` generates query vectors in the API. Each search call sends both a keyword query and a `VectorizedQuery` against the index's vector field.

**Confidence gate:** If retrieval returns fewer than `MIN_RESULTS` chunks, or the average score is below the gate threshold, the agent short-circuits with a clarifying question instead of hallucinating. When semantic reranker is active, the gate uses `MIN_RERANKER_SCORE` (0–4 scale). When not active, it uses `MIN_AVG_SCORE` (RRF 0.01–0.033 scale).

**Diversity filter:** At most `MAX_CHUNKS_PER_SOURCE` chunks per source file are kept, so the answer doesn't over-index on one document.

**Keepalive pings:** The backend emits `event: ping / data: keepalive` every ~20 seconds during long answers to prevent proxy/browser SSE timeouts.

---

## Persistent Chat History (Cosmos DB)

Conversation history is stored in **Azure Cosmos DB for NoSQL** with two containers:

| Container | Partition key | One document per |
|---|---|---|
| `conversations` | `/user_id` | chat thread |
| `messages` | `/thread_id` | message turn |

**How multi-turn context works:**

1. Every user question is persisted to Cosmos before the LLM is called.
2. Every assistant answer + citations are persisted after generation.
3. On the first request to a thread (cold start — e.g. after server restart), prior messages are loaded from Cosmos and injected once as context before the LLM call.
4. On subsequent requests within the same process (warm session), the Agent Framework `InMemoryHistoryProvider` holds in-process turn history — no redundant Cosmos reads.

**Local testing without real user authentication:**

The backend resolves user identity from request headers using this priority:

1. `X-MS-CLIENT-PRINCIPAL-ID` — Azure App Service managed auth (production)
2. `X-Debug-User-Id` — debug header for simulating different local users
3. `DEFAULT_LOCAL_USER_ID` env var — default local identity (`local-dev`)
4. `"anonymous"` — final fallback

During local development, all conversations are stored under the `DEFAULT_LOCAL_USER_ID` value (`local-dev` by default). This proves true persistence — data survives server restarts and browser refreshes — even before real auth is configured. When production auth is enabled later, the same storage model works identically with real user IDs.

**Required Cosmos environment variables:**

```
COSMOS_AUTH_MODE=key
COSMOS_ENDPOINT=https://<account>.documents.azure.com:443/
COSMOS_KEY=<primary-key>
COSMOS_DATABASE=ragchatdb
COSMOS_CONVERSATIONS_CONTAINER=conversations
COSMOS_MESSAGES_CONTAINER=messages
COSMOS_AUTO_CREATE_CONTAINERS=false
COSMOS_HISTORY_MAX_TURNS=12
```

**To switch to managed identity in production** (Azure App Service), set `COSMOS_AUTH_MODE=managed_identity` and remove `COSMOS_KEY`. The backend will use `DefaultAzureCredential` automatically.

---

## Azure AI Search Setup

If you are setting up the index from scratch (new Azure subscription), see
**[AZURE_SEARCH_SETUP.md](AZURE_SEARCH_SETUP.md)** for the complete JSON definitions
for the data source, index schema, skillset (OCR + text split + Ada-002 embeddings),
and indexer.

---

## Setup (Windows Git Bash)

### 1. Clone and enter the repo

```bash
cd pseg-agent-pattern-python
```

### 2. Backend environment

```bash
python -m venv .venv-backend
source .venv-backend/Scripts/activate
pip install -r backend/requirements.txt
```

### 3. Frontend environment

Open a second terminal:

```bash
python -m venv .venv-frontend
source .venv-frontend/Scripts/activate
pip install -r frontend/requirements.txt
```

### 4. Configure

```bash
# Backend
cp backend/.env.example backend/.env

# Frontend
cp .env.frontend.example frontend/.env
```

Open each `.env` and fill in your values. Key things to note:

- `SEARCH_*_FIELD` variables must match your actual Azure AI Search index field names exactly.
- `SEARCH_PAGE_FIELD` should be left blank if your index has no page number field — an empty value means it is skipped in the select list and no page info is shown in citations.
- `SEARCH_SECTION1/2/3_FIELD` map to the three header fields in the layout-based index (`header_1`, `header_2`, `header_3`). Leave blank if unused.
- `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT` must point to an embeddings model deployment (e.g. `text-embedding-ada-002`). This generates query vectors at search time.
- `USE_SEMANTIC_RERANKER=true` and `SEMANTIC_CONFIG_NAME=manual-semantic-config` enable the semantic reranker. The gate will use `MIN_RERANKER_SCORE` (0–4 scale) instead of `MIN_AVG_SCORE` (RRF 0.01–0.033 scale) when the reranker is active.

### 5. Run

```bash
# Terminal 1 — backend (from repo root or backend/)
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend (from repo root or frontend/)
cd frontend
streamlit run app.py --server.port 8501
```

Open [http://localhost:8501](http://localhost:8501).

---

## Environment variables

| Variable | Required | Notes |
|---|---|---|
| `AZURE_OPENAI_ENDPOINT` | yes | `https://your-resource.openai.azure.us/` |
| `AZURE_OPENAI_API_KEY` | yes | |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | yes | e.g. `gpt-4o-mini` (legacy name) |
| `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME` | yes | Same value — read by Agent Framework SDK |
| `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT` | yes | e.g. `text-embedding-ada-002` |
| `AZURE_OPENAI_API_VERSION` | no | Default: `2024-06-01` |
| `AZURE_SEARCH_ENDPOINT` | yes | `https://your-search.search.azure.us` |
| `AZURE_SEARCH_API_KEY` | yes | |
| `AZURE_SEARCH_INDEX` | yes | Default: `rag-psegtechm-index-finalv2` |
| `SEARCH_CONTENT_FIELD` | no | Default: `chunk` — main text field sent to LLM |
| `SEARCH_SEMANTIC_CONTENT_FIELD` | no | Default: `chunk_for_semantic` — used by semantic reranker prioritization |
| `SEARCH_VECTOR_FIELD` | no | Default: `text_vector` — 1536-dim Ada-002 vector field |
| `SEARCH_FILENAME_FIELD` | no | Default: `source_file` |
| `SEARCH_URL_FIELD` | no | Default: `source_url` |
| `SEARCH_CHUNK_ID_FIELD` | no | Default: `chunk_id` |
| `SEARCH_TITLE_FIELD` | no | Default: `title` |
| `SEARCH_SECTION1_FIELD` | no | Default: `header_1` — top-level section heading |
| `SEARCH_SECTION2_FIELD` | no | Default: `header_2` — sub-section heading |
| `SEARCH_SECTION3_FIELD` | no | Default: `header_3` — sub-sub-section heading |
| `SEARCH_PAGE_FIELD` | no | Default: `` (empty) — leave blank if index has no page number field |
| `TOP_K` | no | Default: `5`. Max chunks returned after diversity filter |
| `RETRIEVAL_CANDIDATES` | no | Default: `15`. Raw candidates fetched before diversity filter |
| `VECTOR_K` | no | Default: `50`. Nearest-neighbor count for vector query |
| `USE_SEMANTIC_RERANKER` | no | Default: `true`. Requires a semantic configuration in the index |
| `SEMANTIC_CONFIG_NAME` | no | Default: `manual-semantic-config`. Name of the semantic config in your index |
| `QUERY_LANGUAGE` | no | Default: `en-us`. Language hint for semantic reranker |
| `MIN_RESULTS` | no | Default: `2`. Confidence gate — min chunks required to answer |
| `MIN_AVG_SCORE` | no | Default: `0.02`. Gate threshold for base RRF scores (range 0.01–0.033); used when reranker is off |
| `MIN_RERANKER_SCORE` | no | Default: `0.3`. Gate threshold for semantic reranker scores (range 0–4); used when `USE_SEMANTIC_RERANKER=true` |
| `DIVERSITY_BY_SOURCE` | no | Default: `true`. Caps chunks per source file |
| `MAX_CHUNKS_PER_SOURCE` | no | Default: `2`. Max chunks from any single source |
| `DOMINANT_SOURCE_SCORE_RATIO` | no | Default: `1.5`. A source is "dominant" when its top effective score ≥ this × the next source's top score |
| `MAX_CHUNKS_DOMINANT_SOURCE` | no | Default: `4`. Max chunks allowed from the dominant source |
| `SCORE_GAP_MIN_RATIO` | no | Default: `0.55`. Discard chunks whose effective score falls below this fraction of the top score |
| `TRACE_MODE` | no | Default: `true`. Logs ranked chunks with source, section, reranker score, heading, and content preview |
| `ALLOWED_ORIGINS` | no | Default: `*`. Comma-separated CORS origins for the backend. Set to your frontend URL in Azure (e.g. `https://pseg-frontend.azurewebsites.net`) |
| `BACKEND_URL` | no | Default: `http://localhost:8000`. Frontend uses this to reach the API. Set to your backend App Service URL in Azure |
| `FRONTEND_TITLE` | no | Default: `PSEG Tech Manual Agent`. Browser tab title for the Streamlit app |
| `COSMOS_AUTH_MODE` | no | `key` (default, local) or `managed_identity` (production App Service) |
| `COSMOS_ENDPOINT` | yes* | `https://<account>.documents.azure.com:443/` — omit to disable persistent history |
| `COSMOS_KEY` | yes* | Primary key — required when `COSMOS_AUTH_MODE=key` |
| `COSMOS_DATABASE` | no | Default: `ragchatdb` |
| `COSMOS_CONVERSATIONS_CONTAINER` | no | Default: `conversations` |
| `COSMOS_MESSAGES_CONTAINER` | no | Default: `messages` |
| `COSMOS_AUTO_CREATE_CONTAINERS` | no | Default: `false`. Set `true` only if you want the backend to create the DB/containers on startup |
| `COSMOS_HISTORY_MAX_TURNS` | no | Default: `12`. Max prior messages injected into LLM context per turn |
| `COSMOS_ENABLE_TTL` | no | Default: `false`. Set `true` to auto-expire documents after `COSMOS_TTL_SECONDS` |
| `COSMOS_TTL_SECONDS` | no | Default: `7776000` (90 days). Blank = use default |
| `DEFAULT_LOCAL_USER_ID` | no | Default: `local-dev`. Used as `user_id` when no auth headers are present |

## Testing Cosmos history locally

### Run the smoke test script

```bash
# Terminal 1 — activate backend venv
source .venv-backend/Scripts/activate
cd backend
python ../scripts/test_cosmos_history.py
```

This creates `thread_test_001` under user `local-dev`, writes a user message and an
assistant message with a citation, reads them back, and prints a pass/fail report.
Run it a second time to confirm the data is still there (persistence verified).

### Verify after page refresh

Start the backend and Streamlit frontend, ask a question in the chat UI, then:
1. Stop the backend (`Ctrl+C`).
2. Restart it (`uvicorn app.main:app --reload --port 8000`).
3. Reload the Streamlit page.
4. Select the same conversation from the sidebar — prior messages are reloaded from Cosmos.

### Verify in Azure Portal

1. Open your Cosmos DB account in the Azure Portal.
2. Go to **Data Explorer** → `ragchatdb` → `conversations` → **Items**.
3. You should see one document per chat thread (partition key = `user_id`).
4. Go to **Data Explorer** → `ragchatdb` → `messages` → **Items**.
5. You should see one document per message (partition key = `thread_id`).

## Project layout

```
pseg-agent-pattern-python/
├── .gitignore
├── .env.backend.example               # Backend env template (copy to backend/.env)
├── .env.frontend.example              # Frontend env template (copy to frontend/.env)
├── README.md
├── DEPLOYMENT.md                      # Azure App Service deployment guide
├── AZURE_SEARCH_SETUP.md              # Index / skillset / indexer JSON for Azure setup
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── __init__.py
│       ├── main.py                        # FastAPI app, CORS, /health
│       ├── config/
│       │   ├── __init__.py
│       │   └── settings.py               # All env vars via python-dotenv
│       ├── api/
│       │   ├── __init__.py
│       │   ├── routes.py                  # POST /chat/stream (thin)
│       │   └── schemas.py                 # ChatRequest, Citation, CitationsPayload
│       ├── agent_runtime/
│       │   ├── __init__.py
│       │   ├── agent.py                   # AgentRuntime — orchestrator
│       │   ├── session.py                 # AgentSession — per-request state
│       │   ├── af_rag_context_provider.py # Agent Framework RAG ContextProvider
│       │   ├── context_providers.py       # Evidence block formatter
│       │   ├── citation_provider.py       # Citation dedup + structuring
│       │   └── prompts.py                 # System prompt templates
│       ├── tools/
│       │   ├── __init__.py
│       │   └── retrieval_tool.py          # Hybrid search + adaptive diversity + TOC filter
│       └── llm/
│           ├── __init__.py
│           ├── af_agent_factory.py        # Agent Framework singleton (AzureOpenAIChatClient)
│           └── aoai_embeddings.py         # Query embedding generation
└── frontend/
    ├── requirements.txt
    └── app.py                             # Streamlit UI + SSE consumer
```

FEEDBACK_URL = os.getenv("FEEDBACK_URL", "").strip()
if FEEDBACK_URL:
    st.markdown("### Feedback")
    st.markdown(
        f'<a href="{FEEDBACK_URL}" target="_blank">'
        f'<button style="width:100%;padding:10px;border:none;border-radius:8px;'
        f'background:#f26522;color:white;font-weight:600;cursor:pointer;">'
        f'📝 Share Feedback</button></a>',
        unsafe_allow_html=True,
    )


    What does Buried Underground Distribution (BUD) mean in the Plant Engineering Policies and Procedures manual?
What are the work procedures involved in BUD joint trench installations?
What are the requirements for revenue metering equipment in customer electrical installations?
What are the general specifications for a customer-owned 26.4 kV outdoor substation?
Why are surge arresters used in substations, and what purpose do they serve?
What is an Arc Flash Hazard Calculation Study, and why is it important for electrical systems?
 
 
A developer is planning to install an underground electrical distribution system for a new residential project. What procedures should be followed for Buried Underground Distribution (BUD) installation?
A customer is planning to build a 26.4 kV outdoor substation to connect to the utility system. What approvals and design requirements must be completed before construction begins?
During the design of a customer electrical facility, engineers are concerned about worker safety around high-voltage equipment. When should an Arc Flash Hazard Calculation Study be performed and why?
A company wants to install a solar generation system and connect it to the utility grid as a Non-Utility Generator (NUG). What requirements must be met before it can be connected to the utility system?
During a storm, a voltage surge damages equipment at a substation. How do surge arresters help protect electrical equipment in such situations?
 
What are the guidelines that should be followed for disconnecting switches for Customer-Owned 26.4 kV Outdoor Substation?
 
Right now, I am installing the Underground Plastic Piping, so what are the safety measures I should take
 
So I went to a location where one customer requested the Instructions for the PSE&G Residential Application for Gas Service, what should i have to say
 
I was at one location, and I suspect Theft of Service and Tampering, so what should i have to do
 
We removed a light at this pole a few months ago. If the customer wants a new light at the same exact pole within a year, do we treat it as a replacement or a brand-new install
 
