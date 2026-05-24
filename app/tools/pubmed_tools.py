"""
tools/pubmed_tools.py
---------------------
Fetches research papers from NCBI PubMed using the E-utilities API.
Also provides a fallback search via Europe PMC.
"""

import logging
import time
import requests
from typing import Any, Optional
import xml.etree.ElementTree as ET

from app.config.settings import (
    PUBMED_BASE_URL, EUROPEPMC_BASE_URL,
    NCBI_API_KEY, NCBI_EMAIL,
    MAX_PUBMED_RESULTS, REQUEST_TIMEOUT, MAX_RETRIES, RETRY_DELAY
)

logger = logging.getLogger(__name__)


def search_pubmed(query: str, max_results: int = MAX_PUBMED_RESULTS) -> list[str]:
    """
    Search PubMed and return a list of PMIDs.

    Args:
        query: Search query string (e.g. protein name or gene).
        max_results: Max number of PMIDs to retrieve.

    Returns:
        List of PMID strings.
    """
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "retmode": "json",
        "tool": "agentic-bioinformatics",
        "email": NCBI_EMAIL,
        "sort": "relevance",
    }
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                f"{PUBMED_BASE_URL}/esearch.fcgi",
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            pmids = data.get("esearchresult", {}).get("idlist", [])
            logger.info("PubMed search '%s' returned %d PMIDs", query, len(pmids))
            return pmids

        except Exception as exc:
            logger.warning("PubMed search failed (attempt %d/%d): %s", attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    return []


def fetch_pubmed_abstracts(pmids: list[str]) -> list[dict[str, Any]]:
    """
    Fetch title, abstract, authors, journal, year for a list of PMIDs.

    Args:
        pmids: List of PubMed IDs.

    Returns:
        List of paper dicts.
    """
    if not pmids:
        return []

    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "rettype": "abstract",
        "tool": "agentic-bioinformatics",
        "email": NCBI_EMAIL,
    }
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(
                f"{PUBMED_BASE_URL}/efetch.fcgi",
                params=params,
                timeout=REQUEST_TIMEOUT * 2,
            )
            resp.raise_for_status()
            return _parse_pubmed_xml(resp.text)

        except Exception as exc:
            logger.warning("PubMed fetch failed (attempt %d/%d): %s", attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    return []


def _parse_pubmed_xml(xml_text: str) -> list[dict[str, Any]]:
    """Parse PubMed XML efetch response into structured paper dicts."""
    papers = []
    try:
        root = ET.fromstring(xml_text)
        for article in root.findall(".//PubmedArticle"):
            paper: dict[str, Any] = {}

            # PMID
            pmid_el = article.find(".//PMID")
            paper["pmid"] = pmid_el.text if pmid_el is not None else ""

            # Title
            title_el = article.find(".//ArticleTitle")
            paper["title"] = (title_el.text or "").strip() if title_el is not None else ""

            # Abstract
            abstract_parts = article.findall(".//AbstractText")
            paper["abstract"] = " ".join(
                (el.text or "") for el in abstract_parts if el.text
            ).strip()

            # Authors
            authors = []
            for author in article.findall(".//Author"):
                last = author.find("LastName")
                fore = author.find("ForeName")
                if last is not None:
                    name = last.text or ""
                    if fore is not None:
                        name += f" {fore.text or ''}"
                    authors.append(name.strip())
            paper["authors"] = authors

            # Journal
            journal_el = article.find(".//Journal/Title")
            paper["journal"] = journal_el.text if journal_el is not None else ""

            # Year
            year_el = article.find(".//PubDate/Year")
            if year_el is not None and year_el.text:
                try:
                    paper["year"] = int(year_el.text)
                except ValueError:
                    paper["year"] = None
            else:
                paper["year"] = None

            paper["url"] = f"https://pubmed.ncbi.nlm.nih.gov/{paper['pmid']}/"
            papers.append(paper)

    except ET.ParseError as exc:
        logger.error("XML parsing error: %s", exc)

    logger.info("Parsed %d papers from PubMed XML", len(papers))
    return papers


def search_europepmc(query: str, max_results: int = 10) -> list[dict[str, Any]]:
    """
    Fallback literature search via Europe PMC REST API.

    Returns list of paper dicts (same format as PubMed).
    """
    url = f"{EUROPEPMC_BASE_URL}/search"
    params = {
        "query": query,
        "resultType": "core",
        "pageSize": max_results,
        "format": "json",
    }
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        results = resp.json().get("resultList", {}).get("result", [])

        papers = []
        for r in results:
            papers.append({
                "pmid": r.get("pmid", r.get("id", "")),
                "title": r.get("title", ""),
                "abstract": r.get("abstractText", ""),
                "authors": [a.get("fullName", "") for a in r.get("authorList", {}).get("author", [])],
                "journal": r.get("journalTitle", ""),
                "year": r.get("pubYear"),
                "url": r.get("fullTextUrlList", {}).get("fullTextUrl", [{}])[0].get("url", ""),
            })
        logger.info("Europe PMC returned %d results", len(papers))
        return papers

    except Exception as exc:
        logger.warning("Europe PMC search failed: %s", exc)
        return []
