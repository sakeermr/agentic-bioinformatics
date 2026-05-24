"""
agents/expression_agent.py
---------------------------
Retrieves and summarizes protein expression data from the Human Protein Atlas.
"""

import logging
from app.models.schemas import ExpressionData, TissueExpression
from app.tools.hpa_tools import get_hpa_summary
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert molecular biologist summarizing protein expression data 
for a scientific report. Be concise, factual, and highlight medically relevant tissues."""


class ExpressionAgent:
    """Retrieves and interprets protein expression data."""

    def run(self, uniprot_id: str, gene_name: str) -> ExpressionData:
        """
        Fetch expression data and generate a biological summary.

        Args:
            uniprot_id: Used for result association.
            gene_name: Gene symbol for HPA lookup.

        Returns:
            ExpressionData instance.
        """
        logger.info("[ExpressionAgent] Starting for gene: %s", gene_name)

        hpa = get_hpa_summary(gene_name)

        # Convert tissue dicts to schema objects
        tissue_expressions = [
            TissueExpression(
                tissue=t["tissue"],
                level=t["level"],
                reliability=t.get("reliability"),
            )
            for t in hpa["tissue_expressions"]
        ]

        # Generate summary
        summary = self._generate_summary(gene_name, hpa)

        logger.info(
            "[ExpressionAgent] Done — %d tissues, %d cancer types",
            len(tissue_expressions), len(hpa["cancer_expressions"])
        )

        return ExpressionData(
            uniprot_id=uniprot_id,
            tissue_expressions=tissue_expressions,
            cancer_expressions=hpa["cancer_expressions"],
            subcellular_locations=hpa["subcellular_locations"],
            summary=summary,
        )

    @staticmethod
    def _generate_summary(gene_name: str, hpa: dict) -> str:
        """Use LLM to write a brief expression analysis."""
        tissues = hpa.get("tissue_expressions", [])
        cancers = hpa.get("cancer_expressions", [])
        locations = hpa.get("subcellular_locations", [])

        if not tissues and not cancers and not locations:
            return "Expression data not available from the Human Protein Atlas for this protein."

        # Build a compact data string
        high_tissues = [t["tissue"] for t in tissues if t.get("level") in ("High", "Medium")][:10]
        cancer_summary = [(c["cancer_type"], c["level"]) for c in cancers[:8]]
        loc_str = ", ".join(locations[:5]) if locations else "Unknown"

        user_prompt = f"""
Summarize the expression profile of gene **{gene_name}** based on this data:

**High/Medium expression tissues:** {', '.join(high_tissues) or 'Data not available'}
**Subcellular localization:** {loc_str}
**Cancer expression summary:** {cancer_summary or 'Data not available'}

Write 2–3 sentences describing the expression pattern and its biological or clinical significance.
"""
        try:
            return llm_service.complete(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.2,
                max_tokens=300,
            )
        except Exception as exc:
            logger.error("[ExpressionAgent] LLM failed: %s", exc)
            return f"High expression tissues: {', '.join(high_tissues)}. Location: {loc_str}."
