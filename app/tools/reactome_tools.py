"""
tools/reactome_tools.py - Fixed Reactome API with correct endpoints.
"""
import logging, requests, time
from typing import Any
from app.config.settings import REQUEST_TIMEOUT, MAX_RETRIES, RETRY_DELAY

logger = logging.getLogger(__name__)

def get_top_pathways(uniprot_id: str, limit: int = 15) -> list[dict[str, Any]]:
    """Fetch biological pathways from Reactome for a UniProt ID."""
    
    # Method 1: Reactome ContentService mapping
    pathways = _fetch_reactome_mapping(uniprot_id)
    if pathways:
        return sorted(pathways, key=lambda x: x["pathway_name"])[:limit]
    
    # Method 2: Reactome analysis service
    pathways = _fetch_reactome_analysis(uniprot_id)
    if pathways:
        return pathways[:limit]
    
    logger.warning("All Reactome methods failed for %s", uniprot_id)
    return []


def _fetch_reactome_mapping(uniprot_id: str) -> list[dict]:
    """Use Reactome REST API mapping endpoint."""
    urls = [
        f"https://reactome.org/ContentService/data/mapping/UniProt/{uniprot_id}/pathways",
        f"https://reactome.org/ContentService/data/pathways/low/entity/{uniprot_id}/allForms",
    ]
    
    for url in urls:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.get(
                    url, timeout=REQUEST_TIMEOUT,
                    headers={"Accept": "application/json", "Content-Type": "application/json"}
                )
                if resp.status_code == 404:
                    break
                if resp.status_code == 200:
                    data = resp.json()
                    if not data:
                        break
                    pathways = []
                    for p in data:
                        if isinstance(p, dict):
                            st_id = p.get("stId", p.get("dbId", ""))
                            name = p.get("displayName", p.get("name", ""))
                            if name:
                                pathways.append({
                                    "pathway_id": str(st_id),
                                    "pathway_name": name,
                                    "species": p.get("speciesName", "Homo sapiens"),
                                    "url": f"https://reactome.org/PathwayBrowser/#/{st_id}",
                                })
                    if pathways:
                        logger.info("Reactome: found %d pathways via %s", len(pathways), url)
                        return pathways
            except Exception as exc:
                logger.warning("Reactome attempt %d failed: %s", attempt, exc)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
    return []


def _fetch_reactome_analysis(uniprot_id: str) -> list[dict]:
    """Use Reactome identifier lookup as fallback."""
    try:
        url = f"https://reactome.org/ContentService/data/query/{uniprot_id}"
        resp = requests.get(url, timeout=REQUEST_TIMEOUT,
                           headers={"Accept": "application/json"})
        if resp.status_code == 200:
            data = resp.json()
            pathways = []
            for item in data if isinstance(data, list) else [data]:
                if "pathway" in str(item.get("className", "")).lower():
                    pathways.append({
                        "pathway_id": item.get("stId", ""),
                        "pathway_name": item.get("displayName", ""),
                        "species": "Homo sapiens",
                        "url": f"https://reactome.org/PathwayBrowser/#/{item.get('stId','')}",
                    })
            return pathways
    except Exception as exc:
        logger.warning("Reactome analysis fallback failed: %s", exc)
    return []


def get_reactome_pathways(uniprot_id: str) -> list[dict[str, Any]]:
    return get_top_pathways(uniprot_id)