"""
tools/uniprot_tools.py
-----------------------
Functions for fetching protein data from the UniProt REST API.
"""

import logging
import time
import requests
from typing import Any, Optional

from app.config.settings import UNIPROT_BASE_URL, REQUEST_TIMEOUT, MAX_RETRIES, RETRY_DELAY

logger = logging.getLogger(__name__)


def fetch_uniprot_entry(uniprot_id: str) -> Optional[dict[str, Any]]:
    """
    Fetch full protein entry from UniProt REST API.

    Args:
        uniprot_id: e.g. "P04637"

    Returns:
        Parsed JSON dict or None on failure.
    """
    url = f"{UNIPROT_BASE_URL}/{uniprot_id}.json"

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("Fetching UniProt entry: %s (attempt %d)", uniprot_id, attempt)
            resp = requests.get(url, timeout=REQUEST_TIMEOUT)

            if resp.status_code == 404:
                logger.error("UniProt ID not found: %s", uniprot_id)
                return None

            resp.raise_for_status()
            return resp.json()

        except requests.exceptions.Timeout:
            logger.warning("UniProt request timed out (attempt %d/%d)", attempt, MAX_RETRIES)
        except requests.exceptions.RequestException as exc:
            logger.warning("UniProt request error: %s (attempt %d/%d)", exc, attempt, MAX_RETRIES)

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY * attempt)

    logger.error("All UniProt fetch attempts failed for %s", uniprot_id)
    return None


def parse_protein_name(data: dict) -> str:
    """Extract recommended protein name from UniProt JSON."""
    try:
        desc = data.get("proteinDescription", {})
        rec = desc.get("recommendedName", {})
        full_name = rec.get("fullName", {})
        return full_name.get("value", "Unknown protein")
    except Exception:
        return "Unknown protein"


def parse_gene_name(data: dict) -> str:
    """Extract primary gene name."""
    try:
        genes = data.get("genes", [])
        if genes:
            gene = genes[0]
            return gene.get("geneName", {}).get("value", "Unknown")
        return "Unknown"
    except Exception:
        return "Unknown"


def parse_organism(data: dict) -> str:
    """Extract organism scientific name."""
    try:
        return data.get("organism", {}).get("scientificName", "Unknown organism")
    except Exception:
        return "Unknown organism"


def parse_sequence(data: dict) -> tuple[str, int]:
    """Return (sequence_string, length)."""
    try:
        seq_data = data.get("sequence", {})
        seq = seq_data.get("value", "")
        length = seq_data.get("length", len(seq))
        return seq, length
    except Exception:
        return "", 0


def parse_function(data: dict) -> str:
    """Extract protein function description from UniProt comments."""
    try:
        for comment in data.get("comments", []):
            if comment.get("commentType") == "FUNCTION":
                texts = comment.get("texts", [])
                if texts:
                    return texts[0].get("value", "")
        return "No functional description available."
    except Exception:
        return "No functional description available."


def parse_go_annotations(data: dict) -> list[dict[str, str]]:
    """Extract Gene Ontology annotations."""
    annotations = []
    try:
        for xref in data.get("uniProtKBCrossReferences", []):
            if xref.get("database") == "GO":
                go_id = xref.get("id", "")
                props = {p["key"]: p["value"] for p in xref.get("properties", [])}
                term = props.get("GoTerm", "")
                aspect = props.get("GoEvidenceType", "")

                # Determine category from term prefix
                if term.startswith("F:"):
                    category = "molecular_function"
                    term_name = term[2:]
                elif term.startswith("P:"):
                    category = "biological_process"
                    term_name = term[2:]
                elif term.startswith("C:"):
                    category = "cellular_component"
                    term_name = term[2:]
                else:
                    category = "unknown"
                    term_name = term

                annotations.append({
                    "term_id": go_id,
                    "term_name": term_name,
                    "category": category,
                })
    except Exception as exc:
        logger.warning("GO annotation parsing error: %s", exc)

    return annotations


def parse_diseases(data: dict) -> list[str]:
    """Extract disease associations."""
    diseases = []
    try:
        for comment in data.get("comments", []):
            if comment.get("commentType") == "DISEASE":
                disease = comment.get("disease", {})
                name = disease.get("diseaseId", "")
                if name:
                    diseases.append(name)
    except Exception as exc:
        logger.warning("Disease parsing error: %s", exc)
    return diseases


def parse_subcellular_locations(data: dict) -> list[str]:
    """Extract subcellular localization information."""
    locations = []
    try:
        for comment in data.get("comments", []):
            if comment.get("commentType") == "SUBCELLULAR LOCATION":
                for loc_entry in comment.get("subcellularLocations", []):
                    loc = loc_entry.get("location", {}).get("value", "")
                    if loc:
                        locations.append(loc)
    except Exception as exc:
        logger.warning("Subcellular location parsing error: %s", exc)
    return list(set(locations))


def parse_cross_references(data: dict) -> dict[str, list[str]]:
    """Extract key cross-references (PDB, Ensembl, OMIM, etc.)."""
    refs: dict[str, list[str]] = {}
    databases_of_interest = {"PDB", "Ensembl", "OMIM", "RefSeq", "AlphaFoldDB", "HGNC"}
    try:
        for xref in data.get("uniProtKBCrossReferences", []):
            db = xref.get("database", "")
            if db in databases_of_interest:
                xref_id = xref.get("id", "")
                if xref_id:
                    refs.setdefault(db, []).append(xref_id)
    except Exception as exc:
        logger.warning("Cross-reference parsing error: %s", exc)
    return refs
