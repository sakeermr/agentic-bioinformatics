"""
tools/string_tools.py
----------------------
Fetches protein-protein interaction data from STRING DB.
STRING provides a scored network of known and predicted protein interactions.
"""

import logging
import requests
from typing import Any
from app.config.settings import REQUEST_TIMEOUT, MAX_RETRIES, RETRY_DELAY
import time

logger = logging.getLogger(__name__)
STRING_BASE = "https://string-db.org/api"


def get_string_interactions(protein_name: str, species: int = 9606, limit: int = 20) -> list[dict[str, Any]]:
    """
    Fetch top protein-protein interactions from STRING DB.
    Args:
        protein_name: Gene symbol e.g. TP53
        species: NCBI taxon ID (9606 = Homo sapiens)
        limit: Max interactions to return
    Returns:
        List of interaction dicts with partner name and score.
    """
    # Step 1: Get STRING ID for the protein
    map_url = f"{STRING_BASE}/json/get_string_ids"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(map_url, data={
                "identifiers": protein_name,
                "species": species,
                "limit": 1,
                "caller_identity": "agentic_bioinformatics"
            }, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            mapped = resp.json()
            if not mapped:
                logger.warning("STRING: no ID found for %s", protein_name)
                return []
            string_id = mapped[0].get("stringId", "")
            break
        except Exception as exc:
            logger.warning("STRING ID mapping error (attempt %d): %s", attempt, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                return []

    # Step 2: Get interactions
    interact_url = f"{STRING_BASE}/json/interaction_partners"
    try:
        resp = requests.post(interact_url, data={
            "identifiers": string_id,
            "species": species,
            "limit": limit,
            "required_score": 400,
            "caller_identity": "agentic_bioinformatics"
        }, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        interactions = resp.json()

        results = []
        for item in interactions:
            results.append({
                "partner": item.get("preferredName_B", item.get("stringId_B", "")),
                "score": round(item.get("score", 0), 3),
                "experimental_score": round(item.get("escore", 0), 3),
                "database_score": round(item.get("dscore", 0), 3),
            })
        logger.info("STRING: found %d interactions for %s", len(results), protein_name)
        return results
    except Exception as exc:
        logger.warning("STRING interaction fetch failed: %s", exc)
        return []
