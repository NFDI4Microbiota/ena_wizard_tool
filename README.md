# NFDI MAG2ENA

Automated validation and submission pipeline for **Metagenome-Assembled Genomes (MAGs)** to the **European Nucleotide Archive (ENA)**, implementing the [GSC MIMAGS / ERC000047](https://www.ebi.ac.uk/ena/browser/view/ERC000047) checklist.

The tool provides two interfaces for the same submission workflow:

| Interface | Best for |
|-----------|----------|
| **Web App** (`App/`) | Interactive submissions, metadata assistance, job tracking |
| **CLI** (`nfdi-mag2ena.py`) | Automated pipelines, high-throughput batch processing |

---

# 🚀 Quick Start

```bash
git clone https://github.com/NFDI4Microbiota/ena_wizard_tool.git
cd ena_wizard_tool
```

---

# 🧩 Installation

## Option 1 — Docker (recommended)

Runs the web app with Redis and Java pre-configured.

```bash
docker build -t ena-wizard-tool .
docker run -p 8501:8501 ena-wizard-tool
```

Open `http://localhost:8501`.

To persist job history across container restarts:

```bash
docker run -p 8501:8501 \
  -v "$(pwd)/App/jobs:/app/App/jobs" \
  -v "$(pwd)/App/task_results.db:/app/App/task_results.db" \
  ena-wizard-tool
```

## Option 2 — uv (local)

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Start Redis
redis-server --daemonize yes

# Start RQ worker (from App folder)
cd App && rq worker ena &

# Start the web app
uv run streamlit run App/app.py
```

## Option 3 — pip (classic)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .

redis-server --daemonize yes
cd App && rq worker ena &
streamlit run app.py
```

## External requirements

Java is required for Webin-CLI. Install on Debian/Ubuntu:

```bash
sudo apt install default-jre
```

The Webin-CLI JAR must be present at:

```
App/webin-cli-9.0.1.jar
```

---

# 🖥️ Web Application

The web app is a four-page Streamlit interface. Submissions run as background jobs via Redis Queue so the browser does not need to stay open.

## Pages

### Home
Overview of the tool, feature highlights, and a 6-step workflow summary.

### Submit
Three-step guided submission workflow (detailed below).

### Jobs
Track submission status by job ID. Download all output files once complete.

### About & Help
Full documentation, FAQs, file format specifications, and contact information.

---

## Submit Workflow

### Step 1 — Metadata

Enter metadata manually in the editable table, upload a TSV, or download the provided template. All fields are validated against the ERC000047 checklist in real time.

**Metadata assistance tools:**

| Tool | Description |
|------|-------------|
| **ENA Autofill** | Enter a source sample accession (e.g. `ERS123456`) to auto-populate environmental fields: isolation source, collection date, coordinates, biome context |
| **Taxonomy Resolver** | Look up NCBI Taxonomy IDs in bulk from organism names via the ENA taxonomy API |
| **ENVO Term Search** | Search the ENVO ontology for `broad-scale environmental context`, `local environmental context`, and `environmental medium` |
| **Fill Column** | Apply one value across an entire column, with enum-aware dropdowns for controlled vocabulary fields |
| **Import Quality Files** | Parse and merge CheckM, CheckM2, and GTDB-Tk output files directly into the metadata table |

**Supported quality file formats:**

| Tool | Expected filename |
|------|-------------------|
| CheckM v1 | `storage.tsv` |
| CheckM2 | `quality_report.tsv` |
| GTDB-Tk | `gtdbtk.bac120.summary.tsv` or `gtdbtk.ar53.summary.tsv` |

GTDB-Tk organism names are parsed with rank-aware logic: species names are preferred, falling back to genus/family with an `uncultured` prefix when only higher-rank assignments are available.

### Step 2 — FASTA Files

Upload one `.fasta.gz` file per MAG. The filename (without the `.fasta.gz` suffix) must exactly match the `sample_name` in the metadata table. Single-contig bins are detected automatically and a chromosome list file is generated as required by ENA.

### Step 3 — ENA Submission

| Field | Details |
|-------|---------|
| Study | Create a new study (name, title ≥ 20 chars, description ≥ 20 chars) or provide an existing accession (`PRJEBXXXX`) |
| Credentials | ENA Webin username and password |
| Portal | **Testing** (default — always validate here first) or **Production** |
| Email | Optional — receive a notification when the job finishes (requires Mailgun API key in `secrets.toml`) |

Clicking **Submit** enqueues the job. Copy the job ID to check progress in the **Jobs** page.

---

## Jobs Page

Look up any job by its ID to see:

- **Queued / Running**: Current position in the queue
- **Success**: Number of MAGs submitted, number of errors, and download links for all output files
- **Failed**: Error details

**Downloadable outputs per job:**

| File | Contents |
|------|----------|
| `submit.xml` | ENA metadata XML sent to WEBIN v2 |
| `webin_log.xml` | ENA response containing sample accessions |
| `manifests.zip` | Per-MAG Webin-CLI manifest files |
| `success.txt` | Assemblies submitted successfully |
| `error.txt` | Assemblies that failed with error details |

---

# ⚙️ CLI Tool

`nfdi-mag2ena.py` runs the same submission pipeline non-interactively. Large datasets are split into batches of 1,000 samples automatically.

## Usage

```bash
# Submit with a new study
python nfdi-mag2ena.py \
  --metadata examples/metadata.tsv \
  --fasta-dir examples/fasta \
  --ena-user Webin-XXXXX \
  --ena-password 'your_password' \
  --study-name 'My MAG study' \
  --study-title 'Descriptive title longer than 20 characters' \
  --study-description 'Study description longer than 20 characters'

# Submit to an existing study
python nfdi-mag2ena.py \
  --metadata examples/metadata.tsv \
  --fasta-dir examples/fasta \
  --ena-user Webin-XXXXX \
  --ena-password 'your_password' \
  --study-accession PRJEBXXXX

# Submit to production (default is test)
python nfdi-mag2ena.py ... --portal prod
```

**Always validate using `--portal test` (the default) before submitting to production.**

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `--metadata` | Yes | Path to metadata TSV |
| `--fasta-dir` | Yes | Directory containing `.fasta.gz` files |
| `--ena-user` | Yes | ENA Webin username |
| `--ena-password` | Yes | ENA Webin password |
| `--portal` | No | `test` (default) or `prod` |
| `--study-accession` | No* | Existing study accession |
| `--study-name` | No* | New study short name |
| `--study-title` | No* | New study title (≥ 20 chars) |
| `--study-description` | No* | New study description (≥ 20 chars) |

\* Either `--study-accession` or all three `--study-*` fields are required.

## Outputs

Logs are written to `logs/` after each batch:

```
logs/
├── log_<batch>.xml      # ENA response XML
├── success.txt          # Successfully submitted assemblies
└── error.txt            # Failed assemblies
```

---

# 📂 Input Format

## Metadata TSV

Tab-separated file. One row per MAG.

**Mandatory fields:**

| Field | Notes |
|-------|-------|
| `sample_name` | Unique identifier — must match FASTA filename |
| `organism` | Scientific name (e.g. `uncultured Firmicutes bacterium`) |
| `tax_id` | NCBI Taxonomy ID |
| `genome coverage` | Positive number |
| `platform` | Sequencing platform (controlled vocabulary) |
| `assembly software` | Software name and version |
| `assembly quality` | Controlled vocabulary |
| `completeness score` | 0–100 |
| `contamination score` | 0–100 |
| `completeness software` | e.g. `CheckM2` |
| `binning software` | Software name |
| `binning parameters` | Free text |
| `metagenomic source` | Source metagenome accession |
| `isolation_source` | Free text |
| `collection date` | ISO 8601 format |
| `geographic location (country and/or sea)` | Controlled vocabulary |
| `geographic location (latitude)` | Decimal degrees |
| `geographic location (longitude)` | Decimal degrees |
| `broad-scale environmental context` | ENVO term (e.g. `ENVO:00000446`) |
| `local environmental context` | ENVO term |
| `environmental medium` | ENVO term |
| `taxonomic identity marker` | e.g. `multi-marker approach` |
| `sample derived from` | Source sample accession (e.g. `ERS123456`) |
| `project name` | Free text |

Any additional columns are submitted as ENA `SAMPLE_ATTRIBUTE` entries without modification.

A template TSV is available for download from the Submit page or at `template.tsv`.

## FASTA Files

- Format: gzip-compressed (`.fasta.gz`)
- One file per MAG
- Filename without extension must match `sample_name` exactly
- Maximum 1,000 MAGs per submission

---

# 🔒 Credentials & Secrets

ENA credentials are entered interactively in the web app or passed as CLI arguments.

For the Mailgun email notification feature, create `App/.streamlit/secrets.toml`:

```toml
api_key = "your-mailgun-api-key"
```

If this file is absent, email notifications are silently skipped and all other functionality works normally.

When using Docker, mount the file at runtime to avoid baking credentials into the image:

```bash
docker run -p 8501:8501 \
  -v "$(pwd)/App/.streamlit/secrets.toml:/app/App/.streamlit/secrets.toml:ro" \
  ena-wizard-tool
```

---

# 🧠 Submission Workflow (Internal)

```
Metadata TSV
      │
      ▼
ERC000047 validation
      │
      ▼
FASTA file matching (sample_name ↔ filename)
      │
      ▼
ENA XML generation (SAMPLE_SET + optional PROJECT_SET)
      │
      ▼
WEBIN v2 metadata submission → sample accessions returned
      │
      ▼
Per-MAG manifest generation
      │   └─ single-contig? → chromosome list generated
      ▼
Webin-CLI assembly submission (webin-cli-9.0.1.jar)
      │
      ▼
Logs: success.txt / error.txt / webin_log.xml
```

---

# ⚠️ Common Errors

**Missing FASTA file**
```
Missing FASTA files for: sample_X
```
The FASTA filename (without `.fasta.gz`) does not match `sample_name` in the metadata table.

**Validation errors**
Check for: wrong date format (use ISO 8601), coordinates with wrong notation, enum values not matching the checklist, or empty mandatory fields.

**Webin-CLI errors**
See `error.txt` in the job output. Common causes: invalid manifest field values, temporary ENA API issues, or missing metadata values that passed local validation but failed server-side.

---

# 📚 References

- ENA Submission Portal: https://www.ebi.ac.uk/ena/browser/submit
- ENA Checklist ERC000047: https://www.ebi.ac.uk/ena/browser/view/ERC000047
- GSC MIxS Standard: https://www.nature.com/articles/nbt1366
- MIxS Term Browser: https://w3id.org/mixs/
- ENVO Ontology: https://www.ebi.ac.uk/ols4/ontologies/envo

---

# 👨‍🔬 Authors & Acknowledgements

Developed by Breno L.S. de Almeida, Anderson P. Avila-Santos, and contributors.

Supported by NFDI4Microbiota, with funding from IDRC, FAPESP, and Helmholtz Association.

Issues and contributions welcome on [GitHub](https://github.com/NFDI4Microbiota/ena_wizard_tool).
