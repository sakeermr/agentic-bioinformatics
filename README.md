# 🧬 Agentic Bioinformatics Research Assistant

> An AI-powered multi-agent system that autonomously researches proteins using multiple biomedical databases and generates publication-quality scientific reports.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40-red.svg)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🎯 What It Does

Enter a **UniProt ID** (e.g. `P04637` for TP53) and the system autonomously:

1. Fetches protein metadata from **UniProt**
2. Searches and summarizes **PubMed** literature using RAG + LLM
3. Retrieves tissue expression from **Human Protein Atlas**
4. Queries **ClinVar** for pathogenic variants
5. Checks **AlphaFold** and **RCSB PDB** for 3D structures
6. Synthesizes all data into a **structured scientific report** (Markdown + PDF)

---

## 🏗️ Architecture

```
User Input (UniProt ID)
         │
    Orchestrator
         │
    ┌────┴────┐ parallel execution
    │         │
UniProt   Literature   Expression   Mutation   Structure
 Agent      Agent        Agent       Agent      Agent
    │         │            │           │          │
    └────┬────┘────────────┘───────────┘──────────┘
         │
   Results Aggregation
         │
    LLM Synthesis (OpenAI GPT-4o-mini)
         │
   Report Agent
         │
   Markdown + PDF Report
```

**Databases Used:**
| Database | Data |
|----------|------|
| UniProt REST API | Protein metadata, GO annotations, diseases |
| NCBI PubMed | Literature search and abstracts |
| Europe PMC | Literature fallback |
| Human Protein Atlas | Tissue/cancer expression |
| ClinVar | Pathogenic variants |
| AlphaFold DB | Predicted structures |
| RCSB PDB | Experimental structures |

---

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/sakeermr/agentic-bioinformatics.git
cd agentic-bioinformatics
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate        # Linux/Mac
# OR
venv\Scripts\activate           # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your API keys:

```env
OPENAI_API_KEY=sk-...           # Required
NCBI_EMAIL=your@email.com       # Required (free)
NCBI_API_KEY=...                # Optional but recommended (free)
```

> **Get a free NCBI API key:** https://www.ncbi.nlm.nih.gov/account/

### 5. Run the API

```bash
uvicorn app.main:app --reload
```

API will be available at: http://localhost:8000  
Interactive docs: http://localhost:8000/docs

### 6. Run the Streamlit UI

In a **new terminal**:

```bash
streamlit run app/ui/streamlit_app.py
```

UI will open at: http://localhost:8501

---

## 🔑 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | ✅ Yes | OpenAI API key for LLM + embeddings |
| `NCBI_EMAIL` | ✅ Yes | Email for NCBI API (required by NCBI) |
| `GEMINI_API_KEY` | ❌ Optional | Gemini API key (LLM fallback) |
| `NCBI_API_KEY` | ❌ Optional | NCBI API key (higher rate limits) |
| `LLM_MODEL` | ❌ Optional | OpenAI model (default: `gpt-4o-mini`) |
| `LLM_PROVIDER` | ❌ Optional | `openai` or `gemini` (default: `openai`) |

---

## 📡 API Usage

### Analyze a Protein

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"uniprot_id": "P04637"}'
```

Response:
```json
{
  "status": "success",
  "report_id": "a1b2c3d4",
  "summary": "Protein: Cellular tumor antigen p53 | Variants: 892 pathogenic | ...",
  "data": { ... },
  "duration_seconds": 45.2
}
```

### Download PDF Report

```bash
curl http://localhost:8000/api/v1/report/{report_id} -o report.pdf
```

### Health Check

```bash
curl http://localhost:8000/api/v1/health
```

---

## 🐳 Docker Deployment

```bash
cp .env.example .env
# Fill in your API keys in .env

docker-compose up --build
```

- API: http://localhost:8000
- UI:  http://localhost:8501

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

---

## 📁 Project Structure

```
agentic-bioinformatics/
├── app/
│   ├── agents/
│   │   ├── uniprot_agent.py       # UniProt data retrieval
│   │   ├── literature_agent.py    # PubMed + RAG + LLM synthesis
│   │   ├── expression_agent.py    # Human Protein Atlas
│   │   ├── mutation_agent.py      # ClinVar variants
│   │   ├── structure_agent.py     # AlphaFold + PDB
│   │   ├── report_agent.py        # Final report generation
│   │   └── orchestrator.py        # Parallel workflow coordinator
│   ├── tools/                     # Direct API wrappers
│   ├── services/                  # LLM, PDF, embedding, citation
│   ├── models/                    # Pydantic schemas
│   ├── api/                       # FastAPI routes
│   ├── ui/                        # Streamlit UI
│   ├── config/                    # Settings
│   └── main.py
├── tests/
├── reports/                       # Generated PDF/MD reports
├── chroma_db/                     # Vector store
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## 📄 Report Sections

Generated reports contain:

1. Protein Overview
2. Gene Information
3. Protein Function
4. GO Annotations
5. Expression Analysis
6. Disease Associations
7. Mutation Analysis
8. Structural Information
9. Literature Review (AI-synthesized)
10. Research Insights (AI-generated)
11. Conclusion
12. References

---

## 🗺️ Roadmap

**Phase 1 (Current):** MVP — UniProt → Multi-agent → PDF Report

**Phase 2:** Graph RAG, protein-protein interaction networks  
**Phase 3:** Molecular docking integration  
**Phase 4:** Autonomous hypothesis generation  
**Phase 5:** Kubernetes deployment, cloud GPU inference

---

## 📸 Screenshots

*(Add screenshots here after first run)*

---

## 🙏 Data Sources

- [UniProt](https://www.uniprot.org/) — Protein knowledgebase
- [NCBI PubMed](https://pubmed.ncbi.nlm.nih.gov/) — Biomedical literature
- [Human Protein Atlas](https://www.proteinatlas.org/) — Expression data
- [ClinVar](https://www.ncbi.nlm.nih.gov/clinvar/) — Clinical variants
- [AlphaFold DB](https://alphafold.ebi.ac.uk/) — Predicted structures
- [RCSB PDB](https://www.rcsb.org/) — Experimental structures

---

## 📝 License

MIT License — see [LICENSE](LICENSE) for details.
