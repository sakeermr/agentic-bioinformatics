"""
tests/test_api.py
-----------------
Unit and integration tests for the FastAPI endpoints.
Uses pytest + httpx TestClient with mocked agent calls.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import ResearchResult, ProteinData

client = TestClient(app)


# ── Helper fixtures ───────────────────────────────────────────

def _mock_result(uniprot_id: str = "P04637") -> ResearchResult:
    """Return a minimal mocked ResearchResult."""
    return ResearchResult(
        uniprot_id=uniprot_id,
        protein=ProteinData(
            uniprot_id=uniprot_id,
            protein_name="Cellular tumor antigen p53",
            gene_name="TP53",
            organism="Homo sapiens",
            sequence_length=393,
            function_description="Acts as a tumor suppressor.",
        ),
        markdown_report="# Test Report\n\nTest content.",
        pdf_path=None,
    )


# ── Health check ──────────────────────────────────────────────

def test_health_check():
    """API health endpoint should return 200."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root():
    """Root endpoint should return service info."""
    response = client.get("/")
    assert response.status_code == 200
    assert "name" in response.json()


# ── Analyze endpoint ──────────────────────────────────────────

def test_analyze_invalid_uniprot_id():
    """Invalid UniProt ID should return 422."""
    response = client.post("/api/v1/analyze", json={"uniprot_id": "INVALID123"})
    assert response.status_code == 422


def test_analyze_empty_uniprot_id():
    """Empty string should fail validation."""
    response = client.post("/api/v1/analyze", json={"uniprot_id": ""})
    assert response.status_code in (422, 400)


@patch("app.api.routes.orchestrator")
def test_analyze_valid_id(mock_orchestrator):
    """Valid UniProt ID should trigger pipeline and return structured response."""
    mock_orchestrator.validate_uniprot_id.return_value = True
    mock_orchestrator.run.return_value = _mock_result("P04637")

    response = client.post("/api/v1/analyze", json={"uniprot_id": "P04637"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("success", "partial")
    assert "report_id" in body
    assert "data" in body


@patch("app.api.routes.orchestrator")
def test_analyze_returns_protein_data(mock_orchestrator):
    """Response should contain structured protein data."""
    mock_orchestrator.validate_uniprot_id.return_value = True
    mock_orchestrator.run.return_value = _mock_result("P04637")

    response = client.post("/api/v1/analyze", json={"uniprot_id": "P04637"})
    data = response.json()["data"]
    assert "protein" in data
    assert data["protein"]["gene_name"] == "TP53"


# ── Report retrieval ──────────────────────────────────────────

def test_get_report_not_found():
    """Unknown report ID should return 404."""
    response = client.get("/api/v1/report/nonexistent_id")
    assert response.status_code == 404


def test_get_markdown_not_found():
    """Unknown report ID should return 404 for markdown endpoint."""
    response = client.get("/api/v1/report/nonexistent_id/markdown")
    assert response.status_code == 404


# ── UniProt validation ────────────────────────────────────────

def test_uniprot_id_validation():
    """Test the ID format validator."""
    from app.agents.orchestrator import Orchestrator
    orch = Orchestrator.__new__(Orchestrator)

    valid_ids = ["P04637", "Q9Y6K9", "O00571", "P00533"]
    invalid_ids = ["INVALID", "12345", "p04637", "toolongid123456"]

    for uid in valid_ids:
        assert Orchestrator.validate_uniprot_id(uid), f"Should be valid: {uid}"

    for uid in invalid_ids:
        assert not Orchestrator.validate_uniprot_id(uid), f"Should be invalid: {uid}"


# ── Tool-level tests ──────────────────────────────────────────

def test_parse_protein_name():
    """Test UniProt name parsing with mock data."""
    from app.tools.uniprot_tools import parse_protein_name
    mock_data = {
        "proteinDescription": {
            "recommendedName": {
                "fullName": {"value": "Cellular tumor antigen p53"}
            }
        }
    }
    assert parse_protein_name(mock_data) == "Cellular tumor antigen p53"


def test_parse_gene_name():
    """Test gene name extraction."""
    from app.tools.uniprot_tools import parse_gene_name
    mock_data = {
        "genes": [{"geneName": {"value": "TP53"}}]
    }
    assert parse_gene_name(mock_data) == "TP53"


def test_parse_function():
    """Test function comment extraction."""
    from app.tools.uniprot_tools import parse_function
    mock_data = {
        "comments": [
            {
                "commentType": "FUNCTION",
                "texts": [{"value": "Acts as a tumor suppressor."}]
            }
        ]
    }
    assert "tumor suppressor" in parse_function(mock_data)
