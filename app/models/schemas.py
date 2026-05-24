"""
models/schemas.py
-----------------
Pydantic data models used across all agents and API endpoints.
Provides type safety and automatic validation throughout the system.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime


# ── API Request / Response ────────────────────────────────────

class AnalyzeRequest(BaseModel):
    """Input payload for the /analyze endpoint."""
    uniprot_id: str = Field(..., example="P04637", description="Valid UniProt accession ID")


class AnalyzeResponse(BaseModel):
    """Output payload returned by /analyze endpoint."""
    status: str
    report_id: str
    report_path: Optional[str] = None
    summary: Optional[str] = None
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    duration_seconds: Optional[float] = None


# ── Protein Data ──────────────────────────────────────────────

class GOAnnotation(BaseModel):
    term_id: str
    term_name: str
    category: str          # biological_process | molecular_function | cellular_component


class ProteinData(BaseModel):
    uniprot_id: str
    protein_name: Optional[str] = None
    gene_name: Optional[str] = None
    organism: Optional[str] = None
    sequence: Optional[str] = None
    sequence_length: Optional[int] = None
    function_description: Optional[str] = None
    go_annotations: list[GOAnnotation] = []
    subcellular_locations: list[str] = []
    diseases: list[str] = []
    cross_references: dict[str, list[str]] = {}


# ── Literature Data ───────────────────────────────────────────

class PaperRecord(BaseModel):
    pmid: str
    title: str
    abstract: Optional[str] = None
    authors: list[str] = []
    journal: Optional[str] = None
    year: Optional[int] = None
    url: Optional[str] = None


class LiteratureData(BaseModel):
    query_used: str
    papers: list[PaperRecord] = []
    literature_review: Optional[str] = None   # LLM-generated synthesis


# ── Expression Data ───────────────────────────────────────────

class TissueExpression(BaseModel):
    tissue: str
    level: str            # High | Medium | Low | Not detected
    reliability: Optional[str] = None


class ExpressionData(BaseModel):
    uniprot_id: str
    tissue_expressions: list[TissueExpression] = []
    cancer_expressions: list[dict[str, str]] = []
    subcellular_locations: list[str] = []
    summary: Optional[str] = None


# ── Mutation / Variant Data ───────────────────────────────────

class Variant(BaseModel):
    variant_id: str
    gene: Optional[str] = None
    change: Optional[str] = None           # e.g. "R175H"
    clinical_significance: Optional[str] = None
    condition: Optional[str] = None
    review_status: Optional[str] = None


class MutationData(BaseModel):
    uniprot_id: str
    gene_name: Optional[str] = None
    variants: list[Variant] = []
    pathogenic_count: int = 0
    summary: Optional[str] = None


# ── Structure Data ────────────────────────────────────────────

class StructureData(BaseModel):
    uniprot_id: str
    alphafold_available: bool = False
    alphafold_url: Optional[str] = None
    alphafold_model_url: Optional[str] = None
    pdb_ids: list[str] = []
    pdb_count: int = 0
    summary: Optional[str] = None


# ── Aggregated Research Result ────────────────────────────────

class ResearchResult(BaseModel):
    """Complete aggregated result from all agents."""
    uniprot_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    protein: Optional[ProteinData] = None
    literature: Optional[LiteratureData] = None
    expression: Optional[ExpressionData] = None
    mutations: Optional[MutationData] = None
    structure: Optional[StructureData] = None
    markdown_report: Optional[str] = None
    pdf_path: Optional[str] = None
    errors: dict[str, str] = {}          # agent_name -> error message
    # New enrichment databases
    string_data: Optional[Any] = None
    reactome_data: Optional[Any] = None
    gtex_data: Optional[Any] = None
    opentargets_data: Optional[Any] = None
    classification: Optional[Any] = None


# ── New Database Schemas ──────────────────────────────────────

class StringInteraction(BaseModel):
    partner: str
    score: float
    experimental_score: float = 0.0
    database_score: float = 0.0

class StringData(BaseModel):
    gene_name: str
    interactions: list[StringInteraction] = []
    top_partners: list[str] = []

class ReactomePathway(BaseModel):
    pathway_id: str
    pathway_name: str
    species: str = "Homo sapiens"
    url: Optional[str] = None

class ReactomeData(BaseModel):
    uniprot_id: str
    pathways: list[ReactomePathway] = []
    pathway_count: int = 0

class GTExTissue(BaseModel):
    tissue: str
    median_tpm: float
    level: str
    source: str = "GTEx v8"

class GTExData(BaseModel):
    gene_name: str
    tissues: list[GTExTissue] = []
    top_expressed: list[str] = []

class DrugRecord(BaseModel):
    name: str
    type: Optional[str] = None
    phase: Optional[int] = None
    mechanism: Optional[str] = None
    disease: Optional[str] = None

class OpenTargetsData(BaseModel):
    target_id: Optional[str] = None
    drugs: list[DrugRecord] = []
    disease_associations: list[dict] = []
    drug_count: int = 0

class ProteinClassification(BaseModel):
    primary_class: Optional[str] = None
    expression_class: Optional[str] = None
    structural_class: Optional[str] = None
    mutation_mechanism: Optional[str] = None
    therapeutic_tier: Optional[str] = None
    verdict: Optional[str] = None
    badge_summary: Optional[str] = None
