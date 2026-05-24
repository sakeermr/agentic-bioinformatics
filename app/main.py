"""
main.py
--------
FastAPI application entry point.
Run with: uvicorn app.main:app --reload
"""

import logging
import logging.config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config.settings import LOG_LEVEL

# ── Logging Configuration ─────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── FastAPI App ───────────────────────────────────────────────
app = FastAPI(
    title="Agentic Bioinformatics Research Assistant",
    description=(
        "An AI-powered multi-agent system that autonomously researches proteins "
        "using UniProt, PubMed, Human Protein Atlas, ClinVar, AlphaFold, and more. "
        "Generates structured scientific reports in Markdown and PDF."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────
# Allows the Streamlit UI (on a different port) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────
app.include_router(router, prefix="/api/v1")

# ── Startup event ─────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    logger.info("Agentic Bioinformatics Research Assistant starting up...")
    logger.info("API docs: http://localhost:8000/docs")


@app.get("/", tags=["Root"])
def root():
    return {
        "name": "Agentic Bioinformatics Research Assistant",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
