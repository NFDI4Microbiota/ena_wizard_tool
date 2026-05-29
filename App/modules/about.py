# modules/about.py
import streamlit as st
from utils.css_injection import inject_css

# =========================
# Configuráveis
# =========================
CONTACT_EMAIL = "ulisses.rocha@ufz.de"
CONTACT_SITE  = "https://www.ebi.ac.uk/ena/browser/submit"
ORG_NAME      = "NFDI4Microbiota / Microbial Data Science Group — UFZ"
APP_NAME      = "NFDI MAG2ENA"
SUPPORTED_SCOPE = "MAGs · MIMAGS · ERC000047"
LICENSE       = "MIT"

EXTRA_CSS = """
<style>
.container-max { max-width: 1100px; margin: 0 auto; }
.section { margin: 2.2rem 0; }
.lead { font-size: 1.05rem; line-height: 1.6; }
.muted { color: #6b7280; }
.h2 { font-size: 1.6rem; font-weight: 700; margin-bottom: .75rem; }
.h3 { font-size: 1.15rem; font-weight: 700; margin: 1rem 0 .25rem; }
.badge { display:inline-block; padding:.25rem .6rem; border-radius:999px; background:#eef2ff; color:#3730a3; font-weight:600; font-size:.85rem }
.hero {
  padding: 2.2rem 1.2rem;
  text-align: center;
  background: radial-gradient(1000px 600px at 50% -10%, #f5f7ff 0%, transparent 60%);
  border-radius: 18px;
}
.hero-small { padding: 1.8rem 1rem; }
.hero-title { font-size: 2.05rem; font-weight: 800; margin-bottom: .35rem; }
.hero-sub { font-size: 1.05rem; color: #4b5563; margin: 0 auto .5rem; max-width: 820px; }
.grid-2, .grid-3 { display: grid; gap: 1rem; }
.grid-2 { grid-template-columns: repeat(2, minmax(0,1fr)); }
.grid-3 { grid-template-columns: repeat(3, minmax(0,1fr)); }
@media (max-width: 900px) { .grid-3 { grid-template-columns: 1fr 1fr; } }
@media (max-width: 640px) { .grid-2, .grid-3 { grid-template-columns: 1fr; } }
.card { border: 1px solid #e5e7eb; border-radius: 14px; padding: 1rem 1rem; background: #fff; box-shadow: 0 1px 0 rgba(0,0,0,.02); }
.card h4 { margin: 0 0 .35rem; font-size: 1.05rem; }
.card .muted { font-size: .95rem; }
ul.list, ol.list { padding-left: 1.1rem; margin: .25rem 0; }
ul.list li, ol.list li { margin: .25rem 0; }
.note { border-left: 4px solid #93c5fd; background: #f0f7ff; padding: .6rem .8rem; border-radius: 8px; }
.footer-card { border: 1px dashed #d1d5db; background: #fafafa; border-radius: 14px; padding: 1rem 1rem; }
</style>
"""


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
              Everything you need to know about the <b>{APP_NAME}</b>.
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
        """
        <div class="container-max section">
          <div class="h2">ℹ️ Overview</div>
          <p class="lead">
            The NFDI MAG2ENA is an end-to-end submission pipeline for
            Metagenome-Assembled Genomes (MAGs). It takes your assembled bins and
            bioinformatics tool outputs — CheckM quality scores, GTDB-Tk taxonomy — and
            walks you through metadata completion, validation, and direct submission to the
            European Nucleotide Archive (ENA) via Webin, without writing a single line of XML
            or running Webin-CLI manually.
          </p>
          <div class="grid-3">
            <div class="card">
              <h4>Standard</h4>
              <p class="muted">MIMAGS (ERC000047) — the Genomic Standards Consortium minimum information package for MAGs.</p>
            </div>
            <div class="card">
              <h4>Submission target</h4>
              <p class="muted">ENA via Webin REST API (samples & project) and Webin-CLI (genome assemblies). Testing and Production portals supported.</p>
            </div>
            <div class="card">
              <h4>Scale</h4>
              <p class="muted">Up to 1,000 MAGs per submission. Jobs run in the background — close the browser and check back in Jobs.</p>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.markdown("**Authors**")
        st.markdown(
            """
            This platform was developed by:

            - **Breno L. S. de Almeida** (corresponding author; brenoslivio@usp.br)
            - **Anderson P. Avila-Santos** (corresponding author; anderson.santos@ufz.de)
            - Martin Bole
            - Sanchita Kamath
            - Robson P. Bonidia
            - Peter F. Stadler
            - André C. P. L. F. de Carvalho
            - **Ulisses Rocha** (corresponding author; ulisses.rocha@ufz.de)

            Please cite the associated publication when using this platform in academic work.
            """
        )

    with st.container(border=True):
        st.markdown("**Acknowledgements**")
        st.markdown(
            """
            This work has been funded by the Canadian International Development Research Centre (IDRC) under the Grant Agreement 109981,
            and the UK government’s Foreign, Commonwealth and Development Office. The views expressed here do not necessarily reflect 
            those of the UK government’s Foreign, Commonwealth and Development Office, IDRC, or IDRC’s Board of Governors. 
            Breno L. S. de Almeida has been funded by the São Paulo Research Foundation (FAPESP), grant #2024/10958-1, and the 
            Google PhD Fellowship. This project (ZT-I-PF-3-108) was funded by the Initiative and Networking Fund of the Helmholtz 
            Association in the framework of the Helmholtz Metadata Collaboration project call.

            We also acknowledge open-source libraries and tools that made this work possible.
            """
        )


    with st.container(border=True):
        st.markdown("**Data Availability**")
        st.markdown(
            """
            The source code of the platform is available at: https://github.com/NFDI4Microbiota/ena_wizard_tool
            """
        )

    # ===== Who is it for + File formats =====
    st.markdown('<div class="container-max section">', unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown(
            """
            <div class="h2">🎯 Who is this for?</div>
            <ul class="list">
              <li>Bioinformaticians who have assembled MAGs and need to deposit them in ENA.</li>
              <li>Research groups running metagenomics studies under NFDI4Microbiota or similar consortia.</li>
              <li>Data stewards managing bulk MAG submissions for large environmental projects.</li>
            </ul>
            <p class="muted" style="margin-top:.5rem;">
              Assumed background: you have run a standard MAG workflow
              (assembly → binning → CheckM/CheckM2 quality → GTDB-Tk taxonomy) and want
              to deposit the results in ENA with minimal friction.
            </p>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            """
            <div class="h2">📄 File formats</div>
            <ul class="list">
              <li><b>Metadata:</b> TSV (.tsv) — download the built-in template from the Submit tab.</li>
              <li><b>Genomes:</b> gzip-compressed FASTA (<code>.fasta.gz</code>) — one file per MAG; filename must match <code>sample_name</code>.</li>
              <li><b>CheckM v1:</b> <code>storage.tsv</code> — columns <code>Bin Id</code>, <code>Completeness</code>, <code>Contamination</code>.</li>
              <li><b>CheckM2:</b> <code>quality_report.tsv</code> — columns <code>Name</code>, <code>Completeness</code>, <code>Contamination</code>.</li>
              <li><b>GTDB-Tk:</b> <code>gtdbtk.bac120.summary.tsv</code> or <code>gtdbtk.ar53.summary.tsv</code> — columns <code>user_genome</code>, <code>classification</code>.</li>
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
              <h4>Mandatory fields</h4>
              <ul class="list">
                <li>Derived directly from the ERC000047 XML checklist.</li>
                <li>Mandatory columns are marked with * in the editor.</li>
                <li>Empty mandatory cells are reported row by row.</li>
              </ul>
            </div>
            <div class="card">
              <h4>Regex patterns</h4>
              <ul class="list">
                <li>Field-specific patterns from ERC000047 (e.g., genome coverage must be a positive number).</li>
                <li>Geographic coordinates, dates, and accession IDs are checked against their respective patterns.</li>
              </ul>
            </div>
            <div class="card">
              <h4>Controlled vocabularies</h4>
              <ul class="list">
                <li>Enum fields (e.g., <i>assembly quality</i>, <i>completeness software</i>) only accept values listed in the checklist.</li>
                <li>Invalid values are flagged with the full list of accepted terms.</li>
              </ul>
            </div>
          </div>
          <div class="note muted" style="margin-top:.75rem;">
            Validation runs against the locally cached ERC000047 XML. The checklist is parsed dynamically — if ENA updates it, updating the XML file is all that is needed.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ===== Getting started =====
    st.markdown(
        """
        <div class="container-max section">
          <div class="h2">🚀 Getting started</div>
          <ol class="list">
            <li>Go to <b>Submit</b> and download the metadata template (or upload your existing TSV).</li>
            <li>In <b>Metadata assistance → Import quality files</b>, upload your CheckM / CheckM2 output to auto-fill completeness and contamination scores.</li>
            <li>Upload your GTDB-Tk summary to auto-fill organism names.</li>
            <li>Use <b>Taxonomy resolver</b> to batch-fill NCBI taxon IDs from ENA, and <b>ENVO term search</b> to find the right environmental context codes.</li>
            <li>Click <b>Validate metadata</b> — fix any errors reported in the table.</li>
            <li>Upload one <code>.fasta.gz</code> file per MAG (filenames must match <code>sample_name</code>).</li>
            <li>Fill in your ENA Webin credentials and study information, then click <b>Submit to ENA</b>.</li>
            <li>Monitor progress and retrieve accession numbers in the <b>Jobs</b> tab.</li>
          </ol>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ===== FAQ =====
    st.markdown('<div class="container-max section"><div class="h2">❓ FAQ</div></div>', unsafe_allow_html=True)
    with st.expander("Which ENA checklist does this tool use?"):
        st.write(
            "ERC000047 — the MIMAGS package from the Genomic Standards Consortium. "
            "It defines the minimum information required for a Metagenome-Assembled Genome submission."
        )
    with st.expander("Do I need a pre-existing ENA study (project)?"):
        st.write(
            "No. You can create a new study as part of the submission by providing a study name, title, "
            "and description. If you already have a study accession (e.g. PRJEB12345), select "
            "'Existing study accession' and paste it in."
        )
    with st.expander("What is the Testing portal and when should I use it?"):
        st.write(
            "ENA provides a testing environment at wwwdev.ebi.ac.uk that accepts submissions but does not "
            "create public records. Always run a test submission first to catch any issues before using the "
            "Production portal."
        )
    with st.expander("My MAG is a single contig — do I need to create a chromosome list?"):
        st.write(
            "No. The tool detects single-contig FASTA files automatically and generates the required "
            "chromosome list file on your behalf before passing it to Webin-CLI."
        )
    with st.expander("What happens if some MAGs succeed and others fail?"):
        st.write(
            "Each MAG is submitted independently via Webin-CLI. Successes and errors are logged "
            "separately in the job directory. Check the Jobs tab for a breakdown and the full Webin output."
        )
    with st.expander("Can I resubmit a failed MAG without re-running everything?"):
        st.write(
            "Currently each submission session is independent. For partial re-submissions, filter your "
            "metadata TSV to only the failed samples and start a new submission."
        )
    with st.expander("Is there a limit on how many MAGs I can submit at once?"):
        st.write("Yes — 1,000 rows per submission session.")

    # ===== Privacy + Contact =====
    st.markdown('<div class="container-max section">', unsafe_allow_html=True)
    p1, p2 = st.columns(2, gap="large")
    with p1:
        st.markdown(
            """
            <div class="h2">🔐 Privacy & Data Handling</div>
            <p class="muted">
              Uploaded FASTA files are written to a temporary directory and deleted automatically
              after the submission job completes. Metadata and credentials are held only in your
              session and the background job queue — they are not stored permanently.
              Do not submit data you are not authorised to make public.
            </p>
            """,
            unsafe_allow_html=True,
        )
    with p2:
        st.markdown(
            f"""
            <div class="h2">📬 Contact & Support</div>
            <div class="footer-card">
              <ul class="list">
                <li>Email: <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a></li>
                <li>ENA portal: <a href="{CONTACT_SITE}" target="_blank">{CONTACT_SITE}</a></li>
              </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)

    # ===== Credits =====
    st.markdown(
        f"""
        <div class="container-max section">
          <div class="h2">🎓 Credits & Citation</div>
          <p class="muted">
            If you use this tool in a publication, please cite <b>{ORG_NAME}</b> and the
            <b>{APP_NAME}</b>. Also cite CheckM, CheckM2, GTDB-Tk, and ENA where appropriate.
          </p>
          <p class="muted">
            <b>Making Microbiology Data FAIR and Open</b><br>
            As part of the Nationale Forschungsdaten Infrastruktur (NFDI),
            <b>NFDI4Microbiota</b> supports the microbiology community with access to data,
            analysis services, data/metadata standards, and training.
          </p>
          <p class="muted">
            <b>Microbial Data Science Group — UFZ (Germany)</b><br>
            Research and development contributions from the Microbial Data Science Group at the
            Helmholtz Centre for Environmental Research (UFZ), Leipzig.
          </p>
          <div class="h3">License</div>
          <p class="muted">{LICENSE}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

if __name__ == "__main__":
    runUI()
