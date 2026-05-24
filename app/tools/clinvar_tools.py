"""
tools/clinvar_tools.py
Fixed: Uses simpler query format + fetches total count correctly.
"""
import logging, time, requests
from typing import Any
from app.config.settings import CLINVAR_BASE_URL, NCBI_API_KEY, NCBI_EMAIL, REQUEST_TIMEOUT, MAX_RETRIES, RETRY_DELAY

logger = logging.getLogger(__name__)

def get_variants_for_gene(gene_name: str) -> dict[str, Any]:
    """Get pathogenic variants and total count for a gene from ClinVar."""

    # Step 1: Get total count with pathogenic filter
    total_count = _get_total_count(gene_name)

    # Step 2: Fetch sample variants for display
    ids = _search_ids(gene_name, max_results=20)
    variants = _fetch_details(ids) if ids else []

    pathogenic_count = sum(
        1 for v in variants
        if any(t in v.get("clinical_significance", "").lower()
               for t in ["pathogenic", "likely pathogenic"])
    )

    # Use total_count from search (more accurate than parsed count)
    final_count = max(pathogenic_count, total_count)

    logger.info("ClinVar: %s — %d total pathogenic, %d fetched", gene_name, final_count, len(variants))
    return {
        "variants": variants,
        "pathogenic_count": final_count,
        "total_in_database": total_count,
    }


def _get_total_count(gene_name: str) -> int:
    """Get total pathogenic variant count from ClinVar search."""
    # Try multiple query formats
    queries = [
        f"{gene_name}[gene] AND clinsig_pathogenic[Filter]",
        f"{gene_name}[GENE] AND (pathogenic[CLINSIG] OR likely_pathogenic[CLINSIG])",
        f'"{gene_name}"[gene] AND pathogenic[clinical_significance]',
    ]

    for query in queries:
        params = {
            "db": "clinvar",
            "term": query,
            "retmax": 0,  # Only get count, no IDs
            "retmode": "json",
            "tool": "agentic-bioinformatics",
            "email": NCBI_EMAIL,
        }
        if NCBI_API_KEY:
            params["api_key"] = NCBI_API_KEY

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.get(
                    f"{CLINVAR_BASE_URL}/esearch.fcgi",
                    params=params,
                    timeout=REQUEST_TIMEOUT
                )
                resp.raise_for_status()
                result = resp.json().get("esearchresult", {})
                count = int(result.get("count", 0))
                if count > 0:
                    logger.info("ClinVar count for '%s': %d (query: %s)", gene_name, count, query[:50])
                    return count
                break  # Count is 0, try next query
            except Exception as exc:
                logger.warning("ClinVar count error (attempt %d): %s", attempt, exc)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)

    return 0


def _search_ids(gene_name: str, max_results: int = 20) -> list[str]:
    """Search ClinVar for variant IDs."""
    params = {
        "db": "clinvar",
        "term": f"{gene_name}[gene]",
        "retmax": max_results,
        "retmode": "json",
        "tool": "agentic-bioinformatics",
        "email": NCBI_EMAIL,
        "sort": "clinical_significance",
    }
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(f"{CLINVAR_BASE_URL}/esearch.fcgi",
                               params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json().get("esearchresult", {}).get("idlist", [])
        except Exception as exc:
            logger.warning("ClinVar search error (attempt %d): %s", attempt, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    return []


def _fetch_details(variant_ids: list[str]) -> list[dict[str, Any]]:
    """Fetch variant details using esummary."""
    if not variant_ids:
        return []

    params = {
        "db": "clinvar",
        "id": ",".join(variant_ids[:20]),
        "retmode": "json",
        "tool": "agentic-bioinformatics",
        "email": NCBI_EMAIL,
    }
    if NCBI_API_KEY:
        params["api_key"] = NCBI_API_KEY

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(f"{CLINVAR_BASE_URL}/esummary.fcgi",
                               params=params, timeout=REQUEST_TIMEOUT * 2)
            resp.raise_for_status()
            return _parse(resp.json())
        except Exception as exc:
            logger.warning("ClinVar fetch error (attempt %d): %s", attempt, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
    return []


def _parse(data: dict) -> list[dict[str, Any]]:
    """Parse ClinVar esummary response."""
    variants = []
    try:
        result = data.get("result", {})
        for uid in result.get("uids", []):
            entry = result.get(uid, {})
            if not entry:
                continue
            clinsig = entry.get("clinical_significance", {})
            significance = (clinsig.get("description", "Unknown")
                           if isinstance(clinsig, dict) else str(clinsig))
            trait_set = entry.get("trait_set", [])
            condition = trait_set[0].get("trait_name", "Unknown") if trait_set else "Unknown"
            genes = entry.get("genes", [])
            variants.append({
                "variant_id": uid,
                "change": entry.get("title", uid),
                "clinical_significance": significance,
                "condition": condition,
                "gene": genes[0].get("symbol", "") if genes else "",
                "review_status": entry.get("review_status", ""),
            })
    except Exception as exc:
        logger.error("ClinVar parse error: %s", exc)
    return variants