import streamlit as st
import pandas as pd
import base64

def runUI():
    with open("imgs/logo.png", "rb") as file_:
        contents = file_.read()
        data_url = base64.b64encode(contents).decode("utf-8")

    st.markdown(f"""
        <div style='text-align: center;'>
            <img src="data:image/png;base64,{data_url}" alt="logo" width="400">
            <h5 style="color:gray">ENA Wizard Tool</h5>
        </div>
    """, unsafe_allow_html=True)

    st.info("""ENA Wizard Tool""")

    st.divider()

    st.markdown("""### Submission""", unsafe_allow_html=True)

    metadata_columns = [
        'sample_name',
        'experiment',
        'completeness score',
        'contamination score',
        'organism',
        'tax_id',
        'metagenomic source',
        'sample derived from',
        'project name',
        'completeness software',
        'binning software',
        'assembly quality',
        'binning parameters',
        'taxonomic identity marker',
        'isolation_source',
        'collection date',
        'geographic location (latitude)',
        'geographic location (longitude)',
        'broad-scale environmental context',
        'local environmental context',
        'environmental medium',
        'geographic location (country and/or sea)',
        'assembly software',
        'genome coverage',
        'platform',
        'ENA-CHECKLIST'
    ]

    technical_columns = [

    ]

    # Create a DataFrame with one empty row
    df_metadata = pd.DataFrame([[None] * len(metadata_columns)], columns=metadata_columns)

    st.markdown("""##### Metadata""", unsafe_allow_html=True)

    edited_metadata = st.data_editor(df_metadata, hide_index=True)

    

# Run the Streamlit app
if __name__ == "__main__":
    runUI()