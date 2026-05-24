"""
agents/mutation_agent.py
-------------------------
Retrieves pathogenic variants from ClinVar and summarizes mutation landscape.
"""

import logging
from app.models.schemas import MutationData, Variant
from app.tools.clinvar_tools import get_variants_for_gene
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a clinical geneticist summarizing mutation data for a scientific report.
Focus on pathogenic variants, hotspot residues, and disease associations. Be concise and factual."""


class MutationAgent:
    """Retrieves and interprets variant/mutation data from ClinVar."""

    def run(self, uniprot_id: str, gene_name: str) -> MutationData:
        """
        Fetch variants and generate a mutation analysis summary.

        Args:
            uniprot_id: For result association.
            gene_name: Gene symbol used to query ClinVar.

        Returns:
            MutationData instance.
        """
        logger.info("[MutationAgent] Starting for gene: %s", gene_name)

        clinvar_result = get_variants_for_gene(gene_name)
        raw_variants = clinvar_result.get("variants", [])
        pathogenic_count = clinvar_result.get("pathogenic_count", 0)
        total_in_db = clinvar_result.get("total_in_database", 0)
        # Use the larger of the two counts
        if total_in_db > pathogenic_count:
            pathogenic_count = total_in_db

        # Convert to schema objects
        variants = [
            Variant(
                variant_id=v.get("variant_id", ""),
                gene=v.get("gene", gene_name),
                change=v.get("change", ""),
                clinical_significance=v.get("clinical_significance", ""),
                condition=v.get("condition", ""),
                review_status=v.get("review_status", ""),
            )
            for v in raw_variants
        ]

        summary = self._generate_summary(gene_name, variants, pathogenic_count)

        logger.info(
            "[MutationAgent] Done — %d variants, %d pathogenic",
            len(variants), pathogenic_count
        )

        return MutationData(
            uniprot_id=uniprot_id,
            gene_name=gene_name,
            variants=variants,
            pathogenic_count=pathogenic_count,
            summary=summary,
        )

    @staticmethod
    def _generate_summary(gene_name: str, variants: list[Variant], pathogenic_count: int) -> str:
        """LLM-generated mutation summary."""
        if not variants:
            return f"No ClinVar variants found for {gene_name}."

        # Summarize top pathogenic variants
        pathogenic = [
            v for v in variants
            if "pathogenic" in (v.clinical_significance or "").lower()
        ][:10]

        variant_list = "\n".join(
            f"- {v.change or v.variant_id}: {v.clinical_significance} → {v.condition}"
            for v in pathogenic
        )

        conditions = list(set(v.condition for v in pathogenic if v.condition and v.condition != "Unknown"))[:6]

        user_prompt = f"""
Summarize the mutation landscape for gene **{gene_name}** based on ClinVar data:

**Total pathogenic/likely-pathogenic variants:** {pathogenic_count}
**Associated conditions:** {', '.join(conditions) or 'Various'}

**Key pathogenic variants:**
{variant_list or 'See ClinVar database for full list.'}

Write 2–4 sentences describing the mutation landscape, hotspot regions if apparent, 
and disease significance. Use clinical genetics terminology.
"""
        try:
            return llm_service.complete(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.2,
                max_tokens=400,
            )
        except Exception as exc:
            logger.error("[MutationAgent] LLM failed: %s", exc)
            return (
                f"{gene_name} has {pathogenic_count} pathogenic/likely-pathogenic variants in ClinVar. "
                f"Associated conditions include: {', '.join(conditions)}."
            )