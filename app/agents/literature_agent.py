"""
agents/literature_agent.py
---------------------------
Searches PubMed, stores abstracts in ChromaDB, and uses LLM + RAG
to generate a scientific literature review.
"""

import logging
from app.models.schemas import LiteratureData, PaperRecord
from app.tools.pubmed_tools import search_pubmed, fetch_pubmed_abstracts, search_europepmc
from app.tools.vectorstore import store_literature, retrieve_context
from app.services.llm_service import llm_service
from app.config.settings import MAX_PUBMED_RESULTS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert biomedical scientist writing a literature review section 
for a scientific research report. Your writing is evidence-based, precise, and publication-quality.
Cite specific findings from the provided abstracts. Use formal scientific language.
Structure your response as flowing paragraphs — no bullet points."""


class LiteratureAgent:
    """Searches literature, builds RAG index, generates a review via LLM."""

    def run(self, uniprot_id: str, protein_name: str, gene_name: str) -> LiteratureData:
        """
        Full literature pipeline: search → fetch → store → retrieve → synthesize.

        Args:
            uniprot_id: Protein accession (used as ChromaDB collection namespace).
            protein_name: Full protein name for richer search queries.
            gene_name: Gene symbol.

        Returns:
            LiteratureData with papers and LLM-generated review.
        """
        logger.info("[LiteratureAgent] Starting for %s (%s)", gene_name, protein_name)

        # ── 1. Build search query ─────────────────────────────
        query = self._build_query(protein_name, gene_name)
        logger.info("[LiteratureAgent] Query: %s", query)

        # ── 2. Search PubMed ──────────────────────────────────
        pmids = search_pubmed(query, max_results=MAX_PUBMED_RESULTS)
        papers_raw = []

        if pmids:
            papers_raw = fetch_pubmed_abstracts(pmids)

        # ── 3. Fallback to Europe PMC if PubMed fails ─────────
        if not papers_raw:
            logger.warning("[LiteratureAgent] PubMed returned no results; trying Europe PMC")
            papers_raw = search_europepmc(query, max_results=10)

        logger.info("[LiteratureAgent] Retrieved %d papers", len(papers_raw))

        # ── 4. Store abstracts in ChromaDB ────────────────────
        if papers_raw:
            store_literature(uniprot_id, papers_raw)

        # ── 5. RAG: retrieve most relevant chunks ─────────────
        rag_query = f"{gene_name} {protein_name} biological function disease mechanism"
        context_chunks = retrieve_context(uniprot_id, rag_query, n=6)

        # ── 6. Generate literature review via LLM ─────────────
        review = self._generate_review(gene_name, protein_name, papers_raw, context_chunks)

        # ── 7. Convert to schema objects ──────────────────────
        paper_records = [
            PaperRecord(
                pmid=p.get("pmid", ""),
                title=p.get("title", "Untitled"),
                abstract=p.get("abstract", ""),
                authors=p.get("authors", []),
                journal=p.get("journal", ""),
                year=p.get("year"),
                url=p.get("url", ""),
            )
            for p in papers_raw
        ]

        logger.info("[LiteratureAgent] Done — %d papers, review generated", len(paper_records))
        return LiteratureData(
            query_used=query,
            papers=paper_records,
            literature_review=review,
        )

    # ── Private Helpers ───────────────────────────────────────

    @staticmethod
    def _build_query(protein_name: str, gene_name: str) -> str:
        """Build an effective PubMed query for the protein."""
        terms = []
        if gene_name and gene_name != "Unknown":
            terms.append(f'"{gene_name}"[Gene Name]')
        if protein_name and protein_name != "Unknown protein":
            clean = protein_name.split(" isoform")[0].split(",")[0]
            terms.append(f'"{clean}"')
        terms.append("function OR mechanism OR disease OR pathway")
        return " AND ".join(terms[:2]) + f" AND ({terms[-1]})" if len(terms) >= 3 else " ".join(terms)

    @staticmethod
    def _generate_review(
        gene_name: str,
        protein_name: str,
        papers: list[dict],
        rag_chunks: list[str],
    ) -> str:
        """Use LLM to synthesize a literature review from abstracts."""
        if not papers:
            return "Insufficient literature data available to generate a review."

        # Build context from top abstracts + RAG chunks
        abstract_context = "\n\n".join(
            f"[Paper {i+1}] {p.get('title', '')}\n{p.get('abstract', '')}"
            for i, p in enumerate(papers[:8])
            if p.get("abstract")
        )

        rag_context = "\n\n".join(rag_chunks) if rag_chunks else ""

        user_prompt = f"""
Write a comprehensive literature review for the protein **{protein_name}** (gene: {gene_name}).

Use the following research paper abstracts as your primary evidence:

--- PAPER ABSTRACTS ---
{abstract_context}

--- ADDITIONAL CONTEXT (from vector search) ---
{rag_context}

Your literature review should:
1. Summarize the key biological roles and mechanisms established in the literature
2. Describe the protein's involvement in disease pathways
3. Highlight recent research advances
4. Be 3–5 paragraphs, written in publication-quality English
5. Reference specific findings from the papers above

Write the literature review now:
"""

        try:
            return llm_service.complete(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.3,
                max_tokens=1500,
            )
        except Exception as exc:
            logger.error("[LiteratureAgent] LLM synthesis failed: %s", exc)
            return f"Literature review generation failed: {exc}"
