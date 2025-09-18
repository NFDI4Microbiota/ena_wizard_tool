# modules/about.py
import io
import pandas as pd
import streamlit as st
from utils.css_injection import inject_css

# =========================
# Configuráveis
# =========================
CONTACT_EMAIL = "you@example.org"
CONTACT_SLACK = "Slack: #ena-submission"
CONTACT_SITE  = "https://www.ebi.ac.uk/ena/browser/submit"
ORG_NAME      = "NFDI / Your Lab"
APP_NAME      = "NFDI ENA Submission Tool"
SUPPORTED_SCOPE = "Terrestrial package (MIXS)"
LICENSE       = "Apache-2.0 (example — adjust if needed)"

# =========================
# Pequeno CSS extra só pra garantir fluidez,
# respeitando seu style.css (classes de container/card/etc.)
# =========================
EXTRA_CSS = """
<style>
/* espaçamentos mais generosos e tipografia consistente */
.container-max { max-width: 1100px; margin: 0 auto; }
.section { margin: 2.2rem 0; }
.lead { font-size: 1.05rem; line-height: 1.6; }
.muted { color: #6b7280; }
.h2 { font-size: 1.6rem; font-weight: 700; margin-bottom: .75rem; }
.h3 { font-size: 1.15rem; font-weight: 700; margin: 1rem 0 .25rem; }
.badge { display:inline-block; padding:.25rem .6rem; border-radius:999px; background:#eef2ff; color:#3730a3; font-weight:600; font-size:.85rem }

/* hero mais fluido */
.hero {
  padding: 2.2rem 1.2rem;
  text-align: center;
  background: radial-gradient(1000px 600px at 50% -10%, #f5f7ff 0%, transparent 60%);
  border-radius: 18px;
}
.hero-small { padding: 1.8rem 1rem; }
.hero-title { font-size: 2.05rem; font-weight: 800; margin-bottom: .35rem; }
.hero-sub { font-size: 1.05rem; color: #4b5563; margin: 0 auto .5rem; max-width: 820px; }

/* grids responsivos */
.grid-2, .grid-3 {
  display: grid;
  gap: 1rem;
}
.grid-2 { grid-template-columns: repeat(2, minmax(0,1fr)); }
.grid-3 { grid-template-columns: repeat(3, minmax(0,1fr)); }
@media (max-width: 900px) {
  .grid-3 { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 640px) {
  .grid-2, .grid-3 { grid-template-columns: 1fr; }
}

/* cartões */
.card {
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  padding: 1rem 1rem;
  background: #fff;
  box-shadow: 0 1px 0 rgba(0,0,0,.02);
}
.card h4 { margin: 0 0 .35rem; font-size: 1.05rem; }
.card .muted { font-size: .95rem; }

/* listas mais compactas */
ul.list, ol.list { padding-left: 1.1rem; margin: .25rem 0; }
ul.list li, ol.list li { margin: .25rem 0; }

/* callout “note” */
.note {
  border-left: 4px solid #93c5fd;
  background: #f0f7ff;
  padding: .6rem .8rem;
  border-radius: 8px;
}

/* blocos de contato e créditos */
.footer-card {
  border: 1px dashed #d1d5db;
  background: #fafafa;
  border-radius: 14px;
  padding: 1rem 1rem;
}
</style>
"""

# =========================
# Sample CSV (permanece o mesmo)
# =========================
def _sample_csv() -> pd.DataFrame:
    rows = [
        {
            "project_name": "Forest soil metagenome",
            "collection_date": "2024-05-18",
            "geo_loc_name": "Germany: Saxony",
            "lat": 51.0504,
            "lon": 13.7373,
            "env_broad_scale": "ENVO:00000446",
            "env_local_scale": "ENVO:01000175",
            "env_medium": "ENVO:00005742",
            "samp_name": "SoilPlot_A1",
            "samp_taxon_id": "749906",
            "experiment": "shotgun",
            "organism": "metagenome",
            "tax_id": "256318",
            "ENA_CHECKLIST": "",
        },
        {
            "project_name": "Forest soil metagenome",
            "collection_date": "2024-05-18",
            "geo_loc_name": "Germany: Saxony",
            "lat": 51.0501,
            "lon": 13.7399,
            "env_broad_scale": "ENVO:00000446",
            "env_local_scale": "ENVO:01000175",
            "env_medium": "ENVO:00005742",
            "samp_name": "SoilPlot_A2",
            "samp_taxon_id": "749906",
            "experiment": "shotgun",
            "organism": "metagenome",
            "tax_id": "256318",
            "ENA_CHECKLIST": "",
        },
    ]
    return pd.DataFrame(rows)


def runUI():
    inject_css()
    st.markdown(EXTRA_CSS, unsafe_allow_html=True)

    # ===== Hero =====
    st.markdown(
        f"""
        <div class="container-max">
          <section class="hero hero-small">
            <div class="hero-title">About & Help</div>
            <div class="hero-sub">
              Everything you need to work efficiently with the <b>{APP_NAME}</b>.
              <span class="badge" style="margin-left:.5rem;">{SUPPORTED_SCOPE}</span>
            </div>
          </section>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    # ===== Overview =====
    st.markdown(
        f"""
        <div class="container-max section">
          <div class="h2">ℹ️ Overview</div>
          <p class="lead">
            The <b>{APP_NAME}</b> helps you create and validate metadata for submissions to the
            European Nucleotide Archive (ENA), following MIXS standards. Start from a clean
            template or upload CSV/Excel; the app checks required fields, formats (regex),
            and simple ontology shapes (ENVO/CHEBI/NCBI Taxonomy), then lets you download a clean CSV.
          </p>
          <div class="grid-3">
            <div class="card">
              <h4>Focus</h4>
              <p class="muted">Reduce formatting friction and catch errors early.</p>
            </div>
            <div class="card">
              <h4>Scope</h4>
              <p class="muted">{SUPPORTED_SCOPE}</p>
            </div>
            <div class="card">
              <h4>Future</h4>
              <p class="muted">Automated ENA API submissions and job tracking.</p>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ===== Who is it for + File formats (lado a lado) =====
    st.markdown('<div class="container-max section">', unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown(
            """
            <div class="h2">🎯 Who is this for?</div>
            <ul class="list">
              <li>Researchers preparing environmental/terrestrial metadata aligned with MIXS.</li>
              <li>Lab managers curating datasets before ENA submission.</li>
              <li>Data stewards supporting teams with standard-compliant metadata.</li>
            </ul>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            """
            <div class="h2">📄 File formats & schema</div>
            <ul class="list">
              <li><b>Upload:</b> CSV (.csv) or Excel (.xlsx); UTF-8 for CSV.</li>
              <li><b>Header row:</b> must contain column names; unknown columns are ignored.</li>
              <li><b>Dates:</b> ISO 8601 (<code>YYYY-MM-DD</code> or full timestamp).</li>
              <li><b>Coordinates:</b> lat/lon in decimal degrees (WGS84); commas auto-normalized.</li>
              <li><b>Ontologies:</b> shape checks like <code>ENVO:00000446</code>, <code>CHEBI:2509</code>, TaxIDs.</li>
            </ul>
            """,
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)

    # ===== Validation rules =====
    st.markdown(
        """
        <div class="container-max section">
          <div class="h2">✅ Validation rules</div>
          <div class="grid-3">
            <div class="card">
              <h4>Required fields</h4>
              <ul class="list">
                <li>Marked with an asterisk (*) in the editor.</li>
                <li>Empty values are flagged per row.</li>
                <li>Missing required <i>columns</i> are also reported.</li>
              </ul>
            </div>
            <div class="card">
              <h4>Regex & data types</h4>
              <ul class="list">
                <li>Per-field pattern (e.g., ISO date).</li>
                <li>Number/date columns coerced and validated.</li>
                <li>Custom messages for mismatches.</li>
              </ul>
            </div>
            <div class="card">
              <h4>Semantic shapes</h4>
              <ul class="list">
                <li>ENVO: <code>ENVO:0000000</code> (7 digits).</li>
                <li>CHEBI: <code>CHEBI:12345</code> (optional <code>;timestamp</code>).</li>
                <li>TaxIDs: digits only (1–9 digits).</li>
              </ul>
            </div>
          </div>
          <div class="note muted" style="margin-top:.6rem;">
            Note: We validate ID <i>shapes</i>, not remote term existence.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ===== Common errors (expander) =====
    with st.expander("🚑 Common errors & quick fixes", expanded=True):
        st.markdown(
            """
            - **Dates not in ISO 8601** → Use `YYYY-MM-DD` (e.g., `2024-05-18`).  
            - **Lat/Lon with comma** → Use “Auto-fix common issues” to normalize commas to dots.  
            - **Empty required fields** → Fill all starred columns.  
            - **Duplicate project name** → Project key must be unique when used as identifier.  
            - **Ontology shape mismatch** → Patterns like `ENVO:00000446`, `CHEBI:2509`.  
            - **Trailing blank row** → The editor keeps one empty row; it’s removed on export.
            """
        )

    # ===== Getting started (2 colunas: passos + sample) =====
    st.markdown('<div class="container-max section">', unsafe_allow_html=True)
    g1, g2 = st.columns([1.2, 1], gap="large")
    with g1:
        st.markdown(
            """
            <div class="h2">🚀 Getting started</div>
            <ol class="list">
              <li>Open <b>Create & Validate Metadata</b>.</li>
              <li><b>Upload</b> your CSV/Excel or click <b>Start new</b> for an empty template.</li>
              <li>Use the toolbar to add rows or select & delete.</li>
              <li>Fix red-flagged cells; check “⚠︎ issues” and the Validation panel.</li>
              <li>When issues = 0, <b>Download CSV</b>.</li>
            </ol>
            """,
            unsafe_allow_html=True,
        )
    with g2:
        st.markdown('<div class="h3">📥 Sample CSV</div>', unsafe_allow_html=True)
        sample_df = _sample_csv()
        buf = io.StringIO(); sample_df.to_csv(buf, index=False)
        st.download_button(
            "Download sample_metadata.csv",
            buf.getvalue().encode("utf-8"),
            file_name="sample_metadata.csv",
            mime="text/csv",
            use_container_width=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)

    # ===== FAQ =====
    st.markdown('<div class="container-max section"><div class="h2">❓ FAQ</div></div>', unsafe_allow_html=True)
    with st.expander("Why does the table always show an empty row at the bottom?"):
        st.write("It’s a convenience row for quick data entry. It is excluded when you download the CSV.")
    with st.expander("Do I need to include all MIXS fields?"):
        st.write("No. Only the required set is enforced; optional fields are allowed and validated if present.")
    with st.expander("Can I upload Excel files with multiple sheets?"):
        st.write("Currently the first sheet is read. Save/export the sheet you need, or use CSV.")
    with st.expander("Does the app validate that ENVO/CHEBI IDs actually exist?"):
        st.write("It validates the ID shape only. Full ontology resolution is out of scope for now.")
    with st.expander("What about ENA checklists?"):
        st.write("The column is supported for future API-based submission flows. Values are not enforced here.")

    # ===== Roadmap + Privacy (lado a lado) =====
    st.markdown('<div class="container-max section">', unsafe_allow_html=True)
    r1, r2 = st.columns(2, gap="large")
    with r1:
        st.markdown(
            """
            <div class="h2">🗺️ Roadmap</div>
            <ul class="list">
              <li>More MIXS packages (host-associated, built environment).</li>
              <li>Checklist-aware export (ENA XML generation).</li>
              <li>Direct ENA API submissions & job monitoring.</li>
              <li>UI refinements and accessibility improvements.</li>
            </ul>
            """,
            unsafe_allow_html=True,
        )
    with r2:
        st.markdown(
            """
            <div class="h2">🔐 Privacy & Data Handling</div>
            <p class="muted">
              Files you upload are used only for validation in your session.
              Avoid sensitive content in examples and shared exports.
            </p>
            """,
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)

    # ===== Contact (cartão) =====
    st.markdown(
        f"""
        <div class="container-max section">
          <div class="h2">📬 Contact & Support</div>
          <div class="footer-card">
            <ul class="list">
              <li>Email: <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a></li>
              <li>{CONTACT_SLACK}</li>
              <li>ENA portal: <a href="{CONTACT_SITE}" target="_blank">{CONTACT_SITE}</a></li>
            </ul>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ===== Credits & Citation (inclui seus créditos) =====
    st.markdown(
        f"""
        <div class="container-max section">
          <div class="h2">🎓 Credits & Citation</div>
          <p class="muted">
            If you use this tool in a publication, please cite <b>{ORG_NAME}</b> and the
            <b>{APP_NAME}</b>. Also cite MIXS and ENA where appropriate.
          </p>
          <p class="muted">
            <b>Making Microbiology Data FAIR and Open</b><br>
            As a part of the Nationale Forschungsdaten Infrastruktur (NFDI),
            <b>NFDI4Microbiota</b> supports the microbiology community with access to data,
            analysis services, data/metadata standards, and training.
          </p>
          <p class="muted">
            <b>Microbial Data Science Group — UFZ (Germany)</b><br>
            Research and development contributions from the Microbial Data Science Group at the
            Helmholtz Centre for Environmental Research (UFZ), Leipzig.
          </p>
          <div class="h3">License</div>
          <p class="muted">{LICENSE} — update if your project uses a different license.</p>
          <div class="h3">Changelog</div>
          <ul class="list">
            <li>v0.1: Initial terrestrial metadata validation, CSV/Excel upload, clean export.</li>
          </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

if __name__ == "__main__":
    runUI()
