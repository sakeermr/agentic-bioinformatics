"""
agents/structure_agent.py
--------------------------
Retrieves structural information from AlphaFold DB and RCSB PDB.
"""

import logging
from app.models.schemas import StructureData
from app.tools.alphafold_tools import get_alphafold_summary, fetch_pdb_structures
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a structural biologist writing a protein structure section 
for a scientific report. Describe structural coverage and its significance concisely."""


class StructureAgent:
    """Retrieves protein structure availability from AlphaFold and PDB."""

    def run(self, uniprot_id: str, protein_name: str) -> StructureData:
        """
        Fetch structure data and generate a summary.

        Args:
            uniprot_id: UniProt accession.
            protein_name: For LLM context.

        Returns:
            StructureData instance.
        """
        logger.info("[StructureAgent] Starting for %s", uniprot_id)

        # ── AlphaFold ─────────────────────────────────────────
        af = get_alphafold_summary(uniprot_id)

        # ── PDB ───────────────────────────────────────────────
        pdb_ids = fetch_pdb_structures(uniprot_id)

        summary = self._generate_summary(protein_name, af, pdb_ids)

        logger.info(
            "[StructureAgent] Done — AlphaFold: %s, PDB entries: %d",
            af["available"], len(pdb_ids)
        )

        return StructureData(
            uniprot_id=uniprot_id,
            alphafold_available=af["available"],
            alphafold_url=af.get("viewer_url"),
            alphafold_model_url=af.get("model_url"),
            pdb_ids=pdb_ids,
            pdb_count=len(pdb_ids),
            summary=summary,
        )

    @staticmethod
    def _generate_summary(protein_name: str, af: dict, pdb_ids: list[str]) -> str:
        """LLM-generated structural summary."""
        af_status = "available" if af["available"] else "not available"
        pdb_count = len(pdb_ids)
        pdb_preview = ", ".join(pdb_ids[:5]) if pdb_ids else "None"

        user_prompt = f"""
Write a brief structural summary for **{protein_name}**:

- **AlphaFold predicted structure:** {af_status}
  {f"- AlphaFold URL: {af.get('viewer_url')}" if af['available'] else ""}
- **Experimental PDB structures:** {pdb_count} entries
- **PDB IDs (sample):** {pdb_preview}

Write 2–3 sentences about the structural data availability and its research significance.
"""
        try:
            return llm_service.complete(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.2,
                max_tokens=250,
            )
        except Exception as exc:
            logger.error("[StructureAgent] LLM failed: %s", exc)
            parts = []
            if af["available"]:
                parts.append(f"AlphaFold predicted structure is available at {af.get('viewer_url')}.")
            parts.append(f"{pdb_count} experimental PDB structure(s) are deposited.")
            return " ".join(parts)
