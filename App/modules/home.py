# modules/home.py
import base64
import pandas as pd
import streamlit as st
from utils.css_injection import inject_css

def _load_logo_b64(path: str) -> str:
		with open(path, "rb") as f:
				return base64.b64encode(f.read()).decode("utf-8")

def runUI():
		inject_css()

		# Hero
		logo_b64 = _load_logo_b64("imgs/logo.png")
		st.markdown(
				f"""
				<div class="container-max">
					<section class="hero">
						<img src="data:image/png;base64,{logo_b64}" alt="logo" width="110" />
						<div class="hero-title">NFDI ENA Submission Tool</div>
						<div class="hero-sub">Validate metadata and prepare metagenome-assembled genome (MAG) submissions.</div>
						<div class="badge">Genomic Standards Consortium package for MAGs (MIMAGS) supported.</div>
					</section>
				</div>
				""",
				unsafe_allow_html=True,
		)
		st.divider()

		# Features (cards)
		st.markdown(
				"""
				<div class="container-max section">
					<div class="h2">✨ Features</div>
					<div class="cards-3">
						<div class="card">
							<h4>Checklist-aware validation</h4>
							<ul class="list">
								<li>Dynamic parsing of ENA XML checklists</li>
								<li>Mandatory field verification</li>
								<li>Regex and controlled vocabulary validation</li>
							</ul>
						</div>
						<div class="card">
							<h4>MAG metadata processing</h4>
							<ul class="list">
								<li>TSV metadata table support</li>
								<li>Automatic FASTA.gz discovery</li>
								<li>Batch processing for large MAG collections</li>
							</ul>
						</div>
						<div class="card">
							<h4>Automated ENA submission</h4>
							<ul class="list">
								<li>Automatic SAMPLE and PROJECT XML generation</li>
								<li>Webin-CLI manifest creation and submission</li>
								<li>Accession recovery and submission logging</li>
							</ul>
						</div>
					</div>
				</div>
				""",
				unsafe_allow_html=True,
		)
		st.divider()

		# Workflow (steps)
		st.markdown(
				"""
				<div class="container-max section">
					<div class="h2">🔄 Workflow</div>
					<div class="timeline">
						<div class="step"><b>Prepare</b> your metadata (or start from our template).</div>
						<div class="step"><b>Open the editor</b>: create rows or upload TSV.</div>
						<div class="step"><b>Fix issues</b> flagged by the validator (required fields, formats, ontologies).</div>
						<div class="step"><b>Download</b> a clean TSV ready for ENA submission.</div>
					</div>
				</div>
				""",
				unsafe_allow_html=True,
		)
		st.divider()

		# Template download
		st.markdown('<div class="container-max section"><div class="h3 pad-top">⬇️ Download template</div></div>', unsafe_allow_html=True)

		with open("../examples/metadata.tsv", "rb") as f:
			st.download_button(
					label="Download metadata_template.tsv",
					data=f,
					file_name="metadata_template.tsv",
					mime="text/tab-separated-values",
					use_container_width=True,
			)
		st.divider()

		# # CTA
		# st.markdown('<div class="container-max section"><div class="h2">✅ Ready to validate & submit?</div></div>', unsafe_allow_html=True)
		# try:
		# 		st.page_link("pages/1_Validate_and_Submit.py", label="Go to Validate & Submit", icon="✅")
		# except Exception:
		# 		st.markdown("> Use the left menu to open **Create & Validate Metadata**.")

		st.markdown(
				"""
				**References**  
				- [GSC MIMAGS - Checklist: ERC000047](https://www.ebi.ac.uk/ena/browser/view/ERC000047)  
				- [MIXS Term Browser](https://w3id.org/mixs/)  
				- [ENA Submission Portal](https://www.ebi.ac.uk/ena/browser/submit)
				"""
		)

if __name__ == "__main__":
		runUI()
