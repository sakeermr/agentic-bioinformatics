"""
services/citation_service.py
-----------------------------
Tracks and formats citations/references for the final scientific report.
"""

import logging
from app.models.schemas import PaperRecord

logger = logging.getLogger(__name__)


class CitationService:
    """Collects papers and renders formatted reference lists."""

    def __init__(self):
        self._papers: list[PaperRecord] = []

    def add_papers(self, papers: list[PaperRecord]) -> None:
        """Add a list of papers; deduplicates by PMID."""
        existing_pmids = {p.pmid for p in self._papers}
        for paper in papers:
            if paper.pmid not in existing_pmids:
                self._papers.append(paper)
                existing_pmids.add(paper.pmid)

    def format_references(self) -> str:
        """Return a numbered Markdown reference list."""
        if not self._papers:
            return "_No references available._"

        lines = []
        for i, paper in enumerate(self._papers, start=1):
            authors = ", ".join(paper.authors[:3])
            if len(paper.authors) > 3:
                authors += " et al."
            year = f"({paper.year})" if paper.year else ""
            journal = f"*{paper.journal}*" if paper.journal else ""
            url = f" [{paper.pmid}](https://pubmed.ncbi.nlm.nih.gov/{paper.pmid}/)" if paper.pmid else ""
            lines.append(f"{i}. {authors} {year}. {paper.title}. {journal}.{url}")

        return "\n".join(lines)

    def get_papers(self) -> list[PaperRecord]:
        return self._papers

    def reset(self) -> None:
        self._papers = []
