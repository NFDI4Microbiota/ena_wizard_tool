import streamlit as st
import pandas as pd
import polars as pl
import re
import xml.etree.ElementTree as ET
import gzip
from io import TextIOWrapper
from tqdm import tqdm
import requests
import tempfile
from pathlib import Path
import os
import subprocess

CHECKLIST_XML = "../ERC000047.xml"

def load_fields_from_xml(xml_path: str) -> dict:
    tree = ET.parse(xml_path)
    root = tree.getroot()

    fields = {"sample_name": {"label": "sample_name", 
                            "description": "Name of the sample. Name must be the same as the submitted fasta.gz file.", 
                            "type": "free",
                            "regex": None,
                            "enum": None,
                            "mandatory": True},
            "organism": {"label": "organism", 
                            "description": "Scientific name of the organism.", 
                            "type": "free",
                            "regex": None,
                            "enum": None,
                            "mandatory": True},
            "tax_id": {"label": "tax_id", 
                            "description": "NCBI Taxonomy ID of the organism.", 
                            "type": "free",
                            "regex": None,
                            "enum": None,
                            "mandatory": True},}

    for field in root.findall(".//FIELD"):
        label = field.findtext("LABEL") or name
        description = field.findtext("DESCRIPTION")

        mandatory = field.findtext("MANDATORY") == "mandatory"
        
        regex_elem = field.findtext(".//REGEX_VALUE")

        enum_elems = field.findall(".//TEXT_CHOICE_FIELD/TEXT_VALUE/VALUE")

        if regex_elem is not None:
            fields[label] = {
                "label": label,
                "description": description,
                "type": "regex",
                "regex": re.compile(regex_elem),
                "enum": None,
                "mandatory": mandatory
            }

        elif enum_elems:
            fields[label] = {
                "label": label,
                "description": description,
                "type": "enum",
                "regex": None,
                "enum": [e.text for e in enum_elems],
                "mandatory": mandatory
            }

        else:
            fields[label] = {
                "label": label,
                "description": description,
                "type": "free",
                "regex": None,
                "enum": None,
                "mandatory": mandatory
            }

    fields["genome coverage"] = {
        "label": "genome coverage",
        "description": "The estimated depth of sequencing coverage",
        "type": "regex",
        "regex": re.compile("^(?:0?\.[0-9]*[1-9][0-9]*|[1-9][0-9]*(?:\.[0-9]+)?)$"),
        "enum": None,
        "mandatory": True
    }

    fields["platform"] = {
        "label": "platform",
        "description": "The sequencing platform, or comma-separated list of platforms",
        "type": "free",
        "regex": None,
        "enum": None,
        "mandatory": True
    }

    return fields

def validate_dataframe(df: pd.DataFrame, field_defs: dict) -> pd.DataFrame:
    errors = []

    for col in df.columns:
        if col not in field_defs:
            continue

        field = field_defs[col]

        for idx, value in df[col].items():
            value_str = "" if pd.isna(value) else str(value).strip()

            # Mandatory check
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

def build_column_config(field_defs: dict) -> dict:
    column_config = {}

    for name, field in field_defs.items():
        label = f"{field['label']} *" if field["mandatory"] else field["label"]

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

def load_csv_into_schema(csv_file, field_defs: dict) -> pd.DataFrame:
    schema_cols = list(field_defs.keys())

    csv_df = pd.read_csv(csv_file)

    # Keep only allowed columns and add missing ones
    csv_df = csv_df.reindex(columns=schema_cols)

    # Force string dtype for Streamlit compatibility
    for col in csv_df.columns:
        csv_df[col] = csv_df[col].astype("string")

    return csv_df

def initialize_empty_dataframe(field_defs: dict) -> pd.DataFrame:
    df_empty = pd.DataFrame(field_defs.keys())

    for col in df_empty.columns:
        df_empty[col] = df_empty[col].astype("string")

    df_empty = pd.DataFrame(
        [{col: None for col in field_defs.keys()}],
        dtype="string"
    )

    return df_empty

def persist_fastas_temp(uploaded_files) -> dict[str, Path]:
    """
    Saves uploaded fasta.gz files to temporary disk files.
    Returns mapping: sample_name -> absolute fasta path.
    """
    fasta_map = {}

    for uf in uploaded_files:
        if not uf.name.endswith(".fasta.gz"):
            continue

        sample_name = uf.name.removesuffix(".fasta.gz")

        tmp = tempfile.NamedTemporaryFile(
            suffix=".fasta.gz",
            delete=False
        )

        tmp.write(uf.getbuffer())
        tmp.flush()
        tmp.close()

        fasta_map[sample_name] = Path(tmp.name).resolve()

    return fasta_map

def build_and_submit(df, submission, batch_size, fasta_map):

    samples_submitted, samples_error = 0, 0
    project_accession = submission["study_accession"]

    df = df.with_columns(
        pl.lit("ERC000047").alias("ENA-CHECKLIST")
    )

    for offset in tqdm(range(0, len(df), batch_size)):

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

        for row in df.slice(offset, batch_size).iter_rows(named=True):
            sample = ET.SubElement(sample_set, "SAMPLE", {
                "alias": str(row["sample_name"]),
                "center_name": ""
            })

            # Title
            ET.SubElement(sample, "TITLE").text = (
                "This sample represents a MAG derived from the metagenomic sample "
                + str(row["sample derived from"])
            )

            # SAMPLE_NAME
            sname = ET.SubElement(sample, "SAMPLE_NAME")
            ET.SubElement(sname, "TAXON_ID").text = str(row["tax_id"])
            ET.SubElement(sname, "SCIENTIFIC_NAME").text = str(row["organism"])

            # Attributes
            attrs = ET.SubElement(sample, "SAMPLE_ATTRIBUTES")

            def add_attr(tag, value, units=None):
                sa = ET.SubElement(attrs, "SAMPLE_ATTRIBUTE")
                ET.SubElement(sa, "TAG").text = tag
                ET.SubElement(sa, "VALUE").text = str(value)
                if units:
                    ET.SubElement(sa, "UNITS").text = units

            # Map columns → attributes
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

            add_attr("geographic location (latitude)", row["geographic location (latitude)"], "DD")
            add_attr("geographic location (longitude)", row["geographic location (longitude)"], "DD")

            add_attr("broad-scale environmental context", row["broad-scale environmental context"])
            add_attr("local environmental context", row["local environmental context"])
            add_attr("environmental medium", row["environmental medium"])
            add_attr("geographic location (country and/or sea)", row["geographic location (country and/or sea)"])

            # Assembly software
            add_attr("assembly software", row["assembly software"])

            # ENA checklist (constant here)
            add_attr("ENA-CHECKLIST", row["ENA-CHECKLIST"])

        xml_bytes = ET.tostring(root, encoding="UTF-8", xml_declaration=True)

        # --- Submit via POST ---
        if submission["portal"] == "Test portal":
            url = "https://wwwdev.ebi.ac.uk/ena/submit/webin-v2/submit"
        elif submission["portal"] == "Default":
            url = "https://www.ebi.ac.uk/ena/submit/webin-v2/submit"

        auth = (submission["ena_user"], submission["ena_password"])
        headers = {"Accept": "application/xml", "Content-Type": "application/xml"}

        xml_text = requests.post(url, headers=headers, data=xml_bytes, auth=auth).text

        with open(f"log_{offset}.xml", "w", encoding="utf-8") as f:
            f.write(xml_text)

        root = ET.fromstring(xml_text)

        if not project_accession:
            for project in root.findall("PROJECT"):
                project_accession = project.get("accession")

        samples = root.findall("SAMPLE")

        for sample in samples:
            sample_accession = sample.get("accession")
            alias = sample.get("alias")
            fasta_path = fasta_map[alias]

            # Count sequences and get last header
            seq_count = 0
            last_header = None
            
            with gzip.open(fasta_path, "rt") as f:
                for line in f:
                    if line.startswith(">"):
                        seq_count += 1
                        last_header = line[1:].strip()
                        if seq_count > 1:
                            break
            
            # Build manifest content
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
                chromosome_list = f"{last_header}\t{sample}\tchromosome"
                with tempfile.NamedTemporaryFile(mode="wb+", suffix=".gz", delete=False) as tmp_chromosome_gz:
                    with gzip.GzipFile(fileobj=tmp_chromosome_gz, mode="wb") as gz_file:
                        gz_file.write(chromosome_list.encode("utf-8"))
                    chromosome_gz_path = tmp_chromosome_gz.name
                base_manifest += f"\nCHROMOSOME_LIST   {chromosome_gz_path}"
            
            # Submit to ENA
            with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp_manifest:
                tmp_manifest.write(base_manifest)
                manifest_path = tmp_manifest.name
            
            try:
                cmd = [
                    "java", "-jar", "webin-cli-9.0.1.jar",
                    "-username", auth[0], "-password", auth[1],
                    "-context", "genome", "-manifest", manifest_path,
                    "-submit", 
                    "-test" if submission["portal"] == "Test portal" else ""
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                success = "successfully" in result.stdout
                
                with open("success.txt" if success else "error.txt", "a") as f:
                    f.write(f"SAMPLE : {alias}\n{result.stdout}")
                
                samples_submitted += 1
                if not success:
                    samples_error += 1
            finally:
                os.remove(manifest_path)
                if chromosome_gz_path and os.path.exists(chromosome_gz_path):
                    os.remove(chromosome_gz_path)

        # with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        #     process_func = partial(process_sample, root=root, project_accession=project_accession, df=df, auth=auth)
        #     results = list(executor.map(process_func, samples))
            
    print(f"{samples_submitted} samples submitted successfully. {samples_error} samples with errors.")

    for path in fasta_map.values():
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass

def runUI():
    field_defs = load_fields_from_xml(CHECKLIST_XML)

    uploaded_file = st.file_uploader(
        "Upload CSV file with metadata (optional)",
        type=["csv"],
        accept_multiple_files=False
    )

    st.subheader("Metadata table")

    st.session_state.metadata_df = initialize_empty_dataframe(field_defs)

    # Load CSV only once per upload
    if uploaded_file:
        st.session_state.metadata_df = load_csv_into_schema(
            uploaded_file,
            field_defs
        )

    column_config = build_column_config(field_defs)

    # Always render the editor
    edited_df = st.data_editor(
        st.session_state.metadata_df,
        num_rows="dynamic",
        column_config=column_config,
        width="stretch",
        hide_index=True
    )

    if st.button("Validate"):
        if edited_df.empty:
            st.error("Metadata table can't be empty!")
        else:
            error_df = validate_dataframe(edited_df, field_defs)

            if error_df.empty:
                st.success("All fields are valid and ENA-compliant. Proceed to submit fasta.gz files.")
                st.session_state.submission = edited_df
            else:
                st.error(f"{len(error_df)} validation error(s) detected.")
                st.dataframe(error_df, hide_index=True, width="stretch")
                st.stop()

    if "submission" in st.session_state:
        st.subheader("FASTA files")

        uploaded_files = st.file_uploader(
            label="Upload one or more fasta.gz files",
            type=["fasta.gz"],
            accept_multiple_files=True
        )

        if "fasta_map" not in st.session_state:
            fasta_map = persist_fastas_temp(uploaded_files)

            missing = set(st.session_state.submission["sample_name"]) - set(fasta_map)

            if missing:
                st.error(f"Missing FASTA files for samples: {', '.join(missing)}")
            else:
                st.success("All FASTA files uploaded and staged for submission.")
                st.session_state["fasta_map"] = fasta_map
            
        if "fasta_map" in st.session_state:
            st.subheader("ENA submission")

            study = st.radio(
                "Study for submission",
                ["Create study", "Provide study accession number"],
                horizontal=True,
                index=0,
            )

            with st.form("ena_submission_form", clear_on_submit=True):

                if study == "Create study":
                    col1, col2 = st.columns(2)

                    with col1:
                        study_name = st.text_input(
                            "Study name",
                            placeholder="Study-MAGs"
                        )

                    with col2:
                        study_title = st.text_input(
                            "Study title",
                            placeholder="Study for submitted MAGs"
                        )

                    study_description = st.text_area(
                        "Study description"
                    )
                    study_accession = None
                else:
                    study_accession = st.text_input(
                        "Study accession number"
                    )
                    study_name = None
                    study_title = None
                    study_description = None

                col_user1, col_user2 = st.columns(2)

                with col_user1:
                    ena_user = st.text_input("ENA Webin username")

                with col_user2:
                    ena_password = st.text_input(
                        "ENA Webin password",
                        type="password"
                    )

                portal = st.radio(
                    "Portal for submission",
                    ["Test portal", "Default"],
                    horizontal=True,
                    index=0,
                )

                submitted = st.form_submit_button(
                    "Submit",
                    type="primary",
                    use_container_width=True
                )
                
            if submitted:
                submission = {
                    "study_name": study_name,
                    "study_title": study_title,
                    "study_description": study_description,
                    "study_accession": study_accession,
                    "ena_user": ena_user,
                    "ena_password": ena_password,
                    "portal": portal,
                }

                build_and_submit(pl.from_pandas(st.session_state.submission), submission, 1000, st.session_state["fasta_map"])

                st.success("Submission successful.")

                with open("log_0.xml", "r", encoding="utf-8") as f:
                    xml_content = f.read()

                st.code(xml_content, language="xml")

        # st.dataframe(st.session_state.submission)

if __name__ == "__main__":
    runUI()
