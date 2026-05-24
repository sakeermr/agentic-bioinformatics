"""
agents/orchestrator.py
-----------------------
Central orchestrator that manages the multi-agent workflow using concurrent
execution. Uses asyncio to run all data-collection agents in parallel,
then passes results to the ReportAgent.
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from app.models.schemas import ResearchResult
from app.agents.uniprot_agent import UniProtAgent
from app.agents.literature_agent import LiteratureAgent
from app.agents.expression_agent import ExpressionAgent
from app.agents.mutation_agent import MutationAgent
from app.agents.structure_agent import StructureAgent
from app.agents.report_agent import ReportAgent
from app.agents.enrichment_agent import EnrichmentAgent

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Coordinates all research agents in a parallel pipeline.

    Workflow:
        1. UniProt Agent runs first (other agents need gene name from it)
        2. Literature, Expression, Mutation, Structure agents run in parallel
        3. Report Agent synthesizes everything
    """

    def __init__(self):
        self.uniprot_agent = UniProtAgent()
        self.literature_agent = LiteratureAgent()
        self.expression_agent = ExpressionAgent()
        self.mutation_agent = MutationAgent()
        self.structure_agent = StructureAgent()
        self.report_agent = ReportAgent()
        self.enrichment_agent = EnrichmentAgent()

    def run(self, uniprot_id: str) -> ResearchResult:
        """
        Execute the full research pipeline for a UniProt ID.

        Args:
            uniprot_id: e.g. "P04637"

        Returns:
            Completed ResearchResult with all data and report paths.
        """
        start_time = time.time()
        uniprot_id = uniprot_id.strip().upper()

        logger.info("=" * 60)
        logger.info("Orchestrator starting pipeline for: %s", uniprot_id)

        result = ResearchResult(uniprot_id=uniprot_id)

        # ── Step 1: UniProt (must run first — others need gene name) ──
        logger.info("[Step 1/3] Running UniProt Agent")
        try:
            result.protein = self.uniprot_agent.run(uniprot_id)
            gene_name = result.protein.gene_name or "Unknown"
            protein_name = result.protein.protein_name or uniprot_id
            logger.info("UniProt complete: %s (%s)", protein_name, gene_name)
        except Exception as exc:
            logger.error("UniProt Agent failed: %s", exc)
            result.errors["uniprot"] = str(exc)
            gene_name = "Unknown"
            protein_name = uniprot_id

        # ── Step 2: Parallel data collection ──────────────────────────
        logger.info("[Step 2/3] Running parallel agents (Literature, Expression, Mutation, Structure)")

        def run_literature():
            try:
                return "literature", self.literature_agent.run(uniprot_id, protein_name, gene_name)
            except Exception as exc:
                logger.error("Literature Agent failed: %s", exc)
                return "literature_error", str(exc)

        def run_expression():
            try:
                return "expression", self.expression_agent.run(uniprot_id, gene_name)
            except Exception as exc:
                logger.error("Expression Agent failed: %s", exc)
                return "expression_error", str(exc)

        def run_mutation():
            try:
                return "mutations", self.mutation_agent.run(uniprot_id, gene_name)
            except Exception as exc:
                logger.error("Mutation Agent failed: %s", exc)
                return "mutations_error", str(exc)

        def run_structure():
            try:
                return "structure", self.structure_agent.run(uniprot_id, protein_name)
            except Exception as exc:
                logger.error("Structure Agent failed: %s", exc)
                return "structure_error", str(exc)

        # Run all 4 agents concurrently using thread pool
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(run_literature),
                executor.submit(run_expression),
                executor.submit(run_mutation),
                executor.submit(run_structure),
            ]

            for future in as_completed(futures):
                try:
                    key, value = future.result()
                    if key == "literature":
                        result.literature = value
                        logger.info("✓ Literature Agent complete")
                    elif key == "expression":
                        result.expression = value
                        logger.info("✓ Expression Agent complete")
                    elif key == "mutations":
                        result.mutations = value
                        logger.info("✓ Mutation Agent complete")
                    elif key == "structure":
                        result.structure = value
                        logger.info("✓ Structure Agent complete")
                    elif key.endswith("_error"):
                        agent_name = key.replace("_error", "")
                        result.errors[agent_name] = value
                        logger.warning("✗ %s Agent failed: %s", agent_name, value)
                except Exception as exc:
                    logger.error("Unexpected error in parallel agent: %s", exc)

        # ── Step 2b: Enrichment databases ─────────────────────────────
        logger.info("[Step 2b/3] Running Enrichment Agent (STRING, Reactome, GTEx, OpenTargets)")
        try:
            enrichment = self.enrichment_agent.run(uniprot_id, gene_name)
            result.string_data = enrichment.get("string")
            result.reactome_data = enrichment.get("reactome")
            result.gtex_data = enrichment.get("gtex")
            result.opentargets_data = enrichment.get("opentargets")
            logger.info("✓ Enrichment Agent complete")
        except Exception as exc:
            logger.error("Enrichment Agent failed: %s", exc)
            result.errors["enrichment"] = str(exc)

        # ── Step 3: Report generation ──────────────────────────────────
        logger.info("[Step 3/3] Running Report Agent")
        try:
            result = self.report_agent.run(result)
        except Exception as exc:
            logger.error("Report Agent failed: %s", exc)
            result.errors["report"] = str(exc)

        elapsed = time.time() - start_time
        logger.info("Pipeline complete in %.1f seconds", elapsed)
        logger.info("=" * 60)

        return result

    @staticmethod
    def validate_uniprot_id(uniprot_id: str) -> bool:
        """
        Basic format validation for UniProt accession IDs.
        UniProt IDs are 6 or 10 alphanumeric characters.
        """
        import re
        pattern = r"^[A-Z][0-9][A-Z0-9]{3}[0-9]([A-Z][0-9][A-Z0-9]{3}[0-9])?$"
        return bool(re.match(pattern, uniprot_id.strip().upper()))
