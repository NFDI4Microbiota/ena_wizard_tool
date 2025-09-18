# home.py
import io
import base64
import pandas as pd
import streamlit as st

from utils.css_injection import inject_css

# ========= Helpers =========
def _load_logo_b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def _build_required_columns_df() -> pd.DataFrame:
    # Preview das principais colunas obrigatórias/centrais (você pode expandir aqui depois)
    rows = [
        ("Project metadata", "project_name", "Name of the project", "Free text", "Forest soil metagenome"),
        ("Site metadata", "collection_date", "Sampling time (ISO 8601)", "YYYY-MM-DD or ISO 8601", "2013-03-25T12:42:31+01:00"),
        ("Site metadata", "geo_loc_name", "Country/sea and region (INSDC/GAZ)", "Free text or ontology", "USA: Maryland, Bethesda"),
        ("Site metadata", "lat", "Latitude (WGS84)", "Decimal degrees", "-41.373744"),
        ("Site metadata", "lon", "Longitude (WGS84)", "Decimal degrees", "146.266145"),
        ("Site metadata", "env_broad_scale", "Biome (EnvO)", "Ontology terms", "terrestrial biome [ENVO:00000446]"),
        ("Site metadata", "env_local_scale", "Local env entity (EnvO)", "Ontology terms", "woodland biome [ENVO:01000175]"),
        ("Site metadata", "env_medium", "Material in contact (EnvO)", "Ontology terms", "arable soil [ENVO:00005742]"),
        ("Sample metadata", "samp_name", "Local sample identifier", "Free text (unique per submitter)", "Soil1Sample2Seq2"),
        ("Sample metadata", "samp_taxon_id", "NCBI taxon ID of sample/control", "NCBI Taxonomy ID", "749906"),
    ]
    return pd.DataFrame(rows, columns=["Category", "Field", "Definition", "Expected Value / Unit", "Example"])

def _build_csv_template() -> pd.DataFrame:
    # Template inicial com colunas comuns (alinhei com suas colunas da versão antiga e MIXS centrais)
    cols = [
        # Projeto / Site
        "project_name","collection_date","geo_loc_name","lat","lon","elev","alt","depth",
        "env_broad_scale","env_local_scale","env_medium","chem_administration","temp","salinity","pH",
        # Sample
        "samp_name","source_mat_id","samp_size","ph","samp_taxon_id","samp_collect_method",
        "microbial_isolate","microb_cult_med",
        # Host (quando aplicável)
        "host_taxid","host_common_name","host_height","host_length","host_tot_mass",
        "host_body_site","host_body_product","host_age","host_sex","host_diet","host_disease_stat",
        # Técnicos/ENA usuais (você já tinha algo assim na home antiga)
        "experiment","organism","tax_id","metagenomic_source","sample_derived_from","project_name_alias",
        "completeness_score","contamination_score","completeness_software","binning_software",
        "assembly_quality","binning_parameters","taxonomic_identity_marker","isolation_source",
        "assembly_software","genome_coverage","platform","ENA_CHECKLIST"
    ]
    # Linha vazia
    return pd.DataFrame([{c: "" for c in cols}])

# ========= UI =========
def runUI():
    inject_css()  # mantém seu estilo / background na sidebar

    # Hero
    logo_b64 = _load_logo_b64("imgs/logo.png")
    st.markdown(
        f"""
        <div style='text-align:center;'>
          <img src="data:image/png;base64,{logo_b64}" alt="logo" width="200" />
          <h1>ENA Automatic Submission System</h1>
          <h4 style="color:gray;">Automating Metadata Validation & Submission to ENA</h4>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    # Intro
    st.markdown(
        """
        This system aims to **automate the validation and submission of metadata and sequencing data**
        to the **European Nucleotide Archive (ENA)**, following the metadata standards defined by the **MIXS specification**.
        """
    )
    st.info("Initial version: supports **Terrestrial metadata** only.")

    # Features (3 colunas)
    st.subheader("✨ Features")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            "- **Metadata validation**\n"
            "  - ISO 8601 dates\n"
            "  - Expected value & unit checks\n"
            "  - Controlled vocabularies & ontologies (ENVO, CHEBI, NCBI Taxonomy)"
        )
    with c2:
        st.markdown(
            "- **Automated submission**\n"
            "  - Upload of metadata & sequencing data files\n"
            "  - ENA submission API *(planned for future phases)*"
        )
    with c3:
        st.markdown(
            "- **Initial Scope**\n"
            "  - **Terrestrial metadata** package (MIXS)"
        )

    st.divider()

    # Workflow
    st.subheader("🔄 Workflow")
    st.markdown(
        "1. **Prepare metadata** (CSV/Excel)\n"
        "2. **Validate automatically** in the system\n"
        "3. **Upload sequencing data**\n"
        "4. **Future**: full ENA submission automation"
    )

    # Preview das colunas obrigatórias/centrais
    st.subheader("📋 Core Required Fields (Preview)")
    preview_df = _build_required_columns_df()
    st.dataframe(preview_df, use_container_width=True, hide_index=True)

    # Download de template CSV
    st.markdown("#### Download a CSV template")
    template_df = _build_csv_template()
    csv_bytes = template_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download metadata_template.csv",
        data=csv_bytes,
        file_name="metadata_template.csv",
        mime="text/csv",
        help="CSV template with common MIXS-aligned fields",
    )

    st.divider()

    # CTA para a página de validação & submissão
    st.subheader("✅ Ready to validate & submit?")
    # Se você usa multipage (pages/...), o Streamlit 1.31+ tem page_link:
    try:
        st.page_link("pages/1_Validate_and_Submit.py", label="Go to Validate & Submit", icon="✅")
    except Exception:
        st.markdown(
            "> Use the left menu to open **Validate & Submit** page.",
            help="If the link above doesn't work in your Streamlit version, use the sidebar navigation."
        )

    # Referências
    st.divider()
    st.markdown(
        "**References**  \n"
        "- [MIXS Standard - GSC](https://www.nature.com/articles/nbt1366)  \n"
        "- [MIXS Term Browser](https://w3id.org/mixs/)  \n"
        "- [ENA Submission Portal](https://www.ebi.ac.uk/ena/browser/submit)"
    )

if __name__ == "__main__":
    runUI()
