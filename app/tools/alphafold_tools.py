"""
tools/alphafold_tools.py
------------------------
Fetches predicted protein structure data from AlphaFold DB and RCSB PDB.
Fixed: RCSB uses correct v2 search API with proper query structure.
"""

import logging
import time
import requests
from typing import Any, Optional

from app.config.settings import (
    ALPHAFOLD_BASE_URL, REQUEST_TIMEOUT, MAX_RETRIES, RETRY_DELAY
)

logger = logging.getLogger(__name__)


def fetch_alphafold_entry(uniprot_id: str) -> Optional[dict[str, Any]]:
    """Check if AlphaFold has a predicted structure for this UniProt ID."""
    url = f"{ALPHAFOLD_BASE_URL}/prediction/{uniprot_id}"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 404:
                logger.info("No AlphaFold structure for %s", uniprot_id)
                return None
            resp.raise_for_status()
            entries = resp.json()
            if entries and isinstance(entries, list):
                logger.info("AlphaFold entry found for %s", uniprot_id)
                return entries[0]
            return None
        except requests.exceptions.Timeout:
            logger.warning("AlphaFold timeout (attempt %d/%d)", attempt, MAX_RETRIES)
        except requests.exceptions.RequestException as exc:
            logger.warning("AlphaFold request error: %s", exc)
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)

    return None


def get_alphafold_summary(uniprot_id: str) -> dict[str, Any]:
    """Return a summary dict with AlphaFold availability and model URLs."""
    entry = fetch_alphafold_entry(uniprot_id)

    if not entry:
        return {
            "available": False,
            "model_url": None,
            "viewer_url": None,
            "entry_id": None,
        }

    entry_id = entry.get("entryId", "")
    model_url = entry.get("cifUrl") or entry.get("pdbUrl") or entry.get("modelUrl")
    viewer_url = f"https://alphafold.ebi.ac.uk/entry/{uniprot_id}"

    return {
        "available": True,
        "model_url": model_url,
        "viewer_url": viewer_url,
        "entry_id": entry_id,
    }


def fetch_pdb_structures(uniprot_id: str) -> list[str]:
    """
    Query RCSB PDB for experimental structures associated with a UniProt ID.
    Fixed: uses correct RCSB Search API v2 JSON query format.
    """
    search_url = "https://search.rcsb.org/rcsbsearch/v2/query"

    query_payload = {
        "query": {
            "type": "terminal",
            "service": "text",
            "parameters": {
                "attribute": "rcsb_polymer_entity_container_identifiers.uniprot_ids",
                "operator": "exact_match",
                "value": uniprot_id,
            },
        },
        "return_type": "entry",
        "request_options": {
            "paginate": {"start": 0, "rows": 25},
            "sort": [{"sort_by": "score", "direction": "desc"}],
        },
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(
                search_url,
                json=query_payload,
                headers={"Content-Type": "application/json"},
                timeout=REQUEST_TIMEOUT,
            )

            # 204 = no results found (not an error)
            if resp.status_code == 204:
                logger.info("RCSB PDB: no structures found for %s", uniprot_id)
                return _fallback_pdb_search(uniprot_id)

            resp.raise_for_status()
            results = resp.json().get("result_set", [])
            pdb_ids = [r["identifier"] for r in results]
            logger.info("RCSB PDB: found %d structures for %s", len(pdb_ids), uniprot_id)
            return pdb_ids

        except Exception as exc:
            logger.warning("RCSB PDB search error (attempt %d): %s", attempt, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    return _fallback_pdb_search(uniprot_id)


def _fallback_pdb_search(uniprot_id: str) -> list[str]:
    """
    Fallback: query UniProt cross-references for PDB IDs directly.
    More reliable since UniProt already stores PDB cross-references.
    """
    try:
        url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.json"
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        pdb_ids = []
        for xref in data.get("uniProtKBCrossReferences", []):
            if xref.get("database") == "PDB":
                pdb_id = xref.get("id", "")
                if pdb_id:
                    pdb_ids.append(pdb_id)

        logger.info("Fallback PDB lookup: found %d IDs for %s", len(pdb_ids), uniprot_id)
        return pdb_ids

    except Exception as exc:
        logger.warning("Fallback PDB search failed: %s", exc)
        return []