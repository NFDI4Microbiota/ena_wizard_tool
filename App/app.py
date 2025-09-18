# app.py — trechos relevantes

import streamlit as st
from streamlit_option_menu import option_menu
import utils, modules
import subprocess, os

def runUI():
    st.set_page_config(page_title = "ENA Wizard Tool", page_icon = "imgs/icon.png", initial_sidebar_state = "expanded", layout="wide")

    utils.inject_css()

    page = option_menu(
        None,
        ["Home", "Create & Validate Metadata", "Submission Jobs", "About & Help"],
        icons=["house", "file-earmark-check", "gear-wide", "info-circle"],
        menu_icon="cast",
        default_index=0,
        orientation="horizontal"
    )

    if "queue_started" not in st.session_state:
        st.session_state.queue_started = False

    if page == "Home":
        modules.home.runUI()
        if "job_path" in st.session_state:
            del st.session_state["job_path"]

    elif page == "Create & Validate Metadata":
        modules.create_validate_metadata.runUI()
        if "job_path" in st.session_state:
            del st.session_state["job_path"]

    elif page == "Submission Jobs":
        modules.jobs.runUI()

    elif page == "About & Help":
        modules.about.runUI()
        if "job_path" in st.session_state:
            del st.session_state["job_path"]

if __name__ == "__main__":
    runUI()
