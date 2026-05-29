import streamlit as st
import pandas as pd
import polars as pl
import re
import xml.etree.ElementTree as ET
import gzip
import tempfile
import zipfile
from pathlib import Path
import subprocess
import requests
import time
import json
from datetime import datetime
from urllib.parse import quote
from rq import get_current_job
from utils.tasks import enqueue_task, manager
from utils.db import TaskResultManager, TaskStatus

# =========================================================
# CONFIG
# =========================================================

_HERE = Path(__file__).parent
_APP_DIR = _HERE.parent
_PROJECT_DIR = _APP_DIR.parent

CHECKLIST_XML = str(_PROJECT_DIR / "checklists" / "ERC000047.xml")
WEBIN_JAR = str(_APP_DIR / "webin-cli-9.0.1.jar")
SUBMISSIONS_DIR = _APP_DIR / "jobs"
EXAMPLES_DIR = _PROJECT_DIR / "examples"

# =========================================================
# METADATA HELPERS
# =========================================================

_DATE_REGEX = re.compile(
    r'^[12][0-9]{3}(-(0[1-9]|1[0-2])(-(0[1-9]|[12][0-9]|3[01])'
    r'(T[0-9]{2}:[0-9]{2}(:[0-9]{2})?Z?([+-][0-9]{1,2})?)?)?)?'
    r'(/[0-9]{4}(-[0-9]{2}(-[0-9]{2}'
    r'(T[0-9]{2}:[0-9]{2}(:[0-9]{2})?Z?([+-][0-9]{1,2})?)?)?)?)?$'
)


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_ena_sample_metadata(sample_acc: str) -> dict:
    """Fetch sample attributes from ENA XML API for a sample accession."""
    url = f"https://www.ebi.ac.uk/ena/browser/api/xml/{sample_acc.strip()}"
    try:
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        attrs = {}
        for attr in root.findall(".//SAMPLE_ATTRIBUTE"):
            tag = attr.findtext("TAG", "").strip()
            value = attr.findtext("VALUE", "").strip()
            if tag:
                attrs[tag] = value
        sci_name = root.findtext(".//SAMPLE_NAME/SCIENTIFIC_NAME", "").strip()
        if not attrs.get("organism") and sci_name:
            attrs["organism"] = sci_name
        return attrs
    except Exception as exc:
        return {"_error": str(exc)}


def _fix_coordinate_string(coord_str: str):
    """Parse lat_lon attribute (e.g. '1.5 N 40.2 E') into (lat_str, lon_str)."""
    if not coord_str:
        return None, None
    coord_str = str(coord_str).strip()
    match = re.search(
        r'(\d*\.?\d+)\s*([NS])\s+(\d*\.?\d+)\s*([EW])',
        coord_str,
        re.IGNORECASE,
    )
    if match:
        lat = float(match.group(1)) * (-1 if match.group(2).upper() == "S" else 1)
        lon = float(match.group(3)) * (-1 if match.group(4).upper() == "W" else 1)
        return str(round(lat, 6)), str(round(lon, 6))
    # Bare "lat lon" without direction letters
    parts = coord_str.split()
    if len(parts) == 2:
        try:
            return str(float(parts[0])), str(float(parts[1]))
        except ValueError:
            pass
    return None, None


def _normalize_date(date_str: str) -> str:
    """Normalise a date string to the ISO 8601 format ENA expects."""
    if not date_str or date_str.strip() in ("", "missing"):
        return ""
    d = re.sub(r'^(\d{4})$', r'\1-01-01', date_str.strip())
    d = re.sub(r'^(\d{4})-(\d{2})$', r'\1-\2-01', d)
    d = re.sub(r'^(\d{4})(\d{2})(\d{2})$', r'\1-\2-\3', d)
    return d if _DATE_REGEX.fullmatch(d) else ""


def _attrs_to_mag_metadata(attrs: dict) -> dict:
    """Map raw ENA sample attributes to MAG metadata column names."""
    env_broad = attrs.get("env_broad_scale") or attrs.get("env_biome") or ""
    env_local = attrs.get("env_local_scale") or attrs.get("env_feature") or ""
    env_medium = attrs.get("env_medium") or attrs.get("env_material") or ""

    if not env_broad and not env_local and not env_medium:
        gold = attrs.get("GOLD Ecosystem Classification", "")
        if gold:
            parts = gold.split(" | ")
            env_broad = parts[1] if len(parts) > 1 else ""
            env_local = parts[2] if len(parts) > 2 else ""
            env_medium = parts[3] if len(parts) > 3 else ""

    geo_loc_name = attrs.get("geo_loc_name", "")
    country = geo_loc_name.split(":")[0].strip() if geo_loc_name else ""

    lat, lon = _fix_coordinate_string(attrs.get("lat_lon", ""))

    return {
        "metagenomic source": attrs.get("organism", ""),
        "isolation_source": attrs.get("isolation_source", ""),
        "collection date": _normalize_date(attrs.get("collection_date", "")),
        "geographic location (latitude)": lat or "",
        "geographic location (longitude)": lon or "",
        "broad-scale environmental context": env_broad,
        "local environmental context": env_local,
        "environmental medium": env_medium,
        "geographic location (country and/or sea)": country,
    }


@st.cache_data(ttl=300, show_spinner=False)
def _ena_taxonomy_search(query: str) -> list[dict]:
    if len(query.strip()) < 3:
        return []
    try:
        r = requests.get(
            f"https://www.ebi.ac.uk/ena/taxonomy/rest/suggest-for-search/{quote(query.strip())}",
            timeout=6,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def _envo_search(query: str) -> list[dict]:
    if len(query.strip()) < 3:
        return []
    try:
        r = requests.get(
            "https://www.ebi.ac.uk/ols4/api/search",
            params={"q": query.strip(), "ontology": "envo", "rows": 8},
            timeout=6,
        )
        r.raise_for_status()
        docs = r.json().get("response", {}).get("docs", [])
        return [
            {
                "label": d.get("label", ""),
                "obo_id": d.get("obo_id", ""),
                "description": (d.get("description") or [""])[0][:120],
            }
            for d in docs
            if d.get("label") and d.get("obo_id")
        ]
    except Exception:
        return []


def _parse_checkm_file(file) -> pd.DataFrame | None:
    """Parse CheckM or CheckM2 output TSV into sample_name + quality columns."""
    try:
        df = pd.read_csv(file, sep="\t")
        cols = df.columns.tolist()
        if "Name" in cols and "Completeness" in cols and "Contamination" in cols:
            name_col, software = "Name", "CheckM2"
        elif "Bin Id" in cols and "Completeness" in cols and "Contamination" in cols:
            name_col, software = "Bin Id", "CheckM"
        else:
            return None
        return pd.DataFrame({
            "sample_name": df[name_col].astype(str),
            "completeness score": df["Completeness"].round(2).astype(str),
            "contamination score": df["Contamination"].round(2).astype(str),
            "completeness software": software,
        })
    except Exception:
        return None


def _parse_gtdbtk_file(file) -> pd.DataFrame | None:
    """Parse GTDB-Tk summary TSV into sample_name + organism columns."""
    try:
        df = pd.read_csv(file, sep="\t")
        if "user_genome" not in df.columns or "classification" not in df.columns:
            return None

        def _gtdb_to_name(classification: str) -> str:
            parts = {}
            for p in classification.split(";"):
                if "__" in p:
                    rank, name = p.split("__", 1)
                    parts[rank.strip()] = name.strip().replace("_", " ")
            for rank in ("s", "g", "f", "o", "c", "p"):
                name = parts.get(rank, "")
                if name:
                    return name if rank == "s" else f"uncultured {name} bacterium"
            return "uncultured bacterium"

        return pd.DataFrame({
            "sample_name": df["user_genome"].astype(str),
            "organism": df["classification"].apply(_gtdb_to_name),
        })
    except Exception:
        return None


def _merge_into_metadata(base: pd.DataFrame, overlay: pd.DataFrame) -> pd.DataFrame:
    """Merge overlay columns into base, keyed on sample_name. Only fills empty cells."""
    result = base.copy()
    for col in overlay.columns:
        if col == "sample_name" or col not in result.columns:
            continue
        for _, orow in overlay.iterrows():
            mask = result["sample_name"] == orow["sample_name"]
            if not mask.any():
                continue
            idx = result.index[mask][0]
            current = result.at[idx, col]
            if pd.isna(current) or str(current).strip() in ("", "<NA>", "None", "nan"):
                result.at[idx, col] = str(orow[col])
    return result


# =========================================================
# XML CHECKLIST
# =========================================================

def _field(label, description, mandatory, ftype, *, regex=None, enum=None):
    return {"label": label, "description": description, "type": ftype,
            "regex": regex, "enum": enum, "mandatory": mandatory}


def load_fields_from_xml(xml_path: str) -> dict:

    tree = ET.parse(xml_path)
    root = tree.getroot()

    fields = {
        "sample_name": _field("sample_name", "Sample name (must match fasta filename)", True, "free"),
        "organism":    _field("organism",    "Scientific organism name",                True, "free"),
        "tax_id":      _field("tax_id",      "NCBI taxonomy ID",                        True, "free"),
    }

    for field in root.findall(".//FIELD"):

        label = field.findtext("LABEL")
        description = field.findtext("DESCRIPTION")
        mandatory = field.findtext("MANDATORY") == "mandatory"

        regex_elem = field.findtext(".//REGEX_VALUE")
        enum_elems = field.findall(".//TEXT_CHOICE_FIELD/TEXT_VALUE/VALUE")

        if regex_elem:
            fields[label] = _field(label, description, mandatory, "regex",
                                   regex=re.compile(regex_elem))
        elif enum_elems:
            fields[label] = _field(label, description, mandatory, "enum",
                                   enum=[e.text for e in enum_elems])
        else:
            fields[label] = _field(label, description, mandatory, "free")

    fields["genome coverage"] = _field(
        "genome coverage", "Estimated sequencing depth", True, "regex",
        regex=re.compile(r"^(?:0?\.[0-9]*[1-9][0-9]*|[1-9][0-9]*(?:\.[0-9]+)?)$"),
    )
    fields["platform"] = _field("platform", "Sequencing platform", True, "free")

    return fields

# =========================================================
# VALIDATION
# =========================================================

def validate_dataframe(df: pd.DataFrame, field_defs: dict) -> pd.DataFrame:

    errors = []

    for col in df.columns:

        if col not in field_defs:
            continue

        field = field_defs[col]

        for idx, value in df[col].items():

            value_str = "" if pd.isna(value) else str(value).strip()

            if field["mandatory"] and value_str == "":
                errors.append({
                    "row": idx + 1,
                    "field": col,
                    "value": "",
                    "expected": "Mandatory field — cannot be empty"
                })
                continue

            if value_str == "":
                continue

            if field["type"] == "regex":

                if not field["regex"].fullmatch(value_str):
                    errors.append({
                        "row": idx + 1,
                        "field": col,
                        "value": value_str,
                        "expected": f"Pattern: {field['regex'].pattern}"
                    })

            elif field["type"] == "enum":

                if value_str not in field["enum"]:
                    errors.append({
                        "row": idx + 1,
                        "field": col,
                        "value": value_str,
                        "expected": ", ".join(field["enum"])
                    })

    return pd.DataFrame(errors)

# =========================================================
# STREAMLIT TABLE CONFIG
# =========================================================

def build_column_config(field_defs: dict):

    column_config = {}

    for name, field in field_defs.items():

        label = (
            f"{field['label']} *"
            if field["mandatory"]
            else field["label"]
        )

        if field["type"] == "enum":

            column_config[name] = st.column_config.SelectboxColumn(
                label=label,
                options=field["enum"],
                help=field["description"]
            )

        else:

            column_config[name] = st.column_config.TextColumn(
                label=label,
                help=field["description"]
            )

    return column_config

# =========================================================
# DATAFRAME
# =========================================================

def initialize_empty_dataframe(field_defs):

    return pd.DataFrame(
        [{col: None for col in field_defs.keys()}],
        dtype="string"
    )

def load_tsv_into_schema(tsv_file, field_defs):

    schema_cols = list(field_defs.keys())

    df = pd.read_csv(tsv_file, sep="\t", dtype="string")

    return df.reindex(columns=schema_cols).astype("string")

# =========================================================
# FASTA
# =========================================================

def persist_fastas_temp(uploaded_files):

    fasta_map = {}

    for uf in uploaded_files:

        if not uf.name.endswith(".fasta.gz"):
            continue

        sample_name = uf.name.removesuffix(".fasta.gz")

        if sample_name in fasta_map:
            raise ValueError(f"Duplicate FASTA file: {sample_name}")

        tmp = tempfile.NamedTemporaryFile(
            suffix=".fasta.gz",
            delete=False
        )

        tmp.write(uf.getbuffer())
        tmp.flush()
        tmp.close()

        fasta_map[sample_name] = Path(tmp.name).resolve()

    return fasta_map

# =========================================================
# SUBMISSION WORKER (runs in RQ worker process)
# =========================================================

def submission_task(df_records, submission, fasta_map_str, email=None):
    """
    RQ worker function. All arguments must be JSON-serializable.
    df_records: list of dicts from pl.DataFrame.to_dicts()
    fasta_map_str: {sample_name: absolute_path_str}
    """
    job = get_current_job()
    job_id = job.id if job else datetime.now().strftime("%Y%m%d_%H%M%S")

    manager.store_start(job_id, TaskStatus.RUNNING)

    log_dir = SUBMISSIONS_DIR / job_id
    log_dir.mkdir(parents=True, exist_ok=True)

    df = pl.DataFrame(df_records)
    fasta_map = {k: Path(v) for k, v in fasta_map_str.items()}

    samples_submitted = 0
    samples_error = 0

    RESERVED_COLUMNS = {
        "sample_name",
        "organism",
        "tax_id",
        "ENA-CHECKLIST",
    }

    df = df.with_columns(
        pl.lit("ERC000047").alias("ENA-CHECKLIST")
    )

    project_accession = submission["study_accession"]

    root = ET.Element("WEBIN")

    submission_set = ET.fromstring("""
    <SUBMISSION_SET>
        <SUBMISSION>
            <ACTIONS>
                <ACTION>
                    <ADD/>
                </ACTION>
            </ACTIONS>
        </SUBMISSION>
    </SUBMISSION_SET>
    """)

    root.append(submission_set)

    if not project_accession:

        project_set = ET.fromstring(f"""
        <PROJECT_SET>
            <PROJECT alias="{submission["study_name"]}">
            <TITLE>{submission["study_title"]}</TITLE>
            <DESCRIPTION>{submission["study_description"]}</DESCRIPTION>
            <SUBMISSION_PROJECT>
                <SEQUENCING_PROJECT/>
            </SUBMISSION_PROJECT>
            </PROJECT>
        </PROJECT_SET>
        """)

        root.append(project_set)

    sample_set = ET.SubElement(root, "SAMPLE_SET")

    for row in df.iter_rows(named=True):

        sample = ET.SubElement(sample_set, "SAMPLE", {
            "alias": str(row["sample_name"]),
            "center_name": ""
        })

        ET.SubElement(sample, "TITLE").text = (
            "This sample represents a MAG derived from the metagenomic sample "
            + str(row["sample derived from"])
        )

        sname = ET.SubElement(sample, "SAMPLE_NAME")

        ET.SubElement(sname, "TAXON_ID").text = str(row["tax_id"])
        ET.SubElement(sname, "SCIENTIFIC_NAME").text = str(row["organism"])

        attrs = ET.SubElement(sample, "SAMPLE_ATTRIBUTES")

        def add_attr(tag, value, units=None):

            sa = ET.SubElement(attrs, "SAMPLE_ATTRIBUTE")

            ET.SubElement(sa, "TAG").text = tag
            ET.SubElement(sa, "VALUE").text = str(value)

            if units:
                ET.SubElement(sa, "UNITS").text = units

        explicit_cols = {
            "metagenomic source",
            "sample derived from",
            "project name",
            "completeness score",
            "completeness software",
            "contamination score",
            "binning software",
            "assembly quality",
            "binning parameters",
            "taxonomic identity marker",
            "isolation_source",
            "collection date",
            "geographic location (latitude)",
            "geographic location (longitude)",
            "broad-scale environmental context",
            "local environmental context",
            "environmental medium",
            "geographic location (country and/or sea)",
            "assembly software",
            "platform",
            "genome coverage",
        }

        add_attr("metagenomic source", row["metagenomic source"])
        add_attr("sample derived from", row["sample derived from"])
        add_attr("project name", row["project name"])
        add_attr("completeness score", row["completeness score"], "%")
        add_attr("completeness software", row["completeness software"])
        add_attr("contamination score", row["contamination score"], "%")
        add_attr("binning software", row["binning software"])
        add_attr("assembly quality", row["assembly quality"])
        add_attr("binning parameters", row["binning parameters"])
        add_attr("taxonomic identity marker", row["taxonomic identity marker"])
        add_attr("isolation_source", row["isolation_source"])
        add_attr("collection date", row["collection date"])

        add_attr(
            "geographic location (latitude)",
            row["geographic location (latitude)"],
            "DD"
        )

        add_attr(
            "geographic location (longitude)",
            row["geographic location (longitude)"],
            "DD"
        )

        add_attr(
            "broad-scale environmental context",
            row["broad-scale environmental context"]
        )

        add_attr(
            "local environmental context",
            row["local environmental context"]
        )

        add_attr(
            "environmental medium",
            row["environmental medium"]
        )

        add_attr(
            "geographic location (country and/or sea)",
            row["geographic location (country and/or sea)"]
        )

        add_attr(
            "assembly software",
            row["assembly software"]
        )

        for col, value in row.items():

            if col in RESERVED_COLUMNS:
                continue

            if col in explicit_cols:
                continue

            if value is None or str(value).strip() == "":
                continue

            add_attr(col, value)

        add_attr("ENA-CHECKLIST", row["ENA-CHECKLIST"])

    xml_bytes = ET.tostring(
        root,
        encoding="UTF-8",
        xml_declaration=True
    )

    with open(log_dir / "submit.xml", "wb") as f:
        f.write(xml_bytes)

    if submission["portal"] == "Testing":
        url = "https://wwwdev.ebi.ac.uk/ena/submit/webin-v2/submit/queue"
    else:
        url = "https://www.ebi.ac.uk/ena/submit/webin-v2/submit/queue"

    auth = (
        submission["ena_user"],
        submission["ena_password"]
    )

    headers = {
        "Accept": "application/json"
    }

    files = {
        "file": ("submit.xml", xml_bytes, "text/xml")
    }

    response = requests.post(
        url,
        headers=headers,
        files=files,
        auth=auth
    )

    response.raise_for_status()

    response_json = response.json()

    poll_url = response_json["_links"]["poll"]["href"]

    response = requests.get(poll_url, auth=auth)

    while response.status_code != 200:
        time.sleep(5)
        response = requests.get(poll_url, auth=auth)

    xml_text = response.text

    xml_log = log_dir / "webin_log.xml"

    with open(xml_log, "w", encoding="utf-8") as f:
        f.write(xml_text)

    root = ET.fromstring(xml_text)

    alias_to_accession = {}

    for sample in root.findall(".//SAMPLE"):

        accession = sample.get("accession")

        if accession:
            alias_to_accession[
                sample.get("alias")
            ] = accession

    error_regex = re.compile(
        r'alias: "(.+?)".*accession: "(.+?)"'
    )

    for err in root.findall(".//ERROR"):

        error_msg = err.text

        match = error_regex.search(error_msg)

        if match:

            alias, accession = match.groups()

            alias_to_accession[alias] = accession

    if not project_accession:

        for project in root.findall(".//PROJECT"):
            project_accession = project.get("accession")

    manifests = {}

    for alias, sample_accession in alias_to_accession.items():

        fasta_path = fasta_map[alias]

        seq_count = 0
        last_header = None

        with gzip.open(fasta_path, "rt") as f:

            for line in f:

                if line.startswith(">"):

                    seq_count += 1
                    last_header = line[1:].strip()

                    if seq_count > 1:
                        break

        sample_row = df.filter(pl.col("sample_name") == alias)

        base_manifest = f"""STUDY   {project_accession}
SAMPLE   {sample_accession}
ASSEMBLYNAME   {alias}
ASSEMBLY_TYPE   Metagenome-Assembled Genome (MAG)
COVERAGE   {sample_row["genome coverage"].item()}
PROGRAM   {sample_row["assembly software"].item()}
PLATFORM   {sample_row["platform"].item()}
FASTA   {fasta_path}"""

        chromosome_gz_path = None

        if seq_count == 1:

            chromosome_list = (
                f"{last_header}\t{alias}\tchromosome"
            )

            with tempfile.NamedTemporaryFile(
                mode="wb+",
                suffix=".gz",
                delete=False
            ) as tmp_chromosome_gz:

                with gzip.GzipFile(
                    fileobj=tmp_chromosome_gz,
                    mode="wb"
                ) as gz_file:

                    gz_file.write(
                        chromosome_list.encode("utf-8")
                    )

                chromosome_gz_path = tmp_chromosome_gz.name

            base_manifest += (
                f"\nCHROMOSOME_LIST   {chromosome_gz_path}"
            )

        manifests[alias] = base_manifest

        with tempfile.NamedTemporaryFile(
            mode="w+",
            delete=False
        ) as tmp_manifest:

            tmp_manifest.write(base_manifest)

            manifest_path = tmp_manifest.name

        try:

            cmd = [
                "java",
                "-jar",
                WEBIN_JAR,
                "-username",
                auth[0],
                "-password",
                auth[1],
                "-context",
                "genome",
                "-manifest",
                manifest_path,
                "-submit",
            ]

            if submission["portal"] == "Testing":
                cmd.append("-test")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )

            success = (
                "successfully" in result.stdout.lower()
            )

            logfile = (
                log_dir / "success.txt"
                if success
                else log_dir / "error.txt"
            )

            with open(logfile, "a") as f:
                f.write(
                    f"SAMPLE : {alias}\n"
                    f"{result.stdout}\n"
                )

            if success:
                samples_submitted += 1
            else:
                samples_error += 1

        finally:

            Path(manifest_path).unlink(missing_ok=True)

            if chromosome_gz_path:
                Path(chromosome_gz_path).unlink(missing_ok=True)

    with zipfile.ZipFile(log_dir / "manifests.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        for alias, content in manifests.items():
            zf.writestr(f"{alias}.manifest", content)

    # Clean up temp FASTA files
    for path in fasta_map.values():
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass

    task_result = {
        "submitted": samples_submitted,
        "errors": samples_error,
        "log_dir": str(log_dir),
    }

    with open(log_dir / "result.json", "w") as f:
        json.dump(task_result, f)

    return task_result

@st.dialog("Job submitted")
def job_submitted_dialog(job_id):
    st.success(
        f'Job submitted to the queue.\n\n'
        f'You can consult the results in **Jobs** using the following ID:\n\n'
        f'**{job_id}**\n\n'
        f'Save this ID securely.'
    )

# =========================================================
# UI
# =========================================================

def runUI():

    if not Path(WEBIN_JAR).exists():
        st.error(f"Missing Webin CLI jar: {WEBIN_JAR}")
        st.stop()

    field_defs = load_fields_from_xml(CHECKLIST_XML)

    if "metadata_df" not in st.session_state:
        st.session_state.metadata_df = initialize_empty_dataframe(field_defs)

    if "editor_key" not in st.session_state:
        st.session_state.editor_key = 0

    st.info(
        "This page walks you through submitting Metagenome-Assembled Genomes (MAGs) to ENA. "
        "Fill in your metadata, upload one `.fasta.gz` file per MAG, enter your ENA Webin "
        "credentials, and submit — all XML and Webin-CLI manifests are generated automatically. "
        "**Limit: 1,000 MAGs per job.** For larger collections, split your metadata into batches "
        "of up to 1,000 rows and submit each batch separately.",
        icon="ℹ️",
    )

    # ── Step 1: Metadata ──────────────────────────────────────────────────────
    st.subheader("Step 1 — Metadata")

    use_example = st.toggle(
        "Load example data",
        key="use_example_toggle",
        help=(
            "Populate the metadata table with two example MAGs and automatically load their "
            "FASTA files — lets you test the full submission workflow without your own data."
        ),
    )

    if use_example and not st.session_state.get("_example_active"):
        st.session_state.metadata_df = load_tsv_into_schema(
            EXAMPLES_DIR / "metadata.tsv", field_defs
        )
        st.session_state.pop("validated_df", None)
        st.session_state.pop("tsv_filename", None)
        st.session_state.pop("_example_fasta_map", None)
        st.session_state.editor_key += 1
        st.session_state._example_active = True
        st.rerun()
    elif not use_example and st.session_state.get("_example_active"):
        st.session_state.metadata_df = initialize_empty_dataframe(field_defs)
        st.session_state.pop("validated_df", None)
        st.session_state.pop("_example_fasta_map", None)
        st.session_state.editor_key += 1
        st.session_state._example_active = False
        st.rerun()

    col_upload, col_template = st.columns([3, 1])

    with col_upload:
        uploaded_tsv = st.file_uploader(
            "Upload metadata TSV (optional)",
            type=["tsv"],
            help="Upload an existing TSV to pre-fill the table. You can continue editing it below.",
            disabled=use_example,
        )

    with col_template:
        template_df = initialize_empty_dataframe(field_defs)
        tsv_bytes = template_df.to_csv(sep="\t", index=False).encode()
        st.download_button(
            "Download template",
            data=tsv_bytes,
            file_name="metadata_template.tsv",
            mime="text/tab-separated-values",
            use_container_width=True,
            help="Download an empty TSV template with the required columns."
        )

    # Only reload from TSV when a new file is uploaded (different filename),
    # so that subsequent user edits to the table are not overwritten on re-render.
    if not use_example and uploaded_tsv:
        if st.session_state.get("tsv_filename") != uploaded_tsv.name:
            st.session_state.metadata_df = load_tsv_into_schema(uploaded_tsv, field_defs)
            st.session_state.tsv_filename = uploaded_tsv.name
            st.session_state.pop("validated_df", None)
            st.session_state.editor_key += 1

    row_count = len(st.session_state.metadata_df)
    st.caption(
        f"{row_count} row{'s' if row_count != 1 else ''} · "
        "Columns marked with * are mandatory · "
        "Hover column headers for field descriptions"
    )

    edited_df = st.data_editor(
        st.session_state.metadata_df,
        num_rows="dynamic",
        column_config=build_column_config(field_defs),
        hide_index=True,
        use_container_width=True,
        key=f"metadata_editor_{st.session_state.editor_key}",
    )

    # Persist edits back to session state so re-renders don't discard them.
    st.session_state.metadata_df = edited_df

    # ── Step 1b: Metadata assistance ─────────────────────────────────────────
    with st.expander("Metadata assistance"):

        tab_ena, tab_tax, tab_envo, tab_fill, tab_import = st.tabs([
            "ENA autofill",
            "Taxonomy resolver",
            "ENVO term search",
            "Fill column",
            "Import quality files",
        ])

        # ── ENA autofill ──────────────────────────────────────────────────────
        with tab_ena:
            st.caption(
                "Look up the original metagenome in ENA using the accession(s) in "
                "`sample derived from` and autofill environmental metadata. "
                "Fills: `metagenomic source`, `isolation_source`, `collection date`, "
                "`geographic location (latitude/longitude)`, "
                "`broad-scale environmental context`, `local environmental context`, "
                "`environmental medium`, `geographic location (country and/or sea)`. "
                "Only empty cells are overwritten — existing values are preserved."
            )

            derived_col = st.session_state.metadata_df.get(
                "sample derived from", pd.Series(dtype="string")
            )
            unique_accs = sorted({
                str(a).strip()
                for a in derived_col.dropna()
                if str(a).strip() not in ("", "<NA>", "None", "nan")
            })

            if unique_accs:
                st.info(
                    f"Found {len(unique_accs)} unique accession(s) in `sample derived from`: "
                    + ", ".join(f"`{a}`" for a in unique_accs[:6])
                    + ("…" if len(unique_accs) > 6 else "")
                )
            else:
                st.warning(
                    "No accessions found in `sample derived from`. "
                    "Fill in that column first, then come back here."
                )

            col_prev_input, col_prev_btn = st.columns([3, 1])
            with col_prev_input:
                preview_acc = st.text_input(
                    "Preview a single accession",
                    placeholder="e.g. ERS1234567 or SRS1981904",
                    key="ena_preview_acc",
                )
            with col_prev_btn:
                st.write("")
                preview_clicked = st.button(
                    "Preview",
                    key="btn_ena_preview",
                    use_container_width=True,
                )

            if preview_clicked:
                acc = preview_acc.strip()
                if not acc:
                    st.warning("Enter an accession to preview.")
                else:
                    with st.spinner(f"Querying ENA for {acc}…"):
                        raw = _fetch_ena_sample_metadata(acc)
                    if "_error" in raw:
                        st.error(f"Could not fetch metadata: {raw['_error']}")
                        st.session_state.pop("ena_preview_result", None)
                    else:
                        st.session_state.ena_preview_result = _attrs_to_mag_metadata(raw)

            preview_result = st.session_state.get("ena_preview_result")
            if preview_result:
                preview_rows = [
                    {"field": k, "value": v}
                    for k, v in preview_result.items()
                    if v
                ]
                if preview_rows:
                    st.dataframe(
                        pd.DataFrame(preview_rows),
                        hide_index=True,
                        use_container_width=True,
                    )
                else:
                    st.info("No fillable attributes found for this accession.")

            st.divider()

            if st.button(
                "Autofill from all accessions",
                key="btn_ena_autofill",
                type="primary",
                use_container_width=True,
                disabled=not unique_accs,
            ):
                df_mod = st.session_state.metadata_df.copy()
                cells_filled = 0
                failed_accs = []

                with st.spinner(
                    f"Fetching metadata for {len(unique_accs)} accession(s)…"
                ):
                    for acc in unique_accs:
                        raw = _fetch_ena_sample_metadata(acc)
                        if "_error" in raw:
                            failed_accs.append(acc)
                            continue
                        mapped = _attrs_to_mag_metadata(raw)
                        mask = df_mod["sample derived from"] == acc
                        for col, val in mapped.items():
                            if col not in df_mod.columns or not val:
                                continue
                            for idx in df_mod.index[mask]:
                                current = df_mod.at[idx, col]
                                if pd.isna(current) or str(current).strip() in (
                                    "", "<NA>", "None", "nan"
                                ):
                                    df_mod.at[idx, col] = val
                                    cells_filled += 1

                st.session_state.metadata_df = df_mod
                st.session_state.pop("validated_df", None)
                st.session_state.pop("ena_preview_result", None)
                st.session_state.editor_key += 1

                if cells_filled:
                    st.toast(f"Filled {cells_filled} cell(s) from ENA.", icon="✅")
                if failed_accs:
                    st.warning(
                        "Could not fetch metadata for: "
                        + ", ".join(f"`{a}`" for a in failed_accs)
                    )
                if not cells_filled and not failed_accs:
                    st.info("No empty cells to fill — all matching fields already have values.")
                st.rerun()

        # ── Taxonomy resolver ─────────────────────────────────────────────────
        with tab_tax:
            st.caption(
                "Search the ENA taxonomy database by organism name to find the correct "
                "scientific name and NCBI taxon ID."
            )
            tax_query = st.text_input(
                "Organism name",
                key="tax_query",
                placeholder="e.g. uncultured Firmicutes bacterium",
            )
            col_search, col_batch = st.columns(2)

            with col_search:
                if st.button("Search taxonomy", key="btn_tax_search", use_container_width=True):
                    if tax_query:
                        with st.spinner("Querying ENA taxonomy…"):
                            st.session_state.tax_results = _ena_taxonomy_search(tax_query)
                    else:
                        st.warning("Enter an organism name first.")

            with col_batch:
                if st.button(
                    "Batch resolve tax IDs",
                    key="btn_batch_tax",
                    use_container_width=True,
                    help=(
                        "For every row with `organism` filled but `tax_id` empty, "
                        "query the ENA taxonomy API and fill the best match."
                    ),
                ):
                    df_mod = st.session_state.metadata_df.copy()
                    resolved, unresolved = 0, []
                    with st.spinner("Resolving tax IDs…"):
                        for idx, row in df_mod.iterrows():
                            org = str(row.get("organism", "")).strip()
                            tid = str(row.get("tax_id", "")).strip()
                            if org and tid in ("", "<NA>", "None", "nan"):
                                hits = _ena_taxonomy_search(org)
                                if hits:
                                    exact = next(
                                        (
                                            h for h in hits
                                            if h.get("scientificName", "").lower() == org.lower()
                                        ),
                                        hits[0],
                                    )
                                    df_mod.at[idx, "tax_id"] = str(exact["taxId"])
                                    resolved += 1
                                else:
                                    unresolved.append(org)
                    st.session_state.metadata_df = df_mod
                    st.session_state.pop("validated_df", None)
                    st.session_state.editor_key += 1
                    if resolved:
                        st.toast(f"Resolved {resolved} tax ID(s).", icon="✅")
                    if unresolved:
                        st.warning(
                            f"Could not resolve {len(unresolved)} organism(s): "
                            + ", ".join(unresolved[:5])
                            + ("…" if len(unresolved) > 5 else "")
                        )
                    st.rerun()

            results = st.session_state.get("tax_results")
            if results is not None:
                if results:
                    res_df = pd.DataFrame([
                        {
                            "tax_id": r.get("taxId", ""),
                            "Scientific name": r.get("scientificName", ""),
                            "Rank": r.get("rank", ""),
                        }
                        for r in results[:10]
                    ])
                    st.dataframe(res_df, hide_index=True, use_container_width=True)

                    col_sel, col_fill = st.columns([3, 2])
                    with col_sel:
                        selected_idx = st.selectbox(
                            "Apply result",
                            options=range(len(results[:10])),
                            format_func=lambda i: (
                                f"{results[i].get('scientificName')} "
                                f"(taxId: {results[i].get('taxId')})"
                            ),
                            key="tax_select",
                        )
                    with col_fill:
                        st.write("")
                        if st.button("Fill all rows", key="btn_tax_fill", use_container_width=True):
                            chosen = results[selected_idx]
                            df_mod = st.session_state.metadata_df.copy()
                            df_mod["organism"] = str(chosen["scientificName"])
                            df_mod["tax_id"] = str(chosen["taxId"])
                            st.session_state.metadata_df = df_mod
                            st.session_state.pop("validated_df", None)
                            st.session_state.pop("tax_results", None)
                            st.session_state.editor_key += 1
                            st.toast("Filled organism and tax_id for all rows.", icon="✅")
                            st.rerun()
                else:
                    st.info("No results found. Try a broader search term.")

        # ── ENVO term search ──────────────────────────────────────────────────
        with tab_envo:
            st.caption(
                "Search the ENVO ontology for terms to use in "
                "`broad-scale environmental context`, `local environmental context`, "
                "and `environmental medium` fields."
            )
            envo_query = st.text_input(
                "Search term",
                key="envo_query",
                placeholder="e.g. soil, marine sediment, freshwater",
            )
            if st.button("Search ENVO", key="btn_envo_search"):
                if envo_query:
                    with st.spinner("Querying ENVO ontology…"):
                        st.session_state.envo_results = _envo_search(envo_query)
                else:
                    st.warning("Enter a search term first.")

            envo_results = st.session_state.get("envo_results")
            if envo_results is not None:
                if envo_results:
                    for r in envo_results:
                        col_id, col_label, col_desc = st.columns([2, 3, 4])
                        with col_id:
                            st.code(r["obo_id"])
                        with col_label:
                            st.write(r["label"])
                        with col_desc:
                            st.caption(r["description"])
                    st.caption(
                        "Copy the ENVO ID (e.g. `ENVO:00002030`) directly into the metadata table."
                    )
                else:
                    st.info("No results found.")

        # ── Fill column ───────────────────────────────────────────────────────
        with tab_fill:
            st.caption(
                "Apply a single value across an entire column — useful for study-wide "
                "constants such as `platform`, `assembly software`, or `collection date`."
            )
            fillable_cols = [c for c in st.session_state.metadata_df.columns if c != "sample_name"]
            fill_col = st.selectbox("Column", options=fillable_cols, key="fill_col")
            fill_empty_only = st.checkbox("Fill empty cells only", value=True, key="fill_empty_only")

            field_def = field_defs.get(fill_col, {})
            if field_def.get("type") == "enum":
                fill_val = st.selectbox("Value", options=field_def["enum"], key="fill_val_enum")
            else:
                fill_val = st.text_input("Value", key="fill_val_text")

            if st.button("Apply to column", key="btn_fill_apply", type="primary"):
                df_mod = st.session_state.metadata_df.copy()
                if fill_empty_only:
                    mask = df_mod[fill_col].isna() | (
                        df_mod[fill_col].astype(str).str.strip().isin(["", "<NA>", "None", "nan"])
                    )
                    df_mod.loc[mask, fill_col] = fill_val
                else:
                    df_mod[fill_col] = fill_val
                st.session_state.metadata_df = df_mod
                st.session_state.pop("validated_df", None)
                st.session_state.editor_key += 1
                st.toast(f"Applied value to `{fill_col}`.", icon="✅")
                st.rerun()

        # ── Import quality files ──────────────────────────────────────────────
        with tab_import:
            st.caption(
                "Auto-populate metadata columns from bioinformatics tool outputs. "
                "Only empty cells are overwritten — existing values are preserved."
            )
            col_checkm, col_gtdbtk = st.columns(2)

            with col_checkm:
                col_title, col_ex1, col_ex2 = st.columns([3, 2, 2])
                with col_title:
                    st.markdown("**CheckM / CheckM2**")
                with col_ex1:
                    checkm1_path = EXAMPLES_DIR / "checkm_example.tsv"
                    if checkm1_path.exists():
                        st.download_button(
                            "CheckM example",
                            data=checkm1_path.read_bytes(),
                            file_name="checkm_example.tsv",
                            mime="text/tab-separated-values",
                            use_container_width=True,
                            help="Download an example CheckM v1 output (storage.tsv format).",
                        )
                with col_ex2:
                    checkm2_path = EXAMPLES_DIR / "checkm2_example.tsv"
                    if checkm2_path.exists():
                        st.download_button(
                            "CheckM2 example",
                            data=checkm2_path.read_bytes(),
                            file_name="checkm2_example.tsv",
                            mime="text/tab-separated-values",
                            use_container_width=True,
                            help="Download an example CheckM2 output (quality_report.tsv format).",
                        )
                st.caption("Fills: `completeness score`, `contamination score`, `completeness software`")
                checkm_file = st.file_uploader(
                    "quality_report.tsv or storage.tsv",
                    type=["tsv", "txt"],
                    key="checkm_upload",
                )
                if checkm_file:
                    parsed_qc = _parse_checkm_file(checkm_file)
                    if parsed_qc is None:
                        st.error("Unrecognised format. Expected CheckM or CheckM2 output.")
                    elif st.button("Apply CheckM data", key="btn_checkm"):
                        df_mod = _merge_into_metadata(st.session_state.metadata_df, parsed_qc)
                        matched = int(parsed_qc["sample_name"].isin(df_mod["sample_name"]).sum())
                        st.session_state.metadata_df = df_mod
                        st.session_state.pop("validated_df", None)
                        st.session_state.editor_key += 1
                        st.toast(f"Applied quality scores for {matched} sample(s).", icon="✅")
                        st.rerun()

            with col_gtdbtk:
                col_title, col_ex = st.columns([3, 2])
                with col_title:
                    st.markdown("**GTDB-Tk**")
                with col_ex:
                    gtdbtk_path = EXAMPLES_DIR / "gtdbtk_example.tsv"
                    if gtdbtk_path.exists():
                        st.download_button(
                            "GTDB-Tk example",
                            data=gtdbtk_path.read_bytes(),
                            file_name="gtdbtk_example.tsv",
                            mime="text/tab-separated-values",
                            use_container_width=True,
                            help="Download an example GTDB-Tk summary TSV (bac120 format).",
                        )
                st.caption("Fills: `organism` — use *Taxonomy resolver* afterwards to auto-fill `tax_id`")
                gtdbtk_file = st.file_uploader(
                    "gtdbtk.bac120.summary.tsv or gtdbtk.ar53.summary.tsv",
                    type=["tsv"],
                    key="gtdbtk_upload",
                )
                if gtdbtk_file:
                    parsed_gtdb = _parse_gtdbtk_file(gtdbtk_file)
                    if parsed_gtdb is None:
                        st.error("Unrecognised format. Expected GTDB-Tk summary TSV.")
                    elif st.button("Apply GTDB-Tk data", key="btn_gtdbtk"):
                        df_mod = _merge_into_metadata(st.session_state.metadata_df, parsed_gtdb)
                        matched = int(parsed_gtdb["sample_name"].isin(df_mod["sample_name"]).sum())
                        st.session_state.metadata_df = df_mod
                        st.session_state.pop("validated_df", None)
                        st.session_state.editor_key += 1
                        st.toast(
                            f"Applied organism names for {matched} sample(s). "
                            "Run Taxonomy resolver to fill tax IDs.",
                            icon="✅",
                        )
                        st.rerun()

    col_validate, col_reset = st.columns([4, 1])

    with col_reset:
        if st.button("Reset table", use_container_width=True, help="Clear all rows and start over."):
            st.session_state.metadata_df = initialize_empty_dataframe(field_defs)
            st.session_state.pop("tsv_filename", None)
            st.session_state.pop("validated_df", None)
            st.session_state.editor_key += 1
            st.rerun()

    with col_validate:
        validate_clicked = st.button(
            "Validate metadata",
            type="primary",
            use_container_width=True,
        )

    if validate_clicked:

        non_empty = edited_df.dropna(how="all")

        if edited_df.empty or non_empty.empty:
            st.error("Metadata table cannot be empty.")
            st.stop()

        if len(edited_df) > 1000:
            st.error(
                f"Submission is limited to 1000 rows. "
                f"Your table has {len(edited_df)} rows."
            )
            st.stop()

        error_df = validate_dataframe(edited_df, field_defs)

        if not error_df.empty:
            st.error(f"{len(error_df)} validation error(s) found:")
            st.dataframe(
                error_df,
                hide_index=True,
                use_container_width=True,
            )
            st.stop()

        st.success(
            f"All {len(edited_df)} sample(s) validated successfully."
        )

        st.session_state.validated_df = edited_df

    if "validated_df" not in st.session_state:
        return

    # ── Step 2: FASTA files ───────────────────────────────────────────────────
    st.divider()

    st.subheader("Step 2 — FASTA files")

    n_samples = len(st.session_state.validated_df)

    fasta_map = {}

    if use_example:
        st.caption(
            f"Example FASTA files are loaded automatically — "
            f"no upload needed when using example data."
        )

        # Build temp copies of example FASTAs so the originals are never deleted by the worker.
        if "_example_fasta_map" not in st.session_state or not all(
            Path(p).exists() for p in st.session_state._example_fasta_map.values()
        ):
            fasta_dir = EXAMPLES_DIR / "fasta"
            tmp_map = {}
            for fp in sorted(fasta_dir.glob("*.fasta.gz")):
                sample_name = fp.name.removesuffix(".fasta.gz")
                tmp = tempfile.NamedTemporaryFile(suffix=".fasta.gz", delete=False)
                tmp.write(fp.read_bytes())
                tmp.flush()
                tmp.close()
                tmp_map[sample_name] = str(Path(tmp.name).resolve())
            st.session_state._example_fasta_map = tmp_map

        fasta_map = {k: Path(v) for k, v in st.session_state._example_fasta_map.items()}
        names = ", ".join(f"`{k}.fasta.gz`" for k in sorted(fasta_map))
        st.success(f"Example FASTA files loaded: {names}")

    else:
        st.caption(
            f"Upload one `.fasta.gz` file per sample. "
            f"Expected {n_samples} file(s) — filenames must match the `sample_name` column."
        )

        uploaded_fastas = st.file_uploader(
            "Upload FASTA.GZ files",
            type=["gz"],
            accept_multiple_files=True,
        )

        if uploaded_fastas:

            try:
                fasta_map = persist_fastas_temp(uploaded_fastas)
            except Exception as e:
                st.error(str(e))
                st.stop()

            expected = set(
                st.session_state.validated_df["sample_name"].dropna()
            )
            uploaded = set(fasta_map)
            missing = expected - uploaded
            extra = uploaded - expected

            if missing:
                st.error(
                    f"Missing FASTA files for: {', '.join(sorted(missing))}"
                )
                st.stop()

            if extra:
                st.warning(
                    f"Extra FASTA files not in the metadata (will be ignored): "
                    f"{', '.join(sorted(extra))}"
                )

            st.success(
                f"All {len(fasta_map)} FASTA file(s) uploaded and matched successfully."
            )

    if not fasta_map:
        return

    # ── Step 3: ENA submission ────────────────────────────────────────────────
    st.divider()
    st.subheader("Step 3 — ENA submission")

    study_mode = st.radio(
        "Submission mode",
        ["Create new study", "Existing study accession"],
        horizontal=True,
    )

    notification_container = st.container()

    with st.form("submission_form"):

        if study_mode == "Create new study":

            study_name = st.text_input("Study name")
            study_title = st.text_input("Study title")
            study_description = st.text_area("Study description")
            study_accession = None

        else:

            study_accession = st.text_input("Study accession")
            study_name = None
            study_title = None
            study_description = None

        col_user, col_pass = st.columns(2)

        with col_user:
            ena_user = st.text_input("ENA Webin username")

        with col_pass:
            ena_password = st.text_input(
                "ENA Webin password",
                type="password"
            )

        portal = st.radio(
            "Submission portal",
            ["Testing", "Production"],
            horizontal=True,
            help="Use the Testing portal before Production to validate your submission."
        )

        notification_email = st.text_input(
            "Notification email (optional)",
            help="Enter your email to receive a notification when the submission completes."
        )

        submitted = st.form_submit_button(
            "Submit to ENA",
            type="primary",
            use_container_width=True,
        )

    if submitted:

        if study_mode == "Create new study":

            if not study_name:
                with notification_container:
                    st.error("Study name is required.")
                st.stop()

            if (
                len(study_title or "") < 20
                or len(study_description or "") < 20
            ):
                with notification_container:
                    st.error(
                        "Study title and description "
                        "must each be at least 20 characters."
                    )
                st.stop()

        if not ena_user or not ena_password:
            with notification_container:
                st.error(
                    "Please enter a valid ENA Webin username and password."
                )
            st.stop()

        submission = {
            "study_name": study_name,
            "study_title": study_title,
            "study_description": study_description,
            "study_accession": study_accession,
            "ena_user": ena_user,
            "ena_password": ena_password,
            "portal": portal,
        }

        fasta_map_str = {k: str(v) for k, v in fasta_map.items()}

        df_records = pl.from_pandas(
            st.session_state.validated_df
        ).to_dicts()

        fn_kwargs = {
            "df_records": df_records,
            "submission": submission,
            "fasta_map_str": fasta_map_str,
        }

        if notification_email:
            fn_kwargs["email"] = notification_email

        job_id = enqueue_task(submission_task, fn_kwargs)

        with notification_container:
            st.success("Submission queued successfully!")
            job_submitted_dialog(job_id)

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    runUI()
