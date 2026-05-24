"""
agents/uniprot_agent.py
------------------------
Fetches and structures all protein metadata from the UniProt REST API.
Returns a ProteinData schema object.
"""

import logging
from app.models.schemas import ProteinData, GOAnnotation
from app.tools.uniprot_tools import (
    fetch_uniprot_entry,
    parse_protein_name, parse_gene_name, parse_organism,
    parse_sequence, parse_function, parse_go_annotations,
    parse_diseases, parse_subcellular_locations, parse_cross_references,
)

logger = logging.getLogger(__name__)


class UniProtAgent:
    """Agent responsible for all UniProt data retrieval and parsing."""

    def run(self, uniprot_id: str) -> ProteinData:
        """
        Fetch and parse protein data for the given UniProt ID.

        Args:
            uniprot_id: e.g. "P04637"

        Returns:
            ProteinData instance (may be partially populated on API errors).
        """
        logger.info("[UniProtAgent] Starting for %s", uniprot_id)

        raw = fetch_uniprot_entry(uniprot_id)

        if not raw:
            logger.error("[UniProtAgent] No data returned for %s", uniprot_id)
            return ProteinData(uniprot_id=uniprot_id)

        # Parse individual fields
        protein_name = parse_protein_name(raw)
        gene_name = parse_gene_name(raw)
        organism = parse_organism(raw)
        sequence, seq_length = parse_sequence(raw)
        function_desc = parse_function(raw)
        go_raw = parse_go_annotations(raw)
        diseases = parse_diseases(raw)
        locations = parse_subcellular_locations(raw)
        xrefs = parse_cross_references(raw)

        # Convert GO dicts to schema objects
        go_annotations = [
            GOAnnotation(
                term_id=go["term_id"],
                term_name=go["term_name"],
                category=go["category"],
            )
            for go in go_raw
        ]

        result = ProteinData(
            uniprot_id=uniprot_id,
            protein_name=protein_name,
            gene_name=gene_name,
            organism=organism,
            sequence=sequence,
            sequence_length=seq_length,
            function_description=function_desc,
            go_annotations=go_annotations,
            subcellular_locations=locations,
            diseases=diseases,
            cross_references=xrefs,
        )

        logger.info(
            "[UniProtAgent] Done — %s (%s), %d GO terms, %d diseases",
            protein_name, gene_name, len(go_annotations), len(diseases)
        )
        return result
