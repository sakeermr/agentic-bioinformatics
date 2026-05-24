"""
agents/enrichment_agent.py
---------------------------
Runs all new database enrichments in parallel:
STRING (interactions), Reactome (pathways), GTEx (expression), Open Targets (drugs).
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.tools.string_tools import get_string_interactions
from app.tools.reactome_tools import get_top_pathways
from app.tools.gtex_tools import get_gtex_expression
from app.tools.opentargets_tools import get_opentargets_data
from app.models.schemas import (
    StringData, StringInteraction, ReactomeData, ReactomePathway,
    GTExData, GTExTissue, OpenTargetsData, DrugRecord
)

logger = logging.getLogger(__name__)


class EnrichmentAgent:
    """Fetches enrichment data from STRING, Reactome, GTEx, Open Targets in parallel."""

    def run(self, uniprot_id: str, gene_name: str) -> dict:
        logger.info("[EnrichmentAgent] Starting enrichment for %s (%s)", gene_name, uniprot_id)

        results = {"string": None, "reactome": None, "gtex": None, "opentargets": None}

        def run_string():
            try:
                interactions = get_string_interactions(gene_name)
                top_partners = [i["partner"] for i in interactions[:10]]
                return "string", StringData(
                    gene_name=gene_name,
                    interactions=[StringInteraction(**i) for i in interactions],
                    top_partners=top_partners,
                )
            except Exception as exc:
                logger.error("STRING failed: %s", exc)
                return "string", StringData(gene_name=gene_name)

        def run_reactome():
            try:
                pathways = get_top_pathways(uniprot_id)
                return "reactome", ReactomeData(
                    uniprot_id=uniprot_id,
                    pathways=[ReactomePathway(**p) for p in pathways],
                    pathway_count=len(pathways),
                )
            except Exception as exc:
                logger.error("Reactome failed: %s", exc)
                return "reactome", ReactomeData(uniprot_id=uniprot_id)

        def run_gtex():
            try:
                tissues = get_gtex_expression(gene_name)
                top = [t["tissue"] for t in tissues[:5] if t["level"] in ("High", "Medium")]
                return "gtex", GTExData(
                    gene_name=gene_name,
                    tissues=[GTExTissue(**t) for t in tissues[:30]],
                    top_expressed=top,
                )
            except Exception as exc:
                logger.error("GTEx failed: %s", exc)
                return "gtex", GTExData(gene_name=gene_name)

        def run_opentargets():
            try:
                ot = get_opentargets_data(gene_name, uniprot_id)
                drugs = [DrugRecord(**d) for d in ot.get("drugs", [])]
                return "opentargets", OpenTargetsData(
                    target_id=ot.get("target_id"),
                    drugs=drugs,
                    disease_associations=ot.get("diseases", []),
                    drug_count=len(drugs),
                )
            except Exception as exc:
                logger.error("OpenTargets failed: %s", exc)
                return "opentargets", OpenTargetsData()

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(run_string),
                executor.submit(run_reactome),
                executor.submit(run_gtex),
                executor.submit(run_opentargets),
            ]
            for future in as_completed(futures):
                key, value = future.result()
                results[key] = value
                logger.info("✓ %s enrichment complete", key)

        logger.info("[EnrichmentAgent] All enrichments complete")
        return results
