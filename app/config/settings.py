"""
config/settings.py
------------------
Central configuration loaded from environment variables via dotenv.
All modules import from here — never hardcode values elsewhere.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
load_dotenv()

# ── Project Paths ────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parents[2]
REPORTS_DIR = BASE_DIR / os.getenv("REPORTS_DIR", "reports")
CHROMA_DB_PATH = BASE_DIR / os.getenv("CHROMA_DB_PATH", "chroma_db")
DATA_DIR = BASE_DIR / "data"

# Ensure directories exist
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ── LLM Configuration ────────────────────────────────────────
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# ── NCBI / PubMed ────────────────────────────────────────────
NCBI_API_KEY: str = os.getenv("NCBI_API_KEY", "")
NCBI_EMAIL: str = os.getenv("NCBI_EMAIL", "researcher@bioinformatics.ai")

# ── External API Base URLs ───────────────────────────────────
UNIPROT_BASE_URL = "https://rest.uniprot.org/uniprotkb"
PUBMED_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
HPA_BASE_URL = "https://www.proteinatlas.org"
ALPHAFOLD_BASE_URL = "https://alphafold.ebi.ac.uk/api"
RCSB_BASE_URL = "https://data.rcsb.org/rest/v1/core"
CLINVAR_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EUROPEPMC_BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"

# ── Request Settings ─────────────────────────────────────────
REQUEST_TIMEOUT: int = 45          # seconds
MAX_RETRIES: int = 2
RETRY_DELAY: float = 1.5           # seconds between retries

# ── Literature Settings ──────────────────────────────────────
MAX_PUBMED_RESULTS: int = 15
MAX_ABSTRACTS_FOR_RAG: int = 10

# ── FastAPI ──────────────────────────────────────────────────
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))

# ── Logging ──────────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")