"""
api/routes.py
-------------
FastAPI routes including new batch analysis endpoint.
"""

import logging
import time
import uuid
from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.models.schemas import AnalyzeRequest, AnalyzeResponse
from app.agents.orchestrator import Orchestrator
from app.config.settings import REPORTS_DIR

logger = logging.getLogger(__name__)
router = APIRouter()

orchestrator = Orchestrator()

# In-memory job store
_jobs: dict[str, dict] = {}
_batch_jobs: dict[str, dict] = {}


# ── Single Analysis ───────────────────────────────────────────

@router.get("/health", tags=["System"])
def health_check():
    return {"status": "healthy", "service": "Agentic Bioinformatics Research Assistant"}


@router.post("/analyze", response_model=AnalyzeResponse, tags=["Research"])
def analyze_protein(request: AnalyzeRequest):
    """Run full research pipeline for a single UniProt ID."""
    uniprot_id = request.uniprot_id.strip().upper()

    if not orchestrator.validate_uniprot_id(uniprot_id):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid UniProt ID format: '{uniprot_id}'. Expected format: P04637"
        )

    logger.info("POST /analyze — %s", uniprot_id)
    start = time.time()

    try:
        result = orchestrator.run(uniprot_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}") from exc

    elapsed = round(time.time() - start, 2)
    report_id = str(uuid.uuid4())[:8]

    _jobs[report_id] = {
        "uniprot_id": uniprot_id,
        "pdf_path": result.pdf_path,
        "markdown": result.markdown_report,
    }

    summary_parts = []
    if result.protein:
        summary_parts.append(f"Protein: {result.protein.protein_name}")
    if result.mutations:
        summary_parts.append(f"Variants: {result.mutations.pathogenic_count}")
    if result.structure:
        summary_parts.append(f"PDB: {result.structure.pdb_count} structures")

    return AnalyzeResponse(
        status="success" if not result.errors else "partial",
        report_id=report_id,
        report_path=result.pdf_path,
        summary=" | ".join(summary_parts),
        data={
            "protein": result.protein.model_dump() if result.protein else None,
            "literature_count": len(result.literature.papers) if result.literature else 0,
            "expression": result.expression.model_dump() if result.expression else None,
            "mutations": result.mutations.model_dump() if result.mutations else None,
            "structure": result.structure.model_dump() if result.structure else None,
            "errors": result.errors,
        },
        duration_seconds=elapsed,
    )


# ── Batch Analysis ────────────────────────────────────────────

class BatchRequest(BaseModel):
    uniprot_ids: List[str]
    class Config:
        json_schema_extra = {
            "example": {"uniprot_ids": ["P04637", "P00533", "Q9Y6K9"]}
        }


class BatchJobStatus(BaseModel):
    batch_id: str
    status: str
    total: int
    completed: int
    failed: int
    results: list
    duration_seconds: float = 0.0


@router.post("/analyze/batch", tags=["Research"])
def analyze_batch(request: BatchRequest, background_tasks: BackgroundTasks):
    """
    Run research pipeline for multiple UniProt IDs.
    Returns a batch_id to track progress via GET /batch/{batch_id}
    """
    # Validate all IDs first
    valid_ids = []
    invalid_ids = []
    for uid in request.uniprot_ids:
        uid_clean = uid.strip().upper()
        if orchestrator.validate_uniprot_id(uid_clean):
            valid_ids.append(uid_clean)
        else:
            invalid_ids.append(uid_clean)

    if not valid_ids:
        raise HTTPException(
            status_code=422,
            detail=f"No valid UniProt IDs provided. Invalid: {invalid_ids}"
        )

    if len(valid_ids) > 10:
        raise HTTPException(
            status_code=422,
            detail="Maximum 10 proteins per batch. Please split into smaller batches."
        )

    batch_id = str(uuid.uuid4())[:8]
    _batch_jobs[batch_id] = {
        "status": "running",
        "total": len(valid_ids),
        "completed": 0,
        "failed": 0,
        "invalid": invalid_ids,
        "results": [],
        "start_time": time.time(),
    }

    logger.info("Batch job %s started — %d proteins", batch_id, len(valid_ids))

    # Run in background
    background_tasks.add_task(_run_batch, batch_id, valid_ids)

    return {
        "batch_id": batch_id,
        "status": "started",
        "total": len(valid_ids),
        "invalid_ids": invalid_ids,
        "message": f"Batch analysis started. Track progress at GET /api/v1/batch/{batch_id}",
        "estimated_time_minutes": round(len(valid_ids) * 1.5, 1),
    }


def _run_batch(batch_id: str, uniprot_ids: list):
    """Background task that runs all proteins sequentially."""
    job = _batch_jobs[batch_id]

    for uid in uniprot_ids:
        try:
            logger.info("Batch %s: processing %s (%d/%d)",
                       batch_id, uid, job["completed"] + 1, job["total"])
            start = time.time()
            result = orchestrator.run(uid)
            elapsed = round(time.time() - start, 2)

            report_id = str(uuid.uuid4())[:8]
            _jobs[report_id] = {
                "uniprot_id": uid,
                "pdf_path": result.pdf_path,
                "markdown": result.markdown_report,
            }

            job["results"].append({
                "uniprot_id": uid,
                "status": "success",
                "report_id": report_id,
                "protein_name": result.protein.protein_name if result.protein else uid,
                "gene_name": result.protein.gene_name if result.protein else "Unknown",
                "pdf_path": result.pdf_path,
                "duration_seconds": elapsed,
                "summary": {
                    "variants": result.mutations.pathogenic_count if result.mutations else 0,
                    "pdb_structures": result.structure.pdb_count if result.structure else 0,
                    "papers": len(result.literature.papers) if result.literature else 0,
                    "primary_class": result.protein.protein_name if result.protein else "Unknown",
                }
            })
            job["completed"] += 1

        except Exception as exc:
            logger.error("Batch %s: failed for %s — %s", batch_id, uid, exc)
            job["results"].append({
                "uniprot_id": uid,
                "status": "failed",
                "error": str(exc),
            })
            job["failed"] += 1

    job["status"] = "complete"
    job["duration_seconds"] = round(time.time() - job["start_time"], 2)
    logger.info("Batch %s complete — %d success, %d failed",
               batch_id, job["completed"], job["failed"])


@router.get("/batch/{batch_id}", tags=["Research"])
def get_batch_status(batch_id: str):
    """Get status and results of a batch analysis job."""
    job = _batch_jobs.get(batch_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Batch job '{batch_id}' not found.")

    return {
        "batch_id": batch_id,
        "status": job["status"],
        "total": job["total"],
        "completed": job["completed"],
        "failed": job["failed"],
        "progress_percent": round((job["completed"] + job["failed"]) / job["total"] * 100),
        "results": job["results"],
        "duration_seconds": job.get("duration_seconds", 0),
        "invalid_ids": job.get("invalid", []),
    }


# ── Report Download ───────────────────────────────────────────

@router.get("/report/{report_id}", tags=["Research"])
def get_report(report_id: str):
    """Download PDF report."""
    job = _jobs.get(report_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")
    pdf_path = job.get("pdf_path")
    if not pdf_path or not Path(pdf_path).exists():
        raise HTTPException(status_code=404, detail="PDF file not found.")
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=Path(pdf_path).name,
    )


@router.get("/report/{report_id}/markdown", tags=["Research"])
def get_report_markdown(report_id: str):
    """Return Markdown report."""
    job = _jobs.get(report_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Report '{report_id}' not found.")
    return {"report_id": report_id, "markdown": job.get("markdown", "")}