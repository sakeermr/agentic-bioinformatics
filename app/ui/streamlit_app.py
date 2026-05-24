"""
ui/streamlit_app.py
Professional Streamlit UI with Single, Batch, and CSV Upload analysis tabs.
"""

import time
import io
import zipfile
import requests
import streamlit as st
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

st.set_page_config(
    page_title="Agentic Bioinformatics",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE = "http://127.0.0.1:8000/api/v1"

st.markdown("""
<style>
    .stApp { background-color: #f0f4f8; }
    .main-header {
        background: linear-gradient(135deg, #1a3a5c 0%, #2c5f8a 50%, #3a7abf 100%);
        color: white; padding: 2rem 2.5rem; border-radius: 12px;
        margin-bottom: 2rem; box-shadow: 0 4px 15px rgba(26,58,92,0.3);
    }
    .main-header h1 { color: white; margin: 0; font-size: 2rem; }
    .main-header p  { color: #b8d4f0; margin: 0.5rem 0 0; font-size: 1rem; }
    .metric-card {
        background: white; border: 1px solid #dce8f5; border-radius: 10px;
        padding: 1.2rem; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
    .metric-card h3 { color: #1a3a5c; font-size: 1.8rem; margin: 0; }
    .metric-card p  { color: #5a6a7a; margin: 0.3rem 0 0; font-size: 0.85rem; }
    #MainMenu { visibility: hidden; }
    footer    { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ── Helper: Parse UniProt IDs from CSV ───────────────────────
def parse_uniprot_ids_from_csv(uploaded_file) -> tuple:
    """
    Auto-detect and extract UniProt IDs from any CSV format.
    Returns (list_of_ids, detected_column, preview_df)
    """
    import pandas as pd
    import re

    try:
        df = pd.read_csv(uploaded_file)
    except Exception as exc:
        return [], None, None

    # UniProt ID pattern: 1 letter + 1 digit + 3 alphanumeric + 1 digit (6 chars)
    # or extended 10-char format
    uniprot_pattern = re.compile(
        r'^[OPQ][0-9][A-Z0-9]{3}[0-9]$|^[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}$',
        re.IGNORECASE
    )

    # Find which column contains UniProt IDs
    detected_col = None
    best_score = 0

    for col in df.columns:
        col_values = df[col].dropna().astype(str).str.strip()
        matches = col_values.apply(lambda x: bool(uniprot_pattern.match(x)))
        score = matches.sum()
        if score > best_score:
            best_score = score
            detected_col = col

    if not detected_col or best_score == 0:
        # Try to find IDs anywhere in the dataframe
        all_ids = []
        for col in df.columns:
            col_values = df[col].dropna().astype(str).str.strip()
            ids = col_values[col_values.apply(lambda x: bool(uniprot_pattern.match(x)))].tolist()
            all_ids.extend(ids)
        return list(dict.fromkeys(all_ids)), "auto-detected", df

    ids = df[detected_col].dropna().astype(str).str.strip()
    ids = ids[ids.apply(lambda x: bool(uniprot_pattern.match(x)))].tolist()
    ids = list(dict.fromkeys(ids))  # deduplicate

    return ids, detected_col, df


# ── Helper: Run batch and collect results ────────────────────
def run_batch_and_wait(ids: list, progress_bar, status_text) -> list:
    """Submit a batch job and poll until complete. Returns results list."""
    try:
        resp = requests.post(
            f"{API_BASE}/analyze/batch",
            json={"uniprot_ids": ids},
            timeout=30,
        )
        if resp.status_code != 200:
            status_text.error(f"Batch failed: {resp.text[:200]}")
            return []

        batch_data = resp.json()
        batch_id = batch_data["batch_id"]

        max_wait = 900
        elapsed = 0
        poll_interval = 10

        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval

            status_resp = requests.get(f"{API_BASE}/batch/{batch_id}", timeout=10)
            if status_resp.status_code == 200:
                status = status_resp.json()
                if status["status"] == "complete":
                    return status.get("results", [])

        return []

    except Exception as exc:
        status_text.error(f"Batch error: {exc}")
        return []


# ── Render Results Function ───────────────────────────────────
def render_results(data: dict, uniprot_id: str):
    report_id = data.get("report_id", "")
    payload = data.get("data", {})
    protein = payload.get("protein") or {}
    structure = payload.get("structure") or {}
    mutations = payload.get("mutations") or {}
    expression = payload.get("expression") or {}

    st.markdown("---")

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f"""<div class="metric-card"><h3>{protein.get("sequence_length", "N/A")}</h3><p>Amino Acids</p></div>""", unsafe_allow_html=True)
    with m2:
        st.markdown(f"""<div class="metric-card"><h3>{mutations.get("pathogenic_count", 0)}</h3><p>Pathogenic Variants</p></div>""", unsafe_allow_html=True)
    with m3:
        st.markdown(f"""<div class="metric-card"><h3>{structure.get("pdb_count", 0)}</h3><p>PDB Structures</p></div>""", unsafe_allow_html=True)
    with m4:
        papers = payload.get("literature_count", 0)
        st.markdown(f"""<div class="metric-card"><h3>{papers}</h3><p>Papers Retrieved</p></div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if report_id:
        col_dl1, col_dl2 = st.columns([2, 1])
        with col_dl1:
            try:
                pdf_resp = requests.get(f"{API_BASE}/report/{report_id}", timeout=30)
                if pdf_resp.status_code == 200:
                    st.download_button(
                        label="📥 Download PDF Report",
                        data=pdf_resp.content,
                        file_name=f"{uniprot_id}_research_report.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
            except Exception:
                st.warning("PDF download not available")
        with col_dl2:
            try:
                md_resp = requests.get(f"{API_BASE}/report/{report_id}/markdown", timeout=10)
                if md_resp.status_code == 200:
                    md_text = md_resp.json().get("markdown", "")
                    st.download_button(
                        label="📝 Download Markdown",
                        data=md_text,
                        file_name=f"{uniprot_id}_report.md",
                        mime="text/markdown",
                        use_container_width=True,
                    )
            except Exception:
                pass

    st.markdown("---")

    with st.expander("🧬 Protein Overview", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Protein Name:** {protein.get('protein_name', 'N/A')}")
            st.markdown(f"**Gene:** `{protein.get('gene_name', 'N/A')}`")
            st.markdown(f"**Organism:** {protein.get('organism', 'N/A')}")
            st.markdown(f"**UniProt ID:** [{uniprot_id}](https://www.uniprot.org/uniprotkb/{uniprot_id})")
        with c2:
            st.markdown(f"**Sequence Length:** {protein.get('sequence_length', 'N/A')} aa")
            locs = protein.get("subcellular_locations", [])
            st.markdown(f"**Subcellular Location:** {', '.join(locs) if locs else 'N/A'}")
            diseases = protein.get("diseases", [])
            st.markdown(f"**Disease Associations:** {len(diseases)}")
        if protein.get("function_description"):
            st.markdown("**Function:**")
            st.info(protein["function_description"])

    with st.expander("🔬 GO Annotations"):
        go_terms = protein.get("go_annotations", [])
        if go_terms:
            cats = {"biological_process": [], "molecular_function": [], "cellular_component": []}
            for go in go_terms:
                cat = go.get("category", "unknown")
                if cat in cats:
                    cats[cat].append(go)
            for cat_name, terms in cats.items():
                if terms:
                    st.markdown(f"**{cat_name.replace('_', ' ').title()}**")
                    for t in terms[:6]:
                        st.markdown(f"- `{t['term_id']}` {t['term_name']}")
        else:
            st.info("No GO annotations available.")

    with st.expander("🧫 Expression Analysis"):
        expr_summary = expression.get("summary", "")
        if expr_summary:
            st.markdown(expr_summary)
        tissue_expr = expression.get("tissue_expressions", [])
        if tissue_expr:
            import pandas as pd
            st.markdown("**Tissue Expression Levels:**")
            df = pd.DataFrame(tissue_expr).head(15)
            if not df.empty:
                st.dataframe(df, use_container_width=True)

    with st.expander("🧬 Mutation & Variant Analysis"):
        mut_summary = mutations.get("summary", "")
        if mut_summary:
            st.markdown(mut_summary)
        variants = mutations.get("variants", [])
        if variants:
            import pandas as pd
            pathogenic = [v for v in variants if "pathogenic" in (v.get("clinical_significance") or "").lower()][:20]
            if pathogenic:
                st.markdown(f"**Pathogenic Variants ({len(pathogenic)} shown):**")
                df = pd.DataFrame(pathogenic)[["change", "clinical_significance", "condition"]].head(15)
                st.dataframe(df, use_container_width=True)
        else:
            st.info("No variant data available.")

    with st.expander("🏗️ Structural Information"):
        struct_summary = structure.get("summary", "")
        if struct_summary:
            st.markdown(struct_summary)
        c1, c2 = st.columns(2)
        with c1:
            if structure.get("alphafold_available"):
                st.success("✅ AlphaFold structure available")
                af_url = structure.get("alphafold_url")
                if af_url:
                    st.markdown(f"[🔗 View on AlphaFold DB]({af_url})")
            else:
                st.warning("⚠️ No AlphaFold structure")
        with c2:
            pdb_count = structure.get("pdb_count", 0)
            pdb_ids = structure.get("pdb_ids", [])
            if pdb_count:
                st.success(f"✅ {pdb_count} PDB structure(s)")
                for pid in pdb_ids[:5]:
                    st.markdown(f"[`{pid}`](https://www.rcsb.org/structure/{pid})")
            else:
                st.warning("⚠️ No experimental PDB structures")

    def get_report_section(report_id, marker, end_marker):
        try:
            md_resp = requests.get(f"{API_BASE}/report/{report_id}/markdown", timeout=10)
            if md_resp.status_code == 200:
                md = md_resp.json().get("markdown", "")
                if marker in md:
                    start_idx = md.index(marker) + len(marker)
                    end_idx = md.find(end_marker, start_idx)
                    return md[start_idx:end_idx].strip() if end_idx > 0 else md[start_idx:].strip()
        except Exception:
            pass
        return None

    with st.expander("🔗 Protein-Protein Interactions (STRING DB)"):
        section = get_report_section(report_id, "## 9. Protein-Protein Interactions (STRING DB)", "## 10.")
        st.markdown(section) if section else st.info("STRING data not available.")

    with st.expander("🔬 Biological Pathways (Reactome)"):
        section = get_report_section(report_id, "## 10. Biological Pathways (Reactome)", "## 11.")
        st.markdown(section) if section else st.info("Reactome data not available.")

    with st.expander("💊 Drug & Therapeutic Landscape (Open Targets)"):
        section = get_report_section(report_id, "## 11. Drug & Therapeutic Landscape (Open Targets)", "## 12.")
        st.markdown(section) if section else st.info("Open Targets data not available.")

    with st.expander("🔬 Chief Scientist Protein Classification", expanded=True):
        st.markdown("""
        <div style='background: linear-gradient(135deg, #1a3a5c, #2c5f8a);
                    color: white; padding: 0.8rem 1.2rem; border-radius: 8px; margin-bottom: 1rem;'>
            <b>🏆 Expert Classification by Chief Scientist AI</b>
        </div>
        """, unsafe_allow_html=True)
        section = get_report_section(report_id, "## 14. 🔬 Chief Scientist Protein Classification", "## 15.")
        if section:
            lines = section.split("\n")[2:]
            st.markdown("\n".join(lines))
        else:
            st.info("Classification not available.")

    with st.expander("📚 Literature Review"):
        section = get_report_section(report_id, "## 12. Literature Review", "## 13.")
        st.markdown(section) if section else st.info("Literature review not available.")

    with st.expander("📄 Full Markdown Report"):
        section = get_report_section(report_id, "", "")
        try:
            md_resp = requests.get(f"{API_BASE}/report/{report_id}/markdown", timeout=10)
            if md_resp.status_code == 200:
                st.markdown(md_resp.json().get("markdown", ""))
        except Exception:
            st.info("Full report not available.")

    errors = payload.get("errors", {})
    if errors:
        with st.expander("⚠️ Data Collection Notes"):
            for agent, err in errors.items():
                st.warning(f"**{agent}:** {err}")


# ── Header ────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🧬 Agentic Bioinformatics Research Assistant</h1>
    <p>AI-powered multi-agent protein research · UniProt · PubMed · ClinVar · AlphaFold · STRING · Reactome · Open Targets</p>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Configuration")
    st.markdown("---")
    st.markdown("**API Status**")
    api_online = False
    for _url in ["http://127.0.0.1:8000/api/v1/health", "http://localhost:8000/api/v1/health"]:
        try:
            r = requests.get(_url, timeout=5)
            if r.status_code == 200:
                api_online = True
                break
        except Exception:
            pass
    if api_online:
        st.success("✅ API Online")
    else:
        st.warning("⚠️ API status unknown")
        st.caption("If analysis works, API is running fine!")

    st.markdown("---")
    st.markdown("**Example UniProt IDs**")
    examples = {
        "P04637": "TP53 — Tumor Suppressor",
        "P00533": "EGFR — Growth Factor Receptor",
        "Q9Y6K9": "IKBKG — NF-kB Modulator",
        "P35222": "CTNNB1 — Beta-catenin",
        "P15056": "BRAF — Kinase",
    }
    for uid, label in examples.items():
        if st.button(f"🔬 {uid}", help=label, key=f"ex_{uid}"):
            st.session_state["uniprot_input"] = uid

    st.markdown("---")
    st.markdown("**Batch Processing**")
    st.caption("Single: 1 protein | Batch: up to 10 | CSV: up to 100")
    st.markdown("---")
    st.markdown("**About**")
    st.markdown("Autonomously researches proteins using 8 biomedical databases and AI synthesis.")


# ── Tabs ──────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "🔬 Single Protein",
    "📦 Batch Analysis",
    "📂 CSV Upload"
])


# ── Tab 1: Single Analysis ────────────────────────────────────
with tab1:
    col1, col2 = st.columns([3, 1])
    with col1:
        uniprot_id = st.text_input(
            "Enter UniProt Accession ID",
            value=st.session_state.get("uniprot_input", ""),
            placeholder="e.g. P04637",
            help="UniProt accession IDs are 6 alphanumeric characters",
            key="uniprot_input_field",
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        analyze_btn = st.button("🔬 Analyze Protein", type="primary", use_container_width=True)

    if analyze_btn and uniprot_id:
        uniprot_id = uniprot_id.strip().upper()
        st.markdown("---")
        st.markdown(f"### 🔄 Analyzing: `{uniprot_id}`")
        progress_bar = st.progress(0)
        status_text = st.empty()
        steps = [
            (10, "🔗 Fetching protein metadata from UniProt..."),
            (25, "📚 Searching PubMed literature database..."),
            (40, "🧫 Retrieving expression data..."),
            (55, "🧬 Querying ClinVar for pathogenic variants..."),
            (70, "🏗️ Checking AlphaFold and RCSB PDB structures..."),
            (85, "🤖 AI synthesis and report generation..."),
            (95, "📄 Generating PDF report..."),
        ]
        with st.spinner("Running multi-agent research pipeline..."):
            for pct, msg in steps:
                progress_bar.progress(pct)
                status_text.info(msg)
                time.sleep(0.4)
            try:
                response = requests.post(
                    f"{API_BASE}/analyze",
                    json={"uniprot_id": uniprot_id},
                    timeout=600,
                )
                progress_bar.progress(100)
                if response.status_code == 200:
                    status_text.success("✅ Analysis complete!")
                    render_results(response.json(), uniprot_id)
                elif response.status_code == 422:
                    status_text.error(f"❌ {response.json().get('detail', 'Invalid UniProt ID')}")
                else:
                    status_text.error(f"❌ API error {response.status_code}: {response.text[:200]}")
            except requests.exceptions.ConnectionError:
                status_text.error("❌ Cannot connect to API.")
            except requests.exceptions.Timeout:
                status_text.error("❌ Request timed out.")
            except Exception as exc:
                status_text.error(f"❌ Unexpected error: {exc}")


# ── Tab 2: Batch Analysis ─────────────────────────────────────
with tab2:
    st.markdown("### 📦 Batch Protein Analysis")
    st.markdown("Analyze up to **10 proteins** at once.")
    st.info("Enter one UniProt ID per line, or separate with commas.")

    batch_input = st.text_area(
        "Enter UniProt IDs",
        placeholder="P04637\nP00533\nP15056\nQ9Y6K9",
        height=150,
        key="batch_input_area",
    )

    col_b1, col_b2 = st.columns([2, 1])
    with col_b1:
        batch_btn = st.button("🚀 Start Batch Analysis", type="primary", use_container_width=True)
    with col_b2:
        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("⏱️ ~1.5 min per protein")

    # Store batch results in session state so downloads don't clear results
    if "batch_results" not in st.session_state:
        st.session_state.batch_results = []

    if batch_btn and batch_input:
        st.session_state.batch_results = []  # Reset on new run
        raw = batch_input.replace(",", "\n").replace(";", "\n").replace(" ", "\n")
        ids = [x.strip().upper() for x in raw.split("\n") if x.strip()]
        ids = list(dict.fromkeys(ids))

        if len(ids) > 10:
            st.error(f"❌ Maximum 10 proteins per batch. You entered {len(ids)}.")
        elif len(ids) == 0:
            st.error("❌ No valid UniProt IDs found.")
        else:
            st.info(f"🔄 Starting batch for {len(ids)} proteins: {', '.join(ids)}")
            try:
                resp = requests.post(
                    f"{API_BASE}/analyze/batch",
                    json={"uniprot_ids": ids},
                    timeout=30,
                )
                if resp.status_code == 200:
                    batch_data = resp.json()
                    batch_id = batch_data["batch_id"]
                    st.success(f"✅ Batch started! ID: `{batch_id}`")
                    st.info(f"⏱️ Estimated time: {batch_data['estimated_time_minutes']} minutes")

                    if batch_data.get("invalid_ids"):
                        st.warning(f"⚠️ Invalid IDs skipped: {', '.join(batch_data['invalid_ids'])}")

                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    max_wait = 900
                    elapsed = 0

                    while elapsed < max_wait:
                        time.sleep(10)
                        elapsed += 10
                        try:
                            status_resp = requests.get(f"{API_BASE}/batch/{batch_id}", timeout=10)
                            if status_resp.status_code == 200:
                                status = status_resp.json()
                                pct = status.get("progress_percent", 0)
                                completed = status.get("completed", 0)
                                total = status.get("total", len(ids))
                                failed = status.get("failed", 0)
                                progress_bar.progress(min(pct, 100))
                                status_text.info(f"✅ {completed}/{total} complete | ❌ {failed} failed | ⏳ {elapsed}s elapsed")

                                if status["status"] == "complete":
                                    progress_bar.progress(100)
                                    dur = status.get("duration_seconds", 0)
                                    status_text.success(f"🎉 Batch complete! {completed} reports in {dur:.1f}s")
                                    results = status.get("results", [])
                                    if results:
                                        st.markdown("### 📊 Results")
                                        for r in results:
                                            uid = r.get("uniprot_id", "")
                                            if r.get("status") == "success":
                                                report_id = r.get("report_id", "")
                                                protein_name = r.get("protein_name", uid)
                                                gene = r.get("gene_name", "")
                                                summary = r.get("summary", {})
                                                with st.expander(f"✅ {uid} — {protein_name} ({gene})"):
                                                    c1, c2, c3, c4 = st.columns(4)
                                                    c1.metric("Variants", summary.get("variants", 0))
                                                    c2.metric("PDB", summary.get("pdb_structures", 0))
                                                    c3.metric("Papers", summary.get("papers", 0))
                                                    c4.metric("Time", f"{r.get('duration_seconds', 0):.0f}s")
                                                    if report_id:
                                                        try:
                                                            pdf_r = requests.get(f"{API_BASE}/report/{report_id}", timeout=15)
                                                            if pdf_r.status_code == 200:
                                                                st.download_button(
                                                                    f"📥 Download {uid} PDF",
                                                                    data=pdf_r.content,
                                                                    file_name=f"{uid}_report.pdf",
                                                                    mime="application/pdf",
                                                                    key=f"dl_b_{uid}_{report_id}",
                                                                )
                                                        except Exception:
                                                            pass
                                            else:
                                                st.error(f"❌ {uid} failed: {r.get('error', 'Unknown error')}")
                                    # Save to session state
                                        st.session_state.batch_results = results
                                        break
                        except Exception as poll_exc:
                            status_text.warning(f"⚠️ Polling error: {poll_exc}")
                    else:
                        status_text.error("❌ Batch timed out after 15 minutes.")
                else:
                    st.error(f"❌ Batch failed: {resp.json().get('detail', resp.text[:200])}")
            except requests.exceptions.ConnectionError:
                st.error("❌ Cannot connect to API.")
            except Exception as exc:
                st.error(f"❌ Error: {exc}")

    # Always show results from session state (persists across button clicks)
    if st.session_state.get("batch_results"):
        results = st.session_state.batch_results
        st.markdown("### 📊 Batch Results")
        st.info("💡 All download buttons stay available — clicking one won't close others!")
        
        # Collect all PDFs for ZIP download
        pdf_files = {}
        for r in results:
            if r.get("status") == "success":
                report_id = r.get("report_id", "")
                uid = r.get("uniprot_id", "")
                if report_id and uid:
                    try:
                        pdf_r = requests.get(f"{API_BASE}/report/{report_id}", timeout=15)
                        if pdf_r.status_code == 200:
                            pdf_files[f"{uid}_report.pdf"] = pdf_r.content
                    except Exception:
                        pass

        # ZIP download button at top
        if pdf_files:
            import io, zipfile
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for filename, content_bytes in pdf_files.items():
                    zf.writestr(filename, content_bytes)
            zip_buffer.seek(0)
            st.download_button(
                f"📦 Download ALL {len(pdf_files)} Reports as ZIP",
                data=zip_buffer.getvalue(),
                file_name="batch_protein_reports.zip",
                mime="application/zip",
                use_container_width=True,
                key="batch_zip_download",
            )

        st.markdown("---")
        for r in results:
            uid = r.get("uniprot_id", "")
            if r.get("status") == "success":
                report_id = r.get("report_id", "")
                protein_name = r.get("protein_name", uid)
                gene = r.get("gene_name", "")
                summary = r.get("summary", {})
                with st.expander(f"✅ {uid} — {protein_name} ({gene})", expanded=True):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Variants", summary.get("variants", 0))
                    c2.metric("PDB", summary.get("pdb_structures", 0))
                    c3.metric("Papers", summary.get("papers", 0))
                    c4.metric("Time", f"{r.get('duration_seconds', 0):.0f}s")
                    fname = f"{uid}_report.pdf"
                    if fname in pdf_files:
                        st.download_button(
                            f"📥 Download {uid} PDF Report",
                            data=pdf_files[fname],
                            file_name=fname,
                            mime="application/pdf",
                            key=f"dl_persist_{uid}_{report_id}",
                            use_container_width=True,
                        )
            else:
                st.error(f"❌ {uid} failed: {r.get('error', 'Unknown error')}")


# ── Tab 3: CSV Upload ─────────────────────────────────────────
with tab3:
    st.markdown("### 📂 CSV Bulk Upload Analysis")
    st.markdown("Upload a CSV file containing UniProt IDs — up to **100 proteins**.")

    # Sample CSV download
    sample_csv = "uniprot_id,gene_name,description\nP04637,TP53,Tumor suppressor\nP00533,EGFR,Growth factor receptor\nP15056,BRAF,Kinase\nQ9Y6K9,IKBKG,NF-kB modulator\n"
    st.download_button(
        "📥 Download Sample CSV Template",
        data=sample_csv,
        file_name="sample_uniprot_ids.csv",
        mime="text/csv",
        help="Download a sample CSV to see the expected format",
    )

    st.markdown("---")

    uploaded_file = st.file_uploader(
        "Upload CSV file",
        type=["csv"],
        help="CSV can have any columns — the system auto-detects the UniProt ID column",
    )

    if uploaded_file:
        ids, detected_col, preview_df = parse_uniprot_ids_from_csv(uploaded_file)

        if not ids:
            st.error("❌ No UniProt IDs detected in this CSV. Make sure your file contains valid UniProt accession IDs (e.g. P04637).")
        else:
            st.success(f"✅ Detected **{len(ids)} UniProt IDs** from column: `{detected_col}`")

            # Preview
            col_p1, col_p2 = st.columns([2, 1])
            with col_p1:
                if preview_df is not None:
                    st.markdown("**File Preview (first 5 rows):**")
                    st.dataframe(preview_df.head(5), use_container_width=True)
            with col_p2:
                st.markdown("**Detected IDs (first 10):**")
                for uid in ids[:10]:
                    st.code(uid)
                if len(ids) > 10:
                    st.caption(f"... and {len(ids) - 10} more")

            # Limit check
            if len(ids) > 100:
                st.warning(f"⚠️ CSV contains {len(ids)} IDs. Only the first 100 will be processed.")
                ids = ids[:100]

            # Time estimate
            n_batches = (len(ids) + 9) // 10
            est_minutes = round(len(ids) * 1.5)
            est_hours = round(est_minutes / 60, 1)

            st.info(f"📊 **{len(ids)} proteins** → **{n_batches} batches of 10** → Estimated time: **{est_minutes} min ({est_hours} hrs)**")

            if len(ids) > 30:
                st.warning("⏰ This is a large run. Keep this browser tab open or the run will stop. For overnight runs, the reports are saved to your `reports/` folder automatically.")

            col_r1, col_r2 = st.columns([2, 1])
            with col_r1:
                run_csv_btn = st.button(
                    f"🚀 Start Analysis ({len(ids)} proteins)",
                    type="primary",
                    use_container_width=True,
                )
            with col_r2:
                st.markdown("<br>", unsafe_allow_html=True)
                st.caption(f"~{est_minutes} min total")

            if run_csv_btn:
                st.markdown("---")
                st.markdown(f"### 🔄 Processing {len(ids)} proteins in {n_batches} batches")

                overall_progress = st.progress(0)
                overall_status = st.empty()
                all_results = []
                total_completed = 0
                total_failed = 0

                # Process in batches of 10
                for batch_num in range(n_batches):
                    batch_start = batch_num * 10
                    batch_end = min(batch_start + 10, len(ids))
                    batch_ids = ids[batch_start:batch_end]

                    overall_status.info(f"🔄 Batch {batch_num + 1}/{n_batches}: Processing {', '.join(batch_ids)}")

                    batch_progress = st.progress(0)
                    batch_status = st.empty()

                    try:
                        resp = requests.post(
                            f"{API_BASE}/analyze/batch",
                            json={"uniprot_ids": batch_ids},
                            timeout=30,
                        )

                        if resp.status_code == 200:
                            batch_data = resp.json()
                            batch_id = batch_data["batch_id"]
                            max_wait = 900
                            elapsed = 0

                            while elapsed < max_wait:
                                time.sleep(10)
                                elapsed += 10
                                try:
                                    status_resp = requests.get(f"{API_BASE}/batch/{batch_id}", timeout=10)
                                    if status_resp.status_code == 200:
                                        status = status_resp.json()
                                        pct = status.get("progress_percent", 0)
                                        completed = status.get("completed", 0)
                                        batchTotal = status.get("total", len(batch_ids))
                                        batch_progress.progress(min(pct, 100))
                                        batch_status.info(f"  ✅ {completed}/{batchTotal} in this batch")

                                        if status["status"] == "complete":
                                            batch_results = status.get("results", [])
                                            all_results.extend(batch_results)
                                            total_completed += status.get("completed", 0)
                                            total_failed += status.get("failed", 0)
                                            batch_status.success(f"  ✅ Batch {batch_num + 1} complete!")
                                            break
                                except Exception:
                                    pass
                    except Exception as exc:
                        batch_status.error(f"  ❌ Batch {batch_num + 1} failed: {exc}")
                        total_failed += len(batch_ids)

                    # Update overall progress
                    overall_pct = int(((batch_num + 1) / n_batches) * 100)
                    overall_progress.progress(overall_pct)

                # All batches done!
                overall_progress.progress(100)
                overall_status.success(f"🎉 All done! {total_completed} reports generated, {total_failed} failed.")

                st.markdown("---")
                st.markdown(f"### 📊 Results Summary — {total_completed} Proteins Analyzed")

                # Build summary table
                import pandas as pd
                summary_rows = []
                pdf_files = {}

                for r in all_results:
                    uid = r.get("uniprot_id", "")
                    if r.get("status") == "success":
                        summary = r.get("summary", {})
                        summary_rows.append({
                            "UniProt ID": uid,
                            "Protein Name": r.get("protein_name", "N/A"),
                            "Gene": r.get("gene_name", "N/A"),
                            "Pathogenic Variants": summary.get("variants", 0),
                            "PDB Structures": summary.get("pdb_structures", 0),
                            "Papers": summary.get("papers", 0),
                            "Status": "✅ Success",
                            "Report ID": r.get("report_id", ""),
                        })
                        # Collect PDF
                        report_id = r.get("report_id", "")
                        if report_id:
                            try:
                                pdf_r = requests.get(f"{API_BASE}/report/{report_id}", timeout=15)
                                if pdf_r.status_code == 200:
                                    pdf_files[f"{uid}_report.pdf"] = pdf_r.content
                            except Exception:
                                pass
                    else:
                        summary_rows.append({
                            "UniProt ID": uid,
                            "Protein Name": "FAILED",
                            "Gene": "N/A",
                            "Pathogenic Variants": 0,
                            "PDB Structures": 0,
                            "Papers": 0,
                            "Status": "❌ Failed",
                            "Report ID": "",
                        })

                if summary_rows:
                    summary_df = pd.DataFrame(summary_rows)
                    display_df = summary_df.drop(columns=["Report ID"])
                    st.dataframe(display_df, use_container_width=True)

                    # Download summary as Excel
                    excel_buffer = io.BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                        display_df.to_excel(writer, index=False, sheet_name="Protein Analysis Summary")
                    excel_buffer.seek(0)

                    col_d1, col_d2 = st.columns(2)
                    with col_d1:
                        st.download_button(
                            "📊 Download Summary Excel",
                            data=excel_buffer.getvalue(),
                            file_name="protein_analysis_summary.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True,
                        )

                    with col_d2:
                        # Create ZIP of all PDFs
                        if pdf_files:
                            zip_buffer = io.BytesIO()
                            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                                for filename, content in pdf_files.items():
                                    zf.writestr(filename, content)
                            zip_buffer.seek(0)
                            st.download_button(
                                f"📦 Download All PDFs ({len(pdf_files)} reports)",
                                data=zip_buffer.getvalue(),
                                file_name="protein_reports.zip",
                                mime="application/zip",
                                use_container_width=True,
                            )

                    # Individual downloads
                    st.markdown("### 📥 Individual Report Downloads")
                    for r in all_results:
                        uid = r.get("uniprot_id", "")
                        if r.get("status") == "success":
                            report_id = r.get("report_id", "")
                            protein_name = r.get("protein_name", uid)
                            gene = r.get("gene_name", "")
                            summary = r.get("summary", {})
                            with st.expander(f"✅ {uid} — {protein_name} ({gene})"):
                                c1, c2, c3 = st.columns(3)
                                c1.metric("Variants", summary.get("variants", 0))
                                c2.metric("PDB", summary.get("pdb_structures", 0))
                                c3.metric("Papers", summary.get("papers", 0))
                                fname = f"{uid}_report.pdf"
                                if fname in pdf_files:
                                    st.download_button(
                                        f"📥 {uid} PDF",
                                        data=pdf_files[fname],
                                        file_name=fname,
                                        mime="application/pdf",
                                        key=f"dl_csv_{uid}_{report_id}",
                                    )
                        else:
                            st.error(f"❌ {uid}: {r.get('error', 'Unknown error')}")