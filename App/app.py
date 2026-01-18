# app.py — trechos relevantes

import streamlit as st
from streamlit_option_menu import option_menu
import utils, modules
import subprocess, os
from datetime import datetime

def clear_cache():
    keys = list(st.session_state.keys())
    for key in keys:
        st.session_state.pop(key)

def runUI():
    st.set_page_config(page_title = "NFDI ENA Submission Tool", page_icon = "imgs/icon.png", initial_sidebar_state = "expanded", layout="wide")

    utils.inject_css()

    page = option_menu(
        None,
        ["Home", "Submit", "Jobs", "About & Help"],
        icons=["house", "file-earmark-check", "gear-wide", "info-circle"],
        menu_icon="cast",
        default_index=0,
        orientation="horizontal"
    )

    if page == "Home":
        clear_cache()
        modules.home.runUI()
        if "job_path" in st.session_state:
            del st.session_state["job_path"]

    elif page == "Submit":
        modules.submit.runUI()
        if "job_path" in st.session_state:
            del st.session_state["job_path"]

    elif page == "Jobs":
        clear_cache()
        modules.jobs.runUI()

    elif page == "About & Help":
        clear_cache()
        modules.about.runUI()
        if "job_path" in st.session_state:
            del st.session_state["job_path"]

    st.markdown(
        f"""
        <hr>
        <div style="text-align:center; font-size: 0.9em;">
        © {datetime.now().year} NFDI ENA Submission Tool — Released under the 
        <a href="https://opensource.org/licenses/MIT" target="_blank">MIT License</a>. Free for academic and commercial use.
        </div>
        <br>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    runUI()
