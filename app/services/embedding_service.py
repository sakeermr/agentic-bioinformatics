"""
services/embedding_service.py
------------------------------
Generates text embeddings via OpenAI and manages the ChromaDB vector store.
Used by the Literature Agent for RAG (retrieval-augmented generation).
"""

import logging
from typing import Optional
import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config.settings import OPENAI_API_KEY, EMBEDDING_MODEL, CHROMA_DB_PATH

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Handles embedding generation and ChromaDB operations.
    Each research session uses a collection namespaced by UniProt ID.
    """

    def __init__(self):
        self._openai_client = None
        self._chroma_client = None
        self._init_clients()

    def _init_clients(self):
        """Set up OpenAI embedding client and ChromaDB persistent client."""
        if OPENAI_API_KEY:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(api_key=OPENAI_API_KEY)
                logger.info("Embedding client ready (model: %s)", EMBEDDING_MODEL)
            except ImportError:
                logger.warning("openai package not installed — embeddings disabled")

        try:
            self._chroma_client = chromadb.PersistentClient(
                path=str(CHROMA_DB_PATH),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            logger.info("ChromaDB initialized at %s", CHROMA_DB_PATH)
        except Exception as exc:
            logger.error("ChromaDB init failed: %s", exc)

    # ── Public API ────────────────────────────────────────────

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings for a list of text strings."""
        if not self._openai_client:
            logger.warning("No embedding client — returning empty embeddings")
            return [[] for _ in texts]

        # OpenAI recommends replacing newlines for embedding quality
        cleaned = [t.replace("\n", " ") for t in texts]
        response = self._openai_client.embeddings.create(
            input=cleaned, model=EMBEDDING_MODEL
        )
        return [item.embedding for item in response.data]

    def store_abstracts(self, uniprot_id: str, papers: list[dict]) -> None:
        """
        Chunk and store paper abstracts in ChromaDB for later retrieval.

        Args:
            uniprot_id: Used as the collection name.
            papers: List of dicts with keys: pmid, title, abstract.
        """
        if not self._chroma_client:
            return

        collection_name = f"protein_{uniprot_id.lower()}"
        try:
            # Get or create a collection for this protein
            collection = self._chroma_client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )

            documents, metadatas, ids = [], [], []
            for paper in papers:
                abstract = paper.get("abstract", "")
                if not abstract:
                    continue
                doc_id = f"{uniprot_id}_{paper.get('pmid', 'unknown')}"
                documents.append(f"{paper.get('title', '')}. {abstract}")
                metadatas.append({
                    "pmid": paper.get("pmid", ""),
                    "title": paper.get("title", ""),
                    "year": str(paper.get("year", "")),
                })
                ids.append(doc_id)

            if documents:
                collection.upsert(documents=documents, metadatas=metadatas, ids=ids)
                logger.info("Stored %d abstracts in ChromaDB collection '%s'", len(documents), collection_name)

        except Exception as exc:
            logger.error("Failed to store abstracts in ChromaDB: %s", exc)

    def retrieve_relevant(self, uniprot_id: str, query: str, n_results: int = 5) -> list[str]:
        """
        Retrieve the most relevant abstract chunks for a query.

        Args:
            uniprot_id: Collection to search.
            query: Natural language query.
            n_results: Number of chunks to return.

        Returns:
            List of relevant text chunks.
        """
        if not self._chroma_client:
            return []

        collection_name = f"protein_{uniprot_id.lower()}"
        try:
            collection = self._chroma_client.get_collection(name=collection_name)
            results = collection.query(query_texts=[query], n_results=n_results)
            return results["documents"][0] if results["documents"] else []
        except Exception as exc:
            logger.warning("ChromaDB retrieval failed: %s", exc)
            return []


# Module-level singleton
embedding_service = EmbeddingService()
