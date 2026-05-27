import streamlit as st
import pandas as pd
import polars as pl
import re
import xml.etree.ElementTree as ET
import gzip
import tempfile
from pathlib import Path
import os
import shutil
import subprocess
import requests
import time
from datetime import datetime

# =========================================================
# CONFIG
# =========================================================

CHECKLIST_XML = "../checklists/ERC000047.xml"
WEBIN_JAR = "../App/webin-cli-9.0.1.jar"
BATCH_SIZE = 1000

# =========================================================
# XML CHECKLIST
# =========================================================

def load_fields_from_xml(xml_path: str) -> dict:

    tree = ET.parse(xml_path)
    root = tree.getroot()

    fields = {
        "sample_name": {
            "label": "sample_name",
            "description": "Sample name (must match fasta filename)",
            "type": "free",
            "regex": None,
            "enum": None,
            "mandatory": True,
        },
        "organism": {
            "label": "organism",
            "description": "Scientific organism name",
            "type": "free",
            "regex": None,
            "enum": None,
            "mandatory": True,
        },
        "tax_id": {
            "label": "tax_id",
            "description": "NCBI taxonomy ID",
            "type": "free",
            "regex": None,
            "enum": None,
            "mandatory": True,
        },
    }

    for field in root.findall(".//FIELD"):

        label = field.findtext("LABEL")
        description = field.findtext("DESCRIPTION")

        mandatory = field.findtext("MANDATORY") == "mandatory"

        regex_elem = field.findtext(".//REGEX_VALUE")
        enum_elems = field.findall(".//TEXT_CHOICE_FIELD/TEXT_VALUE/VALUE")

        if regex_elem:

            fields[label] = {
                "label": label,
                "description": description,
                "type": "regex",
                "regex": re.compile(regex_elem),
                "enum": None,
                "mandatory": mandatory,
            }

        elif enum_elems:

            fields[label] = {
                "label": label,
                "description": description,
                "type": "enum",
                "regex": None,
                "enum": [e.text for e in enum_elems],
                "mandatory": mandatory,
            }

        else:

            fields[label] = {
                "label": label,
                "description": description,
                "type": "free",
                "regex": None,
                "enum": None,
                "mandatory": mandatory,
            }

    fields["genome coverage"] = {
        "label": "genome coverage",
        "description": "Estimated sequencing depth",
        "type": "regex",
        "regex": re.compile(
            r"^(?:0?\.[0-9]*[1-9][0-9]*|[1-9][0-9]*(?:\.[0-9]+)?)$"
        ),
        "enum": None,
        "mandatory": True,
    }

    fields["platform"] = {
        "label": "platform",
        "description": "Sequencing platform",
        "type": "free",
        "regex": None,
        "enum": None,
        "mandatory": True,
    }

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
                    "expected": "Mandatory field"
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
                        "expected": field["regex"].pattern
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
                required=field["mandatory"],
                help=field["description"]
            )

        else:

            column_config[name] = st.column_config.TextColumn(
                label=label,
                required=field["mandatory"],
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

    df = pd.read_csv(
        tsv_file,
        sep="\t",
        dtype="string"
    )

    df = df.reindex(columns=schema_cols)

    for col in df.columns:
        df[col] = df[col].astype("string")

    return df

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
# LOGGING
# =========================================================

def create_log_dir():

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    log_dir = Path(f"logs_{timestamp}")

    log_dir.mkdir(exist_ok=True)

    return log_dir

# =========================================================
# SUBMISSION
# =========================================================

def build_and_submit(df, submission, fasta_map):

    samples_submitted = 0
    samples_error = 0

    RESERVED_COLUMNS = {
        "sample_name",
        "organism",
        "tax_id",
        "ENA-CHECKLIST",
    }

    log_dir = create_log_dir()

    df = df.with_columns(
        pl.lit("ERC000047").alias("ENA-CHECKLIST")
    )

    project_accession = submission["study_accession"]

    progress = st.progress(0)

    status_box = st.empty()

    for offset in range(0, len(df), BATCH_SIZE):

        status_box.info(
            f"Processing batch {offset // BATCH_SIZE + 1}"
        )

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

        for row in df.slice(offset, BATCH_SIZE).iter_rows(named=True):

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

        xml_log = log_dir / f"log_{offset}.xml"

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

            base_manifest = f"""STUDY   {project_accession}
SAMPLE   {sample_accession}
ASSEMBLYNAME   {alias}
ASSEMBLY_TYPE   Metagenome-Assembled Genome (MAG)
COVERAGE   {df.filter(pl.col("sample_name") == alias)["genome coverage"].item()}
PROGRAM   {df.filter(pl.col("sample_name") == alias)["assembly software"].item()}
PLATFORM   {df.filter(pl.col("sample_name") == alias)["platform"].item()}
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

                os.remove(manifest_path)

                if chromosome_gz_path:
                    if os.path.exists(chromosome_gz_path):
                        os.remove(chromosome_gz_path)

        progress.progress(
            min((offset + BATCH_SIZE) / len(df), 1.0)
        )

    return {
        "submitted": samples_submitted,
        "errors": samples_error,
        "log_dir": log_dir
    }

# =========================================================
# UI
# =========================================================

def runUI():

    if not os.path.exists(WEBIN_JAR):
        st.error(f"Missing Webin CLI jar: {WEBIN_JAR}")
        st.stop()

    field_defs = load_fields_from_xml(CHECKLIST_XML)

    if "metadata_df" not in st.session_state:
        st.session_state.metadata_df = (
            initialize_empty_dataframe(field_defs)
        )

    uploaded_tsv = st.file_uploader(
        "Upload metadata TSV (optional)",
        type=["tsv"]
    )

    if uploaded_tsv:

        st.session_state.metadata_df = (
            load_tsv_into_schema(
                uploaded_tsv,
                field_defs
            )
        )

    st.subheader("Metadata table")

    edited_df = st.data_editor(
        st.session_state.metadata_df,
        num_rows="dynamic",
        column_config=build_column_config(field_defs),
        hide_index=True,
        width="stretch"
    )

    if st.button("Validate metadata"):

        if edited_df.empty:

            st.error("Metadata table cannot be empty.")
            st.stop()

        error_df = validate_dataframe(
            edited_df,
            field_defs
        )

        if not error_df.empty:

            st.error(
                f"{len(error_df)} validation error(s)"
            )

            st.dataframe(
                error_df,
                hide_index=True,
                width="stretch"
            )

            st.stop()

        st.success(
            "Metadata validated successfully."
        )

        st.session_state.validated_df = edited_df

    if "validated_df" not in st.session_state:
        return

    st.subheader("FASTA files")

    uploaded_fastas = st.file_uploader(
        "Upload FASTA.GZ files",
        type=["gz"],
        accept_multiple_files=True
    )

    fasta_map = {}

    if uploaded_fastas:

        try:

            fasta_map = persist_fastas_temp(
                uploaded_fastas
            )

        except Exception as e:

            st.error(str(e))
            st.stop()

        missing = (
            set(st.session_state.validated_df["sample_name"])
            - set(fasta_map)
        )

        if missing:

            st.error(
                f"Missing FASTA files for: {', '.join(missing)}"
            )

            st.stop()

        st.success(
            "All FASTA files uploaded successfully."
        )

    if not fasta_map:
        return

    st.subheader("ENA submission")

    study_mode = st.radio(
        "Submission mode",
        [
            "Create new study",
            "Existing study accession"
        ],
        horizontal=True
    )

    notification_container = st.container()

    with st.form("submission_form"):

        if study_mode == "Create new study":

            study_name = st.text_input("Study name")

            study_title = st.text_input("Study title")

            study_description = st.text_area(
                "Study description"
            )

            study_accession = None

        else:

            study_accession = st.text_input(
                "Study accession"
            )

            study_name = None
            study_title = None
            study_description = None

        ena_user = st.text_input(
            "ENA Webin username"
        )

        ena_password = st.text_input(
            "ENA Webin password",
            type="password"
        )

        portal = st.radio(
            "Submission portal",
            ["Testing", "Production"],
            horizontal=True,
            help="Use the Testing portal before the Production to validate your submission."
        )

        submitted = st.form_submit_button(
            "Submit",
            type="primary",
            use_container_width=True
        )

    if submitted:

        if study_mode == "Create new study":

            if not study_name:
                with notification_container:
                    st.error("Study name required.")
                st.stop()

            if (
                len(study_title) < 20
                or len(study_description) < 20
            ):
                with notification_container:
                    st.error(
                        "Study title and description "
                        "must be at least 20 characters."
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

        try:
            with st.spinner("Submitting to ENA..."):
                results = build_and_submit(
                    pl.from_pandas(
                        st.session_state.validated_df
                    ),
                    submission,
                    fasta_map
                )

            st.success(
                f"{results['submitted']} samples "
                f"submitted successfully."
            )

            if results["errors"] > 0:
                st.warning(
                    f"{results['errors']} samples "
                    f"had errors."
                )

            log_dir = results["log_dir"]

            st.subheader("Logs")

            for logfile in sorted(log_dir.glob("*")):

                with open(logfile, "rb") as f:

                    st.download_button(
                        label=f"Download {logfile.name}",
                        data=f.read(),
                        file_name=logfile.name,
                        use_container_width=True
                    )

        finally:
            for path in fasta_map.values():
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass

# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    runUI()