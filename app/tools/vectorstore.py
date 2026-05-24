"""
tools/vectorstore.py
---------------------
Thin wrapper around EmbeddingService for use within agent pipelines.
Agents import this instead of the service directly for cleaner separation.
"""

from app.services.embedding_service import embedding_service


def store_literature(uniprot_id: str, papers: list[dict]) -> None:
    """Store paper abstracts in the vector store."""
    embedding_service.store_abstracts(uniprot_id, papers)


def retrieve_context(uniprot_id: str, query: str, n: int = 5) -> list[str]:
    """Retrieve relevant abstract chunks for a query."""
    return embedding_service.retrieve_relevant(uniprot_id, query, n_results=n)
