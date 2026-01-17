# modules/home.py
import base64
import pandas as pd
import streamlit as st
from utils.css_injection import inject_css

def _load_logo_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def _build_csv_template() -> pd.DataFrame:
    cols = [
        "project_name","collection_date","geo_loc_name","lat","lon","elev","alt","depth",
        "env_broad_scale","env_local_scale","env_medium","chem_administration","temp","salinity","pH",
        "samp_name","source_mat_id","samp_size","ph","samp_taxon_id","samp_collect_method",
        "microbial_isolate","microb_cult_med",
        "host_taxid","host_common_name","host_height","host_length","host_tot_mass",
        "host_body_site","host_body_product","host_age","host_sex","host_diet","host_disease_stat",
        "experiment","organism","tax_id","metagenomic_source","sample_derived_from","project_name_alias",
        "completeness_score","contamination_score","completeness_software","binning_software",
        "assembly_quality","binning_parameters","taxonomic_identity_marker","isolation_source",
        "assembly_software","genome_coverage","platform","ENA_CHECKLIST"
    ]
    return pd.DataFrame([{c: "" for c in cols}])

def runUI():
    inject_css()

    # Hero
    logo_b64 = _load_logo_b64("imgs/logo.png")
    st.markdown(
        f"""
        <div class="container-max">
          <section class="hero">
            <img src="data:image/png;base64,{logo_b64}" alt="logo" width="110" />
            <div class="hero-title">NFDI ENA Submission Tool</div>
            <div class="hero-sub">Validate metadata and prepare metagenome-assembled genome (MAG) submissions.</div>
            <div class="badge">Genomic Standards Consortium package for MAGs (MIMAGS) supported.</div>
          </section>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    # Features (cards)
    st.markdown(
        """
        <div class="container-max section">
          <div class="h2">✨ Features</div>
          <div class="cards-3">
            <div class="card">
              <h4>Metadata validation</h4>
              <ul class="list">
                <li>ISO 8601 date checks</li>
                <li>Expected values and units</li>
                <li>Ontologies: ENVO, CHEBI, NCBI Taxonomy</li>
              </ul>
            </div>
            <div class="card">
              <h4>Create or upload</h4>
              <ul class="list">
                <li>Start from a clean template</li>
                <li>Or upload CSV/Excel</li>
                <li>Edit inline and re-validate instantly</li>
              </ul>
            </div>
            <div class="card">
              <h4>Submission-ready</h4>
              <ul class="list">
                <li>Download a clean, validated CSV</li>
                <li>MIXS/ENA-aligned fields</li>
                <li>Future: ENA API integration</li>
              </ul>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    # Workflow (steps)
    st.markdown(
        """
        <div class="container-max section">
          <div class="h2">🔄 Workflow</div>
          <div class="timeline">
            <div class="step"><b>Prepare</b> your metadata (or start from our template).</div>
            <div class="step"><b>Open the editor</b>: create rows or upload CSV/Excel.</div>
            <div class="step"><b>Fix issues</b> flagged by the validator (required fields, formats, ontologies).</div>
            <div class="step"><b>Download</b> a clean CSV ready for ENA submission.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    # Template download
    st.markdown('<div class="container-max section"><div class="h3 pad-top">⬇️ Download template</div></div>', unsafe_allow_html=True)
    csv_bytes = _build_csv_template().to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download metadata_template.csv",
        data=csv_bytes,
        file_name="metadata_template.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.divider()

    # CTA
    st.markdown('<div class="container-max section"><div class="h2">✅ Ready to validate & submit?</div></div>', unsafe_allow_html=True)
    try:
        st.page_link("pages/1_Validate_and_Submit.py", label="Go to Validate & Submit", icon="✅")
    except Exception:
        st.markdown("> Use the left menu to open **Create & Validate Metadata**.")

    st.divider()
    st.markdown(
        """
        **References**  
        - [MIXS Standard - GSC](https://www.nature.com/articles/nbt1366)  
        - [MIXS Term Browser](https://w3id.org/mixs/)  
        - [ENA Submission Portal](https://www.ebi.ac.uk/ena/browser/submit)
        """
    )

if __name__ == "__main__":
    runUI()
