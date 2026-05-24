"""
agents/report_agent.py
-----------------------
Generates the final report with badge-style classification in overview,
plus STRING, Reactome, GTEx, and Open Targets sections.
"""

import logging, re
from datetime import datetime
from app.models.schemas import ResearchResult
from app.services.llm_service import llm_service
from app.services.pdf_service import pdf_service
from app.services.citation_service import CitationService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior biomedical researcher and chief scientist. 
Write authoritative, evidence-based, publication-quality scientific content."""

CLASSIFICATION_PROMPT = """You are a chief scientist and expert protein biologist 
with 30 years of experience. Classify proteins definitively for drug discovery and disease research.
Be precise and clinically actionable."""


class ReportAgent:

    def run(self, result: ResearchResult) -> ResearchResult:
        logger.info("[ReportAgent] Generating report for %s", result.uniprot_id)

        citation_svc = CitationService()
        if result.literature and result.literature.papers:
            citation_svc.add_papers(result.literature.papers)

        classification_text = self._generate_protein_classification(result)
        badges = self._extract_badges(classification_text)
        insights = self._generate_insights(result)
        conclusion = self._generate_conclusion(result, classification_text)

        markdown = self._build_markdown(result, classification_text, badges, insights, conclusion, citation_svc)
        result.markdown_report = markdown

        try:
            pdf_path = pdf_service.generate(markdown, result.uniprot_id)
            result.pdf_path = pdf_path
        except Exception as exc:
            logger.error("[ReportAgent] PDF failed: %s", exc)
            result.errors["pdf"] = str(exc)

        return result

    def _extract_badges(self, classification_text: str) -> dict:
        """Parse classification text to extract badge values."""
        badges = {
            "primary_class": "Unknown",
            "expression_class": "Unknown",
            "structural_class": "Unknown",
            "mutation_mechanism": "Unknown",
            "therapeutic_tier": "Unknown",
        }
        lines = classification_text.split("\n")
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if "primary protein class" in line_lower and i + 1 < len(lines):
                next_lines = " ".join(lines[i+1:i+4])
                for cls in ["Tumor Suppressor", "Oncogene", "Transcription Factor",
                            "Kinase", "Receptor", "Enzyme", "Scaffold", "Ion Channel",
                            "Nuclear Receptor", "Signaling Adaptor", "Structural Protein"]:
                    if cls.lower() in next_lines.lower():
                        badges["primary_class"] = cls
                        break
            if "expression classification" in line_lower and i + 1 < len(lines):
                next_lines = " ".join(lines[i+1:i+4])
                for cls in ["Overexpressed", "Underexpressed", "Tissue-Restricted",
                            "Ubiquitously Expressed", "Stress-Induced"]:
                    if cls.lower() in next_lines.lower():
                        badges["expression_class"] = cls
                        break
            if "structural classification" in line_lower and i + 1 < len(lines):
                next_lines = " ".join(lines[i+1:i+4])
                for cls in ["Conformational Change Driver", "Intrinsically Disordered",
                            "Stable Globular", "Multi-domain Allosteric",
                            "Amyloidogenic", "Membrane-Associated"]:
                    if cls.lower() in next_lines.lower():
                        badges["structural_class"] = cls
                        break
            if "mutation mechanism" in line_lower and i + 1 < len(lines):
                next_lines = " ".join(lines[i+1:i+4])
                for cls in ["Loss-of-Function", "Gain-of-Function",
                            "Dominant Negative", "Haploinsufficiency", "Structural Destabilization"]:
                    if cls.lower() in next_lines.lower():
                        badges["mutation_mechanism"] = cls
                        break
            if "therapeutic target" in line_lower and i + 1 < len(lines):
                next_lines = " ".join(lines[i+1:i+4])
                for tier in ["Tier 1", "Tier 2", "Tier 3", "Tier 4", "Tier 5"]:
                    if tier.lower() in next_lines.lower():
                        badges["therapeutic_tier"] = tier
                        break
        return badges

    def _generate_protein_classification(self, result: ResearchResult) -> str:
        p = result.protein
        mut = result.mutations
        expr = result.expression
        struct = result.structure
        lit = result.literature
        ot = result.opentargets_data

        protein_name = p.protein_name if p else result.uniprot_id
        gene_name = p.gene_name if p else "Unknown"
        diseases = ", ".join(p.diseases[:6]) if p and p.diseases else "None"
        function_desc = (p.function_description[:400] if p and p.function_description else "Unknown")
        go_terms = ", ".join([go.term_name for go in p.go_annotations[:8]]) if p else ""
        locations = ", ".join(p.subcellular_locations[:5]) if p and p.subcellular_locations else "Unknown"
        pathogenic_count = mut.pathogenic_count if mut else 0
        pdb_count = struct.pdb_count if struct else 0
        af_available = struct.alphafold_available if struct else False
        drug_count = ot.drug_count if ot else 0
        drug_names = ", ".join([d.name for d in ot.drugs[:5]]) if ot and ot.drugs else "None found"
        lit_summary = (lit.literature_review[:300] if lit and lit.literature_review else "N/A")

        user_prompt = f"""
As Chief Scientist, classify this protein definitively:

Protein: {protein_name} | Gene: {gene_name} | UniProt: {result.uniprot_id}
Function: {function_desc}
GO Terms: {go_terms}
Location: {locations}
Diseases: {diseases}
Pathogenic Variants: {pathogenic_count}
PDB Structures: {pdb_count} | AlphaFold: {"Yes" if af_available else "No"}
Known Drugs: {drug_count} ({drug_names})
Literature: {lit_summary}

Provide classification with these EXACT section headers:

## PRIMARY PROTEIN CLASS
[Single classification + explanation]

## EXPRESSION CLASSIFICATION  
[Pick one: Overexpressed/Underexpressed/Tissue-Restricted/Ubiquitously Expressed/Stress-Induced + evidence]

## STRUCTURAL CLASSIFICATION
[Pick one: Conformational Change Driver/Intrinsically Disordered/Stable Globular/Multi-domain Allosteric/Amyloidogenic/Membrane-Associated + evidence]

## MUTATION MECHANISM CLASS
[Pick one: Loss-of-Function/Gain-of-Function/Dominant Negative/Haploinsufficiency/Structural Destabilization + mechanism]

## THERAPEUTIC TARGET CLASSIFICATION
[Pick tier: Tier 1 Established/Tier 2 Active Clinical/Tier 3 Emerging/Tier 4 Challenging/Tier 5 Undruggable + strategy]

## CHIEF SCIENTIST VERDICT
[3-4 definitive sentences: what this protein IS, its primary disease mechanism, most promising therapeutic direction, key knowledge gap. No hedging.]
"""
        try:
            return llm_service.complete(CLASSIFICATION_PROMPT, user_prompt, temperature=0.2, max_tokens=1500)
        except Exception as exc:
            logger.error("Classification failed: %s", exc)
            return "Classification could not be generated."

    def _generate_insights(self, result: ResearchResult) -> str:
        p = result.protein
        protein_name = p.protein_name if p else result.uniprot_id
        gene_name = p.gene_name if p else "Unknown"
        ot = result.opentargets_data
        string_d = result.string_data
        reactome_d = result.reactome_data

        drug_info = f"{ot.drug_count} drugs including {', '.join([d.name for d in ot.drugs[:3]])}" if ot and ot.drugs else "No drug data"
        partners = ", ".join(string_d.top_partners[:8]) if string_d and string_d.top_partners else "N/A"
        pathways = ", ".join([p.pathway_name for p in reactome_d.pathways[:5]]) if reactome_d and reactome_d.pathways else "N/A"

        user_prompt = f"""
Write Research Insights for {protein_name} ({gene_name}):

Diseases: {', '.join(p.diseases[:5]) if p and p.diseases else 'Unknown'}
Variants: {result.mutations.pathogenic_count if result.mutations else 0} pathogenic
Protein interactions: {partners}
Key pathways: {pathways}
Drug landscape: {drug_info}
Expression: {result.expression.summary[:200] if result.expression and result.expression.summary else 'N/A'}

Write 2-3 paragraphs connecting all data sources to biological mechanisms,
clinical relevance, and future research directions.
"""
        try:
            return llm_service.complete(SYSTEM_PROMPT, user_prompt, temperature=0.4, max_tokens=600)
        except Exception as exc:
            return "Research insights could not be generated."

    def _generate_conclusion(self, result: ResearchResult, classification: str) -> str:
        p = result.protein
        protein_name = p.protein_name if p else result.uniprot_id
        gene_name = p.gene_name if p else "Unknown"
        verdict = classification.split("CHIEF SCIENTIST VERDICT")[-1][:300] if "CHIEF SCIENTIST VERDICT" in classification else ""

        user_prompt = f"""Write a 4-6 sentence Conclusion for {protein_name} ({gene_name}, {result.uniprot_id}).
Chief Scientist Verdict: {verdict}
Cover: biological roles, disease relevance, therapeutic potential, future directions."""
        try:
            return llm_service.complete(SYSTEM_PROMPT, user_prompt, temperature=0.3, max_tokens=300)
        except Exception as exc:
            return "Conclusion could not be generated."

    @staticmethod
    def _build_badge_row(badges: dict) -> str:
        """Build visual badge summary line."""
        badge_map = {
            "primary_class": {"icon": "🔴", "label": "Class"},
            "expression_class": {"icon": "📊", "label": "Expression"},
            "structural_class": {"icon": "🏗️", "label": "Structure"},
            "mutation_mechanism": {"icon": "⚡", "label": "Mutation"},
            "therapeutic_tier": {"icon": "💊", "label": "Drug Target"},
        }
        parts = []
        for key, meta in badge_map.items():
            val = badges.get(key, "Unknown")
            if val and val != "Unknown":
                parts.append(f"{meta['icon']} **{val}**")
        return " | ".join(parts)

    @staticmethod
    def _build_markdown(result, classification_text, badges, insights, conclusion, citation_svc):
        p = result.protein
        lit = result.literature
        expr = result.expression
        mut = result.mutations
        struct = result.structure
        string_d = result.string_data
        reactome_d = result.reactome_data
        gtex_d = result.gtex_data
        ot = result.opentargets_data

        protein_name = p.protein_name if p else result.uniprot_id
        gene_name = p.gene_name if p else "Unknown"
        organism = p.organism if p else "Unknown"
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        badge_line = ReportAgent._build_badge_row(badges)

        sections = [
            f"# Protein Research Report: {protein_name}",
            f"**UniProt ID:** {result.uniprot_id} | **Gene:** {gene_name} | **Generated:** {timestamp}",
            "",
            f"> {badge_line}",
            "",
            "---",

            "## 1. Protein Overview",
            "| Field | Value |",
            "|-------|-------|",
            f"| Protein Name | {protein_name} |",
            f"| UniProt ID | {result.uniprot_id} |",
            f"| Gene | {gene_name} |",
            f"| Organism | {organism} |",
            f"| Sequence Length | {p.sequence_length if p else 'N/A'} amino acids |",
            f"| Primary Class | {badges.get('primary_class','Unknown')} |",
            f"| Expression Profile | {badges.get('expression_class','Unknown')} |",
            f"| Structural Type | {badges.get('structural_class','Unknown')} |",
            f"| Mutation Mechanism | {badges.get('mutation_mechanism','Unknown')} |",
            f"| Therapeutic Tier | {badges.get('therapeutic_tier','Unknown')} |",
            "",

            "## 2. Gene Information",
        ]

        if p and p.cross_references:
            for db, ids in p.cross_references.items():
                sections.append(f"- **{db}:** {', '.join(ids[:3])}")
        else:
            sections.append("_Not available._")

        sections += ["", "## 3. Protein Function",
            p.function_description if p and p.function_description else "_Not available._", ""]

        sections.append("## 4. GO Annotations")
        if p and p.go_annotations:
            for cat in ["biological_process", "molecular_function", "cellular_component"]:
                terms = [go for go in p.go_annotations if go.category == cat]
                if terms:
                    sections.append(f"### {cat.replace('_', ' ').title()}")
                    for go in terms[:8]:
                        sections.append(f"- **{go.term_id}**: {go.term_name}")
        else:
            sections.append("_Not available._")

        # Expression — GTEx priority
        sections += ["", "## 5. Expression Analysis (GTEx + HPA)"]
        if gtex_d and gtex_d.tissues:
            sections.append(f"**Top expressed tissues (GTEx v8):** {', '.join(gtex_d.top_expressed[:8])}")
            sections.append("\n| Tissue | Median TPM | Level |")
            sections.append("|--------|-----------|-------|")
            for t in gtex_d.tissues[:15]:
                sections.append(f"| {t.tissue} | {t.median_tpm} | {t.level} |")
        elif expr and expr.summary:
            sections.append(expr.summary)
            if expr.tissue_expressions:
                for t in expr.tissue_expressions[:10]:
                    sections.append(f"- **{t.tissue}**: {t.level}")
        else:
            sections.append("_Expression data not available._")

        if expr and expr.subcellular_locations:
            sections.append(f"\n**Subcellular Localization:** {', '.join(expr.subcellular_locations)}")

        sections += ["", "## 6. Disease Associations"]
        diseases = p.diseases if p and p.diseases else []
        if diseases:
            for d in diseases:
                sections.append(f"- {d}")
        else:
            sections.append("_Not found._")

        # Open Targets disease associations
        if ot and ot.disease_associations:
            sections.append("\n### Open Targets Evidence Scores")
            sections.append("| Disease | Score |")
            sections.append("|---------|-------|")
            for d in ot.disease_associations[:10]:
                sections.append(f"| {d.get('disease','')} | {d.get('score',0):.3f} |")

        sections += ["", "## 7. Mutation Analysis",
            mut.summary if mut and mut.summary else "_Not available._", ""]

        if mut and mut.variants:
            sections.append(f"**Pathogenic/likely-pathogenic variants:** {mut.pathogenic_count}")
            pathogenic = [v for v in mut.variants
                         if "pathogenic" in (v.clinical_significance or "").lower()][:10]
            if pathogenic:
                sections.append("| Variant | Significance | Condition |")
                sections.append("|---------|-------------|-----------|")
                for v in pathogenic:
                    sections.append(f"| {v.change or v.variant_id} | {v.clinical_significance} | {v.condition} |")

        sections += ["", "## 8. Structural Information",
            struct.summary if struct and struct.summary else "_Not available._", ""]
        if struct:
            if struct.alphafold_available:
                sections.append(f"- **AlphaFold:** [View Structure]({struct.alphafold_url})")
            if struct.pdb_ids:
                sections.append(f"- **PDB ({struct.pdb_count} total):** {', '.join(struct.pdb_ids[:8])}")

        # STRING interactions
        sections += ["", "## 9. Protein-Protein Interactions (STRING DB)"]
        if string_d and string_d.interactions:
            sections.append(f"**Top interaction partners:** {', '.join(string_d.top_partners[:10])}")
            sections.append("\n| Partner | Combined Score | Experimental | Database |")
            sections.append("|---------|---------------|-------------|----------|")
            for i in string_d.interactions[:10]:
                sections.append(f"| {i.partner} | {i.score} | {i.experimental_score} | {i.database_score} |")
        else:
            sections.append("_STRING interaction data not available._")

        # Reactome pathways
        sections += ["", "## 10. Biological Pathways (Reactome)"]
        if reactome_d and reactome_d.pathways:
            sections.append(f"**{reactome_d.pathway_count} pathways identified**\n")
            for pw in reactome_d.pathways[:12]:
                sections.append(f"- [{pw.pathway_name}]({pw.url}) `{pw.pathway_id}`")
        else:
            sections.append("_Reactome pathway data not available._")

        # Drug landscape
        sections += ["", "## 11. Drug & Therapeutic Landscape (Open Targets)"]
        if ot and ot.drugs:
            sections.append(f"**{ot.drug_count} drugs identified targeting this protein**\n")
            sections.append("| Drug | Type | Phase | Mechanism | Indication |")
            sections.append("|------|------|-------|-----------|------------|")
            for d in ot.drugs[:15]:
                sections.append(f"| {d.name} | {d.type or 'N/A'} | {d.phase or 'N/A'} | {d.mechanism or 'N/A'} | {d.disease or 'N/A'} |")
        else:
            sections.append("_Drug data not available from Open Targets._")

        sections += ["", "## 12. Literature Review",
            lit.literature_review if lit and lit.literature_review else "_Not available._", ""]

        sections += ["", "## 13. Research Insights", insights, ""]

        # Chief Scientist Classification
        sections += [
            "## 14. 🔬 Chief Scientist Protein Classification",
            "> *Expert multi-dimensional classification for research & drug discovery*",
            "",
            classification_text,
            "",
        ]

        sections += ["## 15. Conclusion", conclusion, "",
            "## 16. References", citation_svc.format_references(), "",
            "---",
            f"*Report generated by Agentic Bioinformatics Research Assistant | {timestamp}*"]

        if result.errors:
            sections.append("\n## ⚠️ Notes")
            for agent, err in result.errors.items():
                sections.append(f"- **{agent}:** {err}")

        return "\n\n".join(sections)
