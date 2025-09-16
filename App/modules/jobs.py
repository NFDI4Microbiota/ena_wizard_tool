import streamlit as st
import polars as pl
import pandas as pd

def runUI():
    def get_job_example():
        st.session_state["job_input"] = "SuKEVriL0frtqHPU"

    with st.container(border=True):
        col1, col2 = st.columns([9, 1])

        with col2:
            example_job = st.button("Example", use_container_width=True, on_click=get_job_example)

        with st.form("jobs_submit", border=False):
            job_id = st.text_input("Enter Job ID", key="job_input")

            submitted = st.form_submit_button("Submit", use_container_width=True,  type="primary")

