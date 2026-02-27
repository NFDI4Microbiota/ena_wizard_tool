# 🧬 ENA Automatic Submission System

Automated validation and submission pipeline for **Metagenome-Assembled Genomes (MAGs)** to the **European Nucleotide Archive (ENA)**.

This project simplifies ENA submissions by automating:

* metadata validation
* ENA XML generation
* metadata submission via API
* assembly submission using `webin-cli`
* batch processing of large datasets

---

# ⚡ Quick Start

Clone the repository:

```bash
git clone https://github.com/NFDI4Microbiota/ena_wizard_tool.git
cd ena_wizard_tool
```

---

# 🧩 Installation

This project can be installed using either **uv (recommended)** or **pip**.

## Option 1 — Using uv (recommended)

This is the fastest and most reproducible setup.

### Install uv

```bash
pip install uv
```

or

```bash
curl -Ls https://astral.sh/uv/install.sh | sh
```

### Install dependencies

```bash
uv sync
```

Run commands with:

```bash
uv run python nfdi-ena-cli.py --help
```

---

## Option 2 — Using pip (classic)

Create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
# .venv\\Scripts\\activate    # Windows
```

Install dependencies:

```bash
pip install -e .
```

---

## External requirements

Required tools:

* Java (JRE/JDK)
* ENA webin-cli JAR

Expected location:

```
App/webin-cli-9.0.1.jar
```

---

# 📦 Project Overview

This repository is organized into two main components:

| Component                | Description                                      | Status                       |
| ------------------------ | ------------------------------------------------ | ---------------------------- |
| CLI Submission Tool      | Automated validation + ENA submission            | ✔ Available                  |
| Web Application (`App/`) | User-friendly interface for submission workflows | 🚧 Documentation coming soon |

> ⚠️ This README currently documents **only the CLI submission tool**.
> A dedicated section for the web application will be added later.

---

# ⚙️ CLI Submission Tool

The CLI performs the full MAG submission workflow to ENA.

## Main Features

### ✔ Metadata validation

Validation is automatically performed using the ENA checklist XML:

* mandatory field checking
* regex validation
* enum validation
* row-level error reporting

Checklist currently supported:

```
ERC000047 (MAG checklist)
```

### ✔ FASTA discovery

The tool automatically maps metadata entries to FASTA files:

```
sample_name ⇄ *.fasta.gz
```

Example:

```
sample_001.fasta.gz
```

### ✔ ENA metadata submission

The CLI automatically:

* generates ENA-compliant XML
* creates PROJECT (if needed)
* creates SAMPLE objects
* attaches checklist attributes
* submits through WEBIN v2 API

Supported portals:

* ENA TEST
* ENA PRODUCTION

### ✔ Assembly submission (webin-cli)

After metadata submission:

* manifest files are generated automatically
* assemblies are submitted using:

```
webin-cli (genome context)
```

Special handling:

* single-contig assemblies automatically generate chromosome lists.

### ✔ Logging system

All submission logs are saved under:

```
logs/
```

Generated files:

```
log_<batch>.xml
success.txt
error.txt
```

---

# 📂 Input Data

## Metadata table

Format:

```
TSV (tab-separated)
```

Example:

```
example.tsv
```

### Required core fields (simplified)

| Field             | Description              |
| ----------------- | ------------------------ |
| sample_name       | Unique sample identifier |
| organism          | Scientific organism name |
| tax_id            | NCBI taxonomy ID         |
| genome coverage   | Sequencing depth         |
| platform          | Sequencing platform      |
| assembly software | Assembly software used   |

Additional columns are automatically added as ENA sample attributes.

## FASTA directory

Example structure:

```
fasta/
 ├── sample1.fasta.gz
 ├── sample2.fasta.gz
```

---

# 🚀 CLI Usage

## Basic submission example

```bash
python nfdi-ena-cli.py \
  --metadata example.tsv \
  --fasta-dir fasta \
  --ena-user "your_username" \
  --ena-password "your_password" \
  --study-name "study example" \
  --study-title "title for the study" \
  --study-description "description for the study"
```

## Using an existing study accession

```bash
python nfdi-ena-cli.py \
  --metadata example.tsv \
  --fasta-dir fasta \
  --ena-user USER \
  --ena-password PASS \
  --study-accession PRJEBXXXX
```

## Production submission

Default portal:

```
test
```

To submit to production:

```bash
--portal prod
```

⚠️ Always validate using the TEST portal first.

---

# 🧠 Internal Workflow

```
Metadata TSV
      ↓
Checklist validation
      ↓
FASTA matching
      ↓
ENA XML generation
      ↓
Metadata submission (WEBIN API)
      ↓
Manifest generation
      ↓
webin-cli assembly submission
```

---

# 🧱 Automatic Metadata Handling

The CLI automatically:

* injects required ENA fields
* appends user-defined columns as SAMPLE_ATTRIBUTES
* ignores reserved internal columns

This allows metadata extension without code modification.

---

# 📊 Batch Processing

Large submissions are automatically split:

```
batch_size = 1000 samples
```

Each batch generates independent logs.

---

# 🔒 Security Notes

Credentials are passed via CLI arguments:

```
--ena-user
--ena-password
```

Recommended usage:

```bash
export ENA_USER=xxx
export ENA_PASS=xxx
```

---

# ⚠️ Common Errors

## Missing FASTA files

```
Missing FASTA files for: sample_X
```

Cause:

* FASTA filename does not match `sample_name`.

## Regex mismatch errors

Common causes:

* invalid date format
* wrong numeric format
* ontology formatting errors

## webin-cli errors

Check:

```
logs/error.txt
```

Typical causes:

* invalid manifest fields
* ENA temporary API issues
* missing metadata values

---

# 🧪 Development Notes

Main internal functions:

| Function               | Purpose             |
| ---------------------- | ------------------- |
| `load_fields_from_xml` | Parse ENA checklist |
| `validate_dataframe`   | Metadata validation |
| `collect_fastas`       | FASTA mapping       |
| `build_and_submit`     | Submission engine   |

---

# 🌐 Web Application (Coming Soon)

The `App/` directory contains the web application.

Documentation to be added:

* architecture overview
* local run instructions
* deployment guide
* user workflow

---

# 🧭 Roadmap

## Near future

* Full web interface documentation
* Interactive metadata validation
* Submission progress tracking
* Improved error visualization

## Future expansions

* Support for multiple ENA checklists
* MIXS package auto-detection
* Ontology live validation (ENVO/CHEBI)
* Parallelized submission engine

---

# 📚 References

* ENA Submission Portal: [https://www.ebi.ac.uk/ena/browser/submit](https://www.ebi.ac.uk/ena/browser/submit)
* ENA Checklist ERC000047: [https://www.ebi.ac.uk/ena/browser/view/ERC000047](https://www.ebi.ac.uk/ena/browser/view/ERC000047)
* MIXS Standard: [https://www.nature.com/articles/nbt1366](https://www.nature.com/articles/nbt1366)
* MIXS Term Browser: [https://w3id.org/mixs/](https://w3id.org/mixs/)

---

# 👨‍🔬 Intended Users

* Metagenomics researchers
* Bioinformatics pipelines
* Large-scale MAG submission projects
* Institutional data submission workflows
