"""CitationProvider — deduplicates and structures citations.

Converts the raw list of retrieved result dicts into a clean, deduplicated
list of Citation objects ready for the structured SSE citations event.

Deduplication key is chunk_id (globally unique per chunk in the index).
Falls back to source+url if chunk_id is missing.
Results are assumed to arrive ordered by relevance score descending, so the
first occurrence of each key is the most relevant chunk.
"""

from app.agent_runtime.context_providers import _section_path
from app.api.schemas import Citation


def build_citations(results: list[dict]) -> list[Citation]:
    """Build a deduplicated, ordered citation list from retrieved results.

    Parameters
    ----------
    results:
        Normalised result dicts from RetrievalTool — keys: source, title,
        url, chunk_id, section1/2/3, score. Ordered highest relevance first.

    Returns
    -------
    list[Citation]
        One Citation per unique chunk_id (or source+url), in order of
        first appearance (highest relevance).
    """
    seen: set[str] = set()
    citations: list[Citation] = []

    for r in results:
        # chunk_id is globally unique per indexed chunk
        key = r.get("chunk_id") or f"{r['source']}|{r.get('url', '')}"
        if key not in seen:
            seen.add(key)
            citations.append(
                Citation(
                    source=r["source"],
                    title=r.get("title", ""),
                    section=_section_path(r),
                    url=r.get("url", ""),
                    chunk_id=r.get("chunk_id", ""),
                    page=r.get("page", ""),
                )
            )

    return citations
