import streamlit as st
import pandas as pd
import re
import xml.etree.ElementTree as ET


CHECKLIST_XML = "../ERC000047.xml"


def load_fields_from_xml(xml_path: str) -> dict:
    tree = ET.parse(xml_path)
    root = tree.getroot()

    fields = {}

    for field in root.findall(".//FIELD"):
        
        name = field.findtext("NAME")          # ← FIX
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
                    "expected": "MANDATORY FIELD"
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
    df_empty = pd.DataFrame(columns=field_defs.keys())

    for col in df_empty.columns:
        df_empty[col] = df_empty[col].astype("string")

    df_empty = pd.DataFrame(
        [{col: None for col in field_defs.keys()}],
        dtype="string"
    )

    return df_empty

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
                st.success("All fields are valid and ENA-compliant. Proceed for submission.")
                st.session_state.submission = edited_df
            else:
                st.error(f"{len(error_df)} validation error(s) detected.")
                st.dataframe(error_df, hide_index=True, width="stretch")
                st.stop()

    if "submission" in st.session_state:
        st.subheader("Submission")

        st.dataframe(st.session_state.submission)

if __name__ == "__main__":
    runUI()
