# 🧬 Agentic Bioinformatics Research Assistant

> An AI-powered multi-agent system that autonomously researches proteins using 8 biomedical databases and generates publication-quality scientific reports.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.40-red.svg)](https://streamlit.io)
[![Live Demo](https://img.shields.io/badge/Live%20Demo-Streamlit%20Cloud-ff4b4b.svg)](https://agentic-bioinformatics.streamlit.app)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🌐 Live Demo

👉 **https://agentic-bioinformatics.streamlit.app**

---

## 🎯 What It Does

Enter a **UniProt ID** (e.g. `P04637` for TP53) and the system autonomously:

1. Fetches protein metadata from **UniProt**
2. Searches and summarizes **PubMed** literature using RAG + LLM
3. Retrieves tissue expression from **GTEx** (54 tissues)
4. Queries **ClinVar** for pathogenic variants
5. Checks **AlphaFold** and **RCSB PDB** for 3D structures
6. Fetches protein-protein interactions from **STRING DB**
7. Retrieves biological pathways from **Reactome**
8. Gets drug landscape from **Open Targets**
9. Synthesizes all data into a **16-section scientific report** (Markdown + PDF)

---

## 🏗️ Architecture

```
User Input (UniProt ID)
         │
    Orchestrator
         │
    ┌────┴──────────────────────────────┐
    │         Parallel Execution         │
    ├──────────────────────────────────┤
    │ UniProt  │ Literature │ Expression │
    │  Agent   │   Agent    │   Agent    │
    ├──────────────────────────────────┤
    │ Mutation │ Structure  │Enrichment  │
    │  Agent   │   Agent    │   Agent    │
    └────┬──────────────────────────────┘
         │
   Results Aggregation
         │
    LLM Synthesis (OpenAI GPT-4o-mini)
         │
   Report Agent (16 Sections)
         │
   Markdown + PDF Report
```

---

## 🔬 Databases Integrated (8 Total)

| Database | Data Retrieved |
|----------|---------------|
| **UniProt** | Protein metadata, GO annotations, diseases |
| **NCBI PubMed** | Literature search and AI-synthesized review |
| **GTEx v8** | Tissue expression across 54 human tissues |
| **ClinVar** | Pathogenic variants and disease associations |
| **AlphaFold DB** | Predicted 3D structures |
| **RCSB PDB** | Experimental 3D structures |
| **STRING DB** | Protein-protein interaction network |
| **Reactome** | Biological pathway analysis |
| **Open Targets** | Drug landscape and therapeutic evidence |

---

## 📊 Report Sections (16 Total)

| # | Section | Data Source |
|---|---------|-------------|
| 1 | Protein Overview + Badge Classification | UniProt |
| 2 | Gene Information | UniProt |
| 3 | Protein Function | UniProt |
| 4 | GO Annotations | UniProt |
| 5 | Expression Analysis | GTEx v8 |
| 6 | Disease Associations | UniProt + Open Targets |
| 7 | Mutation Analysis | ClinVar |
| 8 | Structural Information | AlphaFold + PDB |
| 9 | Protein-Protein Interactions | STRING DB |
| 10 | Biological Pathways | Reactome |
| 11 | Drug & Therapeutic Landscape | Open Targets |
| 12 | Literature Review | PubMed + AI |
| 13 | Research Insights | AI Synthesis |
| 14 | Chief Scientist Classification | AI Analysis |
| 15 | Conclusion | AI Synthesis |
| 16 | References | PubMed |

---

## 🔬 Chief Scientist AI Classification

Every report includes a multi-dimensional protein classification:

- 🔴 **Primary Class** — Tumor Suppressor / Oncogene / Kinase / etc.
- 📊 **Expression Profile** — Overexpressed / Tissue-Restricted / Ubiquitous
- 🏗️ **Structural Type** — Stable Globular / IDP / Allosteric
- ⚡ **Mutation Mechanism** — Loss-of-Function / Gain-of-Function
- 💊 **Therapeutic Tier** — Tier 1 (Established) to Tier 5 (Undruggable)
- 🏆 **Chief Scientist Verdict** — Expert summary and research directions

---

## 🚀 Features

- ✅ **Single protein analysis** — deep 16-section report
- ✅ **Batch analysis** — up to 10 proteins at once with ZIP download
- ✅ **CSV upload** — bulk analyze up to 100 proteins
- ✅ **PDF + Markdown export** — publication-ready reports
- ✅ **Excel summary table** — for batch/CSV results
- ✅ **Live deployment** — Streamlit Cloud + ngrok tunnel

---

## 🛠️ Local Installation

### 1. Clone the Repository

```bash
git clone https://github.com/sakeermr/agentic-bioinformatics.git
cd agentic-bioinformatics
```

### 2. Create Virtual Environment

```bash
# Windows
py -3.11 -m venv venv
venv\Scripts\activate

# Mac/Linux
python3.11 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
OPENAI_API_KEY=sk-your-key-here
NCBI_EMAIL=your@email.com
NCBI_API_KEY=your-ncbi-key
```

### 5. Run the API

```bash
uvicorn app.main:app --reload
```

API available at: http://localhost:8000
Interactive docs: http://localhost:8000/docs

### 6. Run the UI

```bash
streamlit run app/ui/streamlit_app.py
```

UI available at: http://localhost:8501

---

## ☁️ Cloud Deployment (Streamlit Cloud + ngrok)

### Architecture

```
Streamlit Cloud (UI) ──► ngrok tunnel ──► Your PC (FastAPI)
```

### Setup

1. Push code to GitHub
2. Deploy UI on [Streamlit Community Cloud](https://share.streamlit.io)
3. Install and run ngrok: `ngrok http 8000`
4. Add to Streamlit Cloud secrets:
   ```
   OPENAI_API_KEY = "sk-..."
   NCBI_EMAIL = "your@email.com"
   NCBI_API_KEY = "your-key"
   API_BASE_URL = "https://your-ngrok-url.ngrok-free.dev"
   ```

### Daily Startup

```bash
# Terminal 1 - API
uvicorn app.main:app --reload

# Terminal 2 - ngrok tunnel
ngrok http 8000
```

If ngrok URL changes, update `API_BASE_URL` in Streamlit Cloud secrets.

---

## 📡 API Endpoints

### Single Analysis
```bash
POST /api/v1/analyze
{"uniprot_id": "P04637"}
```

### Batch Analysis
```bash
POST /api/v1/analyze/batch
{"uniprot_ids": ["P04637", "P00533", "P15056"]}
```

### Get Report
```bash
GET /api/v1/report/{report_id}          # PDF download
GET /api/v1/report/{report_id}/markdown # Markdown
GET /api/v1/batch/{batch_id}            # Batch status
GET /api/v1/health                      # Health check
```

---

## 🔑 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | ✅ | OpenAI API key for LLM + embeddings |
| `NCBI_EMAIL` | ✅ | Email for NCBI API (required by NCBI) |
| `NCBI_API_KEY` | ✅ | NCBI API key (higher rate limits) |
| `GEMINI_API_KEY` | ❌ | Gemini API key (LLM fallback) |
| `LLM_MODEL` | ❌ | OpenAI model (default: `gpt-4o-mini`) |
| `API_BASE_URL` | ❌ | ngrok URL for cloud deployment |

---

## 📁 Project Structure

```
agentic-bioinformatics/
├── app/
│   ├── agents/
│   │   ├── uniprot_agent.py       # UniProt data retrieval
│   │   ├── literature_agent.py    # PubMed + RAG + LLM
│   │   ├── expression_agent.py    # GTEx expression
│   │   ├── mutation_agent.py      # ClinVar variants
│   │   ├── structure_agent.py     # AlphaFold + PDB
│   │   ├── enrichment_agent.py    # STRING + Reactome + Open Targets
│   │   ├── report_agent.py        # 16-section report generation
│   │   └── orchestrator.py        # Parallel workflow coordinator
│   ├── tools/                     # Direct API wrappers
│   │   ├── uniprot_tools.py
│   │   ├── pubmed_tools.py
│   │   ├── hpa_tools.py
│   │   ├── clinvar_tools.py
│   │   ├── alphafold_tools.py
│   │   ├── string_tools.py
│   │   ├── reactome_tools.py
│   │   ├── gtex_tools.py
│   │   ├── opentargets_tools.py
│   │   └── vectorstore.py
│   ├── services/
│   │   ├── llm_service.py         # OpenAI + Gemini
│   │   ├── embedding_service.py   # ChromaDB RAG
│   │   ├── pdf_service.py         # ReportLab PDF
│   │   └── citation_service.py    # Reference formatting
│   ├── models/schemas.py          # Pydantic data models
│   ├── api/routes.py              # FastAPI endpoints
│   ├── ui/streamlit_app.py        # Streamlit UI
│   ├── config/settings.py         # Configuration
│   └── main.py                    # App entry point
├── tests/
├── reports/                       # Generated PDF reports
├── chroma_db/                     # Vector store
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## 🧪 Testing

```bash
pytest tests/ -v
```

---

## 🐳 Docker

```bash
cp .env.example .env
# Fill in your API keys

docker-compose up --build
```

- API: http://localhost:8000
- UI: http://localhost:8501

---

## 🗺️ Roadmap

**Phase 1 (Complete):** MVP — 8 databases, 16-section report, batch/CSV processing, cloud deployment

**Phase 2:** Graph RAG, protein-protein interaction networks
**Phase 3:** Molecular docking integration
**Phase 4:** Autonomous hypothesis generation
**Phase 5:** Kubernetes deployment, always-on cloud GPU inference

---

## 📸 Screenshots

*(Add screenshots here)*

---

## 🙏 Data Sources

- [UniProt](https://www.uniprot.org/) — Protein knowledgebase
- [NCBI PubMed](https://pubmed.ncbi.nlm.nih.gov/) — Biomedical literature
- [GTEx](https://gtexportal.org/) — Tissue expression
- [ClinVar](https://www.ncbi.nlm.nih.gov/clinvar/) — Clinical variants
- [AlphaFold DB](https://alphafold.ebi.ac.uk/) — Predicted structures
- [RCSB PDB](https://www.rcsb.org/) — Experimental structures
- [STRING DB](https://string-db.org/) — Protein interactions
- [Reactome](https://reactome.org/) — Biological pathways
- [Open Targets](https://www.opentargets.org/) — Drug target evidence

---

## 📝 License

MIT License — see [LICENSE](LICENSE) for details.

---

*Built with ❤️ for the bioinformatics research community*
