# utils/css_injection.py
import base64
from pathlib import Path
import streamlit as st

@st.cache_data
def _b64(path: str) -> str:
    p = Path(path)
    return base64.b64encode(p.read_bytes()).decode()

def inject_css():
    root = Path(__file__).resolve().parents[1]  # raiz do app
    css_path = root / "css" / "style.css"
    logo_path = root / "imgs" / "logo.png"

    # injeta background da sidebar + todo o style.css
    st.markdown(
        f"""
        <style>
          [data-testid="stSidebar"] {{
            background-image: url("data:image/png;base64,{_b64(str(logo_path))}");
            padding-top: 0px;
            background-repeat: no-repeat;
            background-position: 50% 2%;
            margin-top: -0.2%;
            background-size: 275px;
          }}
          {css_path.read_text()}
        </style>
        """,
        unsafe_allow_html=True,
    )
