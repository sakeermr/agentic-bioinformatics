"""
tools/hpa_tools.py
------------------
Retrieves tissue expression and localization data from the Human Protein Atlas.
Fixed: uses correct HPA API endpoints that are currently active.
"""

import logging
import time
import requests
from typing import Any, Optional

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 1.5


def get_hpa_summary(gene_name: str) -> dict[str, Any]:
    """
    Fetch expression data for a gene from Human Protein Atlas.
    Uses the search API to get reliable data.
    """
    empty = {
        "tissue_expressions": [],
        "cancer_expressions": [],
        "subcellular_locations": [],
    }

    # Try the HPA search/gene API endpoint
    data = _fetch_hpa_gene(gene_name)
    if not data:
        logger.warning("No HPA data for gene: %s", gene_name)
        return empty

    return {
        "tissue_expressions": _parse_tissue_expression(data),
        "cancer_expressions": _parse_cancer_expression(data),
        "subcellular_locations": _parse_subcellular(data),
    }


def _fetch_hpa_gene(gene_name: str) -> Optional[dict]:
    """
    Fetch gene data from HPA using their public API.
    Tries multiple endpoint formats.
    """
    # Method 1: HPA JSON API
    urls = [
        f"https://www.proteinatlas.org/{gene_name}.json",
        f"https://www.proteinatlas.org/search/{gene_name}?format=json",
    ]

    for url in urls:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info("Fetching HPA data: %s", url)
                resp = requests.get(
                    url,
                    timeout=REQUEST_TIMEOUT,
                    headers={"User-Agent": "BioinformaticsResearchBot/1.0"},
                )
                if resp.status_code == 404:
                    break
                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except Exception:
                        # Not JSON — try next URL
                        break
                resp.raise_for_status()
            except requests.exceptions.Timeout:
                logger.warning("HPA timeout (attempt %d)", attempt)
            except Exception as exc:
                logger.warning("HPA error: %s", exc)
                break
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    # Method 2: Use OpenTargets as alternative expression source
    return _fetch_opentargets_expression(gene_name)


def _fetch_opentargets_expression(gene_name: str) -> Optional[dict]:
    """
    Fetch expression data from OpenTargets Platform API.
    More reliable alternative to HPA direct API.
    """
    try:
        # First get the Ensembl gene ID
        url = f"https://rest.uniprot.org/uniprotkb/search?query=gene:{gene_name}+AND+organism_id:9606&fields=xref_ensembl&format=json"
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        results = resp.json().get("results", [])

        ensembl_id = None
        for r in results:
            for xref in r.get("uniProtKBCrossReferences", []):
                if xref.get("database") == "Ensembl":
                    ensembl_id = xref.get("id", "").split(".")[0]
                    break
            if ensembl_id:
                break

        if not ensembl_id:
            return None

        # Query GTEx/Expression Atlas via EBI
        expr_url = f"https://www.ebi.ac.uk/gxa/genes/{ensembl_id}/results?organism=Homo+sapiens&ds=%7B%22kingdom%22%3A%5B%22animals%22%5D%7D&_=1"
        expr_resp = requests.get(expr_url, timeout=REQUEST_TIMEOUT,
                                 headers={"Accept": "application/json"})
        if expr_resp.status_code == 200:
            return {"ebi_expression": expr_resp.json(), "ensembl_id": ensembl_id}

    except Exception as exc:
        logger.warning("OpenTargets/EBI expression fetch failed: %s", exc)

    return None


def _parse_tissue_expression(data: dict) -> list[dict[str, str]]:
    """Extract tissue expression from various API response formats."""
    expressions = []

    try:
        # Format 1: Direct HPA JSON
        if "tissueExpression" in data:
            for entry in data["tissueExpression"].get("data", []):
                tissue = entry.get("tissue", "")
                level = entry.get("level", "Unknown")
                if tissue:
                    expressions.append({"tissue": tissue, "level": level, "reliability": ""})

        # Format 2: HPA search result array
        elif isinstance(data, list) and data:
            item = data[0]
            for entry in item.get("tissue_expression", {}).get("data", []):
                tissue = entry.get("tissue", "")
                level = entry.get("level", "Unknown")
                if tissue:
                    expressions.append({"tissue": tissue, "level": level, "reliability": ""})

        # Format 3: EBI expression atlas format
        elif "ebi_expression" in data:
            ebi = data["ebi_expression"]
            for result in ebi.get("results", []):
                tissue = result.get("factorValues", [{}])[0].get("value", "")
                level_val = result.get("expressions", [{}])[0].get("value", 0)
                if tissue and level_val is not None:
                    level = _numeric_to_level(float(level_val) if level_val else 0)
                    expressions.append({"tissue": tissue, "level": level, "reliability": "EBI"})

    except Exception as exc:
        logger.warning("Tissue expression parse error: %s", exc)

    return expressions[:20]


def _parse_cancer_expression(data: dict) -> list[dict[str, str]]:
    """Extract cancer expression data."""
    cancers = []
    try:
        path_data = data.get("pathologyExpression", data.get("pathology_expression", {}))
        for entry in path_data.get("data", []):
            cancer = entry.get("cancerType", entry.get("cancer_type", entry.get("tissue", "")))
            level = entry.get("level", "Unknown")
            if cancer:
                cancers.append({"cancer_type": cancer, "level": level})
    except Exception as exc:
        logger.warning("Cancer expression parse error: %s", exc)
    return cancers


def _parse_subcellular(data: dict) -> list[str]:
    """Extract subcellular localization."""
    locations = []
    try:
        sc = data.get("subcellularLocation", data.get("subcellular_location", {}))
        for entry in sc.get("data", []):
            loc = entry.get("location", "")
            if loc:
                locations.append(loc)
    except Exception as exc:
        logger.warning("HPA subcellular parse error: %s", exc)
    return list(set(locations))


def _numeric_to_level(value: float) -> str:
    """Convert numeric TPM expression to categorical level."""
    if value > 100:
        return "High"
    elif value > 10:
        return "Medium"
    elif value > 1:
        return "Low"
    else:
        return "Not detected"