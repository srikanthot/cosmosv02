"""Azure OpenAI embeddings wrapper for GCC High.

The Azure AI Search index has NO built-in vectorizer configured, so query
embeddings must be generated here in the API before issuing the hybrid
search. This module calls the embeddings deployment and returns a list[float]
vector ready for VectorizedQuery.
"""

from openai import AzureOpenAI

from app.config.settings import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_API_VERSION,
    AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT,
    AZURE_OPENAI_ENDPOINT,
)


def _get_client() -> AzureOpenAI:
    """Return an AzureOpenAI client configured for GCC High."""
    return AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
    )


def embed(text: str) -> list[float]:
    """Generate an embedding vector for the given text.

    Parameters
    ----------
    text:
        The query string to embed.

    Returns
    -------
    list[float]
        Embedding vector from the configured embeddings deployment.
        Dimensionality matches the index's vector field.

    Raises
    ------
    openai.OpenAIError
        Propagated to the caller (RetrievalTool handles it).
    """
    client = _get_client()

    response = client.embeddings.create(
        model=AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT,
        input=text,
    )

    return response.data[0].embedding
