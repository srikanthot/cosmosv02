"""ContextProvider — formats retrieved evidence into grounded prompt context.

Each retrieved chunk is formatted as a numbered evidence block containing
title, source file, section breadcrumb, URL, chunk ID, and the chunk content.
ocr_fallback_text is intentionally excluded — the LLM receives only the
structured layout-extracted chunk text.
"""


def _section_path(r: dict) -> str:
    """Build a readable section breadcrumb from header_1/2/3 fields."""
    parts = [r.get("section1") or "", r.get("section2") or "", r.get("section3") or ""]
    return " > ".join(p for p in parts if p)


def build_context_blocks(results: list[dict]) -> str:
    """Format retrieved chunks into numbered, labeled evidence blocks.

    Each block carries a header with source metadata followed by the raw chunk
    content. The LLM prompt instructs the model to answer only from these blocks
    and to reference them by their [N] label.

    Parameters
    ----------
    results:
        Normalised result dicts from RetrievalTool — keys: content, title,
        source, url, chunk_id, section1, section2, section3, score.

    Returns
    -------
    str
        A single string with one evidence block per chunk, separated by
        horizontal rules.
    """
    blocks: list[str] = []
    for i, r in enumerate(results, start=1):
        lines = [f"[{i}]"]
        if r.get("title"):
            lines.append(f"Title: {r['title']}")
        lines.append(f"Source: {r['source']}")
        section = _section_path(r)
        if section:
            lines.append(f"Section: {section}")
        if r.get("url"):
            lines.append(f"URL: {r['url']}")
        if r.get("chunk_id"):
            lines.append(f"Chunk ID: {r['chunk_id']}")
        lines.append("Content:")
        lines.append(r["content"])
        blocks.append("\n".join(lines))

    return "\n\n---\n\n".join(blocks)
