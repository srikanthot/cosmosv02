"""Application settings loaded from environment variables.

All configuration is driven by .env so the same codebase works across
dev / staging / production without code changes.
"""

import os

from dotenv import load_dotenv

load_dotenv(override=True)

# ---------------------------------------------------------------------------
# Azure OpenAI (GCC High — openai.azure.us)
# ---------------------------------------------------------------------------
AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_API_VERSION: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")
AZURE_OPENAI_CHAT_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "")
# Agent Framework SDK reads AZURE_OPENAI_CHAT_DEPLOYMENT_NAME; fallback to legacy var
AZURE_OPENAI_CHAT_DEPLOYMENT_NAME: str = os.getenv(
    "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME",
    os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", ""),
)
AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT", "")

# ---------------------------------------------------------------------------
# Azure AI Search (GCC High — search.azure.us)
# ---------------------------------------------------------------------------
AZURE_SEARCH_ENDPOINT: str = os.getenv("AZURE_SEARCH_ENDPOINT", "")
AZURE_SEARCH_API_KEY: str = os.getenv("AZURE_SEARCH_API_KEY", "")
AZURE_SEARCH_INDEX: str = os.getenv("AZURE_SEARCH_INDEX", "rag-psegtechm-index-finalv2")

# ---------------------------------------------------------------------------
# Index field mappings — must match the actual index schema exactly.
# ---------------------------------------------------------------------------
SEARCH_CONTENT_FIELD: str = os.getenv("SEARCH_CONTENT_FIELD", "chunk")
SEARCH_SEMANTIC_CONTENT_FIELD: str = os.getenv("SEARCH_SEMANTIC_CONTENT_FIELD", "chunk_for_semantic")
SEARCH_VECTOR_FIELD: str = os.getenv("SEARCH_VECTOR_FIELD", "text_vector")
SEARCH_FILENAME_FIELD: str = os.getenv("SEARCH_FILENAME_FIELD", "source_file")
SEARCH_URL_FIELD: str = os.getenv("SEARCH_URL_FIELD", "source_url")
SEARCH_CHUNK_ID_FIELD: str = os.getenv("SEARCH_CHUNK_ID_FIELD", "chunk_id")
SEARCH_TITLE_FIELD: str = os.getenv("SEARCH_TITLE_FIELD", "title")
SEARCH_SECTION1_FIELD: str = os.getenv("SEARCH_SECTION1_FIELD", "header_1")
SEARCH_SECTION2_FIELD: str = os.getenv("SEARCH_SECTION2_FIELD", "header_2")
SEARCH_SECTION3_FIELD: str = os.getenv("SEARCH_SECTION3_FIELD", "header_3")
# Leave blank if the index has no page number field (new layout-based index has none)
SEARCH_PAGE_FIELD: str = os.getenv("SEARCH_PAGE_FIELD", "")

# ---------------------------------------------------------------------------
# Retrieval tuning
# ---------------------------------------------------------------------------
TOP_K: int = int(os.getenv("TOP_K", "5"))
# How many candidates to fetch before diversity/gap filters trim to TOP_K.
RETRIEVAL_CANDIDATES: int = int(os.getenv("RETRIEVAL_CANDIDATES", "15"))
VECTOR_K: int = int(os.getenv("VECTOR_K", "50"))

# ---------------------------------------------------------------------------
# Retrieval quality
# ---------------------------------------------------------------------------
USE_SEMANTIC_RERANKER: bool = os.getenv("USE_SEMANTIC_RERANKER", "true").lower() == "true"
SEMANTIC_CONFIG_NAME: str = os.getenv("SEMANTIC_CONFIG_NAME", "manual-semantic-config")
QUERY_LANGUAGE: str = os.getenv("QUERY_LANGUAGE", "en-us")
MIN_RESULTS: int = int(os.getenv("MIN_RESULTS", "2"))
# Gate threshold for base RRF/hybrid scores (range 0.01–0.033 for Azure hybrid)
MIN_AVG_SCORE: float = float(os.getenv("MIN_AVG_SCORE", "0.02"))
# Gate threshold for semantic reranker scores (range 0.0–4.0); used when reranker active
MIN_RERANKER_SCORE: float = float(os.getenv("MIN_RERANKER_SCORE", "0.3"))
DIVERSITY_BY_SOURCE: bool = os.getenv("DIVERSITY_BY_SOURCE", "true").lower() == "true"
MAX_CHUNKS_PER_SOURCE: int = int(os.getenv("MAX_CHUNKS_PER_SOURCE", "2"))
# When one source's top score >= DOMINANT_SOURCE_SCORE_RATIO × next source's top score,
# that source is "dominant" and may contribute up to MAX_CHUNKS_DOMINANT_SOURCE chunks.
DOMINANT_SOURCE_SCORE_RATIO: float = float(os.getenv("DOMINANT_SOURCE_SCORE_RATIO", "1.5"))
MAX_CHUNKS_DOMINANT_SOURCE: int = int(os.getenv("MAX_CHUNKS_DOMINANT_SOURCE", "4"))
# After diversity filtering, discard chunks whose effective score < SCORE_GAP_MIN_RATIO × top.
SCORE_GAP_MIN_RATIO: float = float(os.getenv("SCORE_GAP_MIN_RATIO", "0.55"))
TRACE_MODE: bool = os.getenv("TRACE_MODE", "true").lower() == "true"
