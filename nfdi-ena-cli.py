#!/usr/bin/env python3

import argparse
import polars as pl
import re
import xml.etree.ElementTree as ET
import gzip
import tempfile
from pathlib import Path
import shutil
import requests
import subprocess
import os
from tqdm import tqdm
import time

# -----------------------------
# XML CHECKLIST
# -----------------------------
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
        "regex": re.compile(r"^(?:0?\.[0-9]*[1-9][0-9]*|[1-9][0-9]*(?:\.[0-9]+)?)$"),
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

# -----------------------------
# VALIDATION
# -----------------------------
def validate_dataframe(df: pl.DataFrame, field_defs: dict) -> None:
    errors = []
    # Add a temporary index column to track row numbers
    df_with_idx = df.with_row_index(offset=1)

    for col in df.columns:
        if col not in field_defs:
            continue

        field = field_defs[col]

        # 1. Mandatory Check
        if field["mandatory"]:
            # Find rows where value is null or empty string
            invalid_rows = df_with_idx.filter(
                pl.col(col).is_null() | (pl.col(col).str.strip_chars() == "")
            ).select("index").to_series().to_list()
            
            if invalid_rows:
                errors.append(f"Column '{col}': empty at rows {invalid_rows}")

        # 2. Regex Check
        if field["type"] == "regex":
            pattern = field["regex"].pattern
            # Find rows that don't match (and aren't null, handled above)
            invalid_rows = df_with_idx.filter(
                pl.col(col).is_not_null() & 
                (pl.col(col).str.strip_chars() != "") &
                ~pl.col(col).str.contains(pattern)
            ).select("index").to_series().to_list()
            
            if invalid_rows:
                errors.append(f"Column '{col}': regex mismatch at rows {invalid_rows}")

        # 3. Enum Check
        if field["type"] == "enum":
            invalid_rows = df_with_idx.filter(
                pl.col(col).is_not_null() & 
                (pl.col(col).str.strip_chars() != "") &
                ~pl.col(col).is_in(field["enum"])
            ).select("index").to_series().to_list()
            
            if invalid_rows:
                errors.append(f"Column '{col}': invalid choice at rows {invalid_rows}")

    if errors:
        raise ValueError("\n".join(errors))
# -----------------------------
# FASTA DISCOVERY
# -----------------------------
def collect_fastas(fasta_dir: Path) -> dict[str, Path]:
    fasta_map = {}
    for f in fasta_dir.glob("*.fasta.gz"):
        fasta_map[f.stem.replace(".fasta", "")] = f.resolve()
    return fasta_map

# -----------------------------
# SUBMISSION
# -----------------------------
def build_and_submit(df: pl.DataFrame, submission: dict, fasta_map: dict):

    df = df.with_columns(pl.lit("ERC000047").alias("ENA-CHECKLIST"))
    samples_submitted = 0
    samples_error = 0
    project_accession = submission.get("study_accession")
    batch_size = 1_000

    RESERVED_COLUMNS = {
        "sample_name",
        "organism",
        "tax_id",
        "ENA-CHECKLIST",
    }

    logs_path = "logs"

    if os.path.exists(logs_path):
        shutil.rmtree("logs", ignore_errors=True)

    os.makedirs(logs_path, exist_ok=True)

    for offset in tqdm(range(0, len(df), batch_size), desc=f"Processing ENA submission batches ({batch_size} samples per batch)"):

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
                "alias": str(row["sample_name"])
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
            add_attr("assembly software", row["assembly software"])
            

            # -----------------------------
            # AUTO-ADD user-provided columns
            # -----------------------------
            for col, value in row.items():
                if col in RESERVED_COLUMNS:
                    continue

                # Skip columns already explicitly added
                if col in {
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
                    "genome coverage"
                }:
                    continue

                if value is None or str(value).strip() == "":
                    continue

                add_attr(col, value)
            
            add_attr("ENA-CHECKLIST", row["ENA-CHECKLIST"])

        xml_bytes = ET.tostring(root, encoding="UTF-8", xml_declaration=True)

        # --- Submit via POST ---
        if submission["portal"] == "test":
            url = "https://wwwdev.ebi.ac.uk/ena/submit/webin-v2/submit/queue"
        elif submission["portal"] == "prod":
            url = "https://www.ebi.ac.uk/ena/submit/webin-v2/submit/queue"

        auth = (submission["ena_user"], submission["ena_password"])
        
        headers = {"Accept": "application/json"}

        files = {
            "file": ("submit.xml", xml_bytes, "text/xml")
        }

        response = requests.post(url, headers=headers, files=files, auth=auth).json()

        poll_url = response["_links"]["poll"]["href"]

        response = requests.get(poll_url, auth=auth)

        while response.status_code != 200:
            # print("Metadata being processed on ENA...")
            time.sleep(5)
            response = requests.get(poll_url, auth=auth)

        xml_text = response.text

        with open(f"logs/log_{offset}.xml", "w", encoding="utf-8") as f:
            f.write(xml_text)

        root = ET.fromstring(xml_text)

        alias_to_accession = {}

        # Get accessions from successfully created samples
        for sample in root.findall(".//SAMPLE"):
            accession = sample.get("accession")
            if accession:
                alias_to_accession[sample.get("alias")] = accession

        error_regex = re.compile(r'alias: "(.+?)".*accession: "(.+?)"')
        for err in root.findall(".//ERROR"):
            error_msg = err.text
            match = error_regex.search(error_msg)
            if match:
                alias, accession = match.groups()
                alias_to_accession[alias] = accession
                print(f"Found existing sample: {alias} -> {accession}")
            else:
                print(f"Submission Error: {error_msg}")

        if not project_accession:
            for project in root.findall(".//PROJECT"):
                project_accession = project.get("accession")

        for alias, sample_accession in alias_to_accession.items():
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
                chromosome_list = f"{last_header}\t{alias}\tchromosome"
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
                    "java", "-jar", "App/webin-cli-9.0.1.jar",
                    "-username", auth[0], "-password", auth[1],
                    "-context", "genome", "-manifest", manifest_path,
                    "-submit"
                ]
                
                if submission["portal"] == "test":
                    cmd.append("-test")

                result = subprocess.run(cmd, capture_output=True, text=True)
                success = "successfully" in result.stdout
                
                with open("logs/success.txt" if success else "logs/error.txt", "a") as f:
                    f.write(f"SAMPLE : {alias}\n{result.stdout}")
                
                if success:
                    samples_submitted += 1
                else:
                    samples_error += 1
            finally:
                os.remove(manifest_path)
                if chromosome_gz_path and os.path.exists(chromosome_gz_path):
                    os.remove(chromosome_gz_path)

    print(f"Submitted successfully: {samples_submitted}, Errors: {samples_error}")

# -----------------------------
# MAIN
# -----------------------------
def main():
    print(r'''
#################################################################################################################################################################################
#################################################################################################################################################################################
##  _____   __________________________   ______________   ________       ________      ______            _____              _____                   ________           ______  ##
##  ___  | / /__  ____/__  __ \___  _/   ___  ____/__  | / /__    |      __  ___/___  ____  /________ ______(_)________________(_)____________      ___  __/______________  /  ##
##  __   |/ /__  /_   __  / / /__  /     __  __/  __   |/ /__  /| |      _____ \_  / / /_  __ \_  __ `__ \_  /__  ___/_  ___/_  /_  __ \_  __ \     __  /  _  __ \  __ \_  /   ## 
##  _  /|  / _  __/   _  /_/ /__/ /      _  /___  _  /|  / _  ___ |      ____/ // /_/ /_  /_/ /  / / / / /  / _(__  )_(__  )_  / / /_/ /  / / /     _  /   / /_/ / /_/ /  /    ##  
##  /_/ |_/  /_/      /_____/ /___/      /_____/  /_/ |_/  /_/  |_|      /____/ \__,_/ /_.___//_/ /_/ /_//_/  /____/ /____/ /_/  \____//_/ /_/      /_/    \____/\____//_/     ##   
##                                                                                                                                                                             ##   
#################################################################################################################################################################################
#################################################################################################################################################################################
	''')
    parser = argparse.ArgumentParser(description="ENA MAG submission CLI")

    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--fasta-dir", required=True, type=Path)
    parser.add_argument("--ena-user", required=True)
    parser.add_argument("--ena-password", required=True)
    parser.add_argument("--portal", choices=["test", "prod"], default="test")
    parser.add_argument("--study-accession")
    parser.add_argument("--study-name")
    parser.add_argument("--study-title")
    parser.add_argument("--study-description")

    args = parser.parse_args()

    field_defs = load_fields_from_xml("checklists/ERC000047.xml")

    df = pl.read_csv(args.metadata, separator="\t", infer_schema_length=0)
    validate_dataframe(df, field_defs)

    fasta_map = collect_fastas(args.fasta_dir)
    missing = set(df["sample_name"]) - set(fasta_map)

    if missing:
        raise RuntimeError(f"Missing FASTA files for: {', '.join(missing)}")

    submission = {
        "study_accession": args.study_accession,
        "study_name": args.study_name,
        "study_title": args.study_title,
        "study_description": args.study_description,
        "ena_user": args.ena_user,
        "ena_password": args.ena_password,
        "portal": args.portal,
    }

    build_and_submit(df, submission, fasta_map)

if __name__ == "__main__":
    main()