# app.py — trechos relevantes

import streamlit as st
from streamlit_option_menu import option_menu
import utils, modules
import subprocess, os
from utils.tasks import manager
from datetime import datetime

def clear_cache():
    keys = list(st.session_state.keys())
    for key in keys:
        if key != "cookie":
            st.session_state.pop(key)

@st.dialog("ℹ️ Use notice", width="large")
def cookie_dialog():
    st.markdown(
        """
        This web server uses **session cookies solely** to ensure proper functionality.

        No personal tracking or persistent cookies are employed.

        This platform is released under the [MIT license](https://opensource.org/licenses/MIT). **Free for academic and commercial use**.
        """
    )

    st.session_state["cookie"] = True

def runUI():
    st.set_page_config(page_title = "NFDI MAG2ENA", page_icon = "imgs/mag2ena_logo.png", initial_sidebar_state = "expanded", layout="wide")

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
        modules.home.runUI()
        clear_cache()

    elif page == "Submit":
        modules.submit.runUI()
        # clear_cache()

    elif page == "Jobs":
        modules.jobs.runUI()

    elif page == "About & Help":
        modules.about.runUI()
        clear_cache()

    # Show dialog once per session
    if "cookie" not in st.session_state:
        cookie_dialog()

    st.markdown(
        f"""
        <hr>
        <div style="text-align:center; font-size: 0.9em;">
        © {datetime.now().year} NFDI MAG2ENA — Released under the 
        <a href="https://opensource.org/licenses/MIT" target="_blank">MIT License</a>. Free for academic and commercial use.
        </div>
        <br>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    runUI()
