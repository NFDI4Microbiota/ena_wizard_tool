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
						<div class="hero-title">ENA MAG Submission Wizard</div>
						<div class="hero-sub">From assembled bins to ENA accession numbers — without writing a single line of XML or running Webin-CLI by hand.</div>
						<div class="badge">Genomic Standards Consortium package for MAGs (MIMAGS) supported</div>
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
					<div class="h2">✨ What it does for you</div>
					<div class="cards-3">
						<div class="card">
							<h4>Auto-fill from your tools</h4>
							<ul class="list">
								<li>Import completeness &amp; contamination directly from CheckM or CheckM2 output</li>
								<li>Import organism names from GTDB-Tk summary files</li>
								<li>Resolve NCBI taxon IDs in batch against the ENA taxonomy API</li>
								<li>Search the ENVO ontology for environmental context terms</li>
							</ul>
						</div>
						<div class="card">
							<h4>Catch errors before ENA does</h4>
							<ul class="list">
								<li>Validates every cell against the live ERC000047 checklist</li>
								<li>Flags missing mandatory fields, regex mismatches, and invalid controlled-vocabulary values</li>
								<li>Row-level error table so you know exactly what to fix</li>
							</ul>
						</div>
						<div class="card">
							<h4>Submit with one click</h4>
							<ul class="list">
								<li>Generates all required SAMPLE and PROJECT XML automatically</li>
								<li>Creates per-MAG Webin-CLI manifests, handles chromosome lists for single-contig bins</li>
								<li>Runs in the background — accession numbers and logs saved automatically</li>
								<li>Supports both the ENA Testing and Production portals</li>
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
					<div class="h2">🔄 How it works</div>
					<div class="timeline">
						<div class="step"><b>Start from a template</b> or upload your existing metadata TSV — the table editor opens immediately.</div>
						<div class="step"><b>Auto-populate fields</b> by importing your CheckM / CheckM2 quality report and GTDB-Tk taxonomy summary.</div>
						<div class="step"><b>Resolve taxonomy &amp; ontology terms</b> using the built-in ENA taxonomy search and ENVO browser.</div>
						<div class="step"><b>Validate</b> — every mandatory field, format, and controlled vocabulary is checked against ERC000047 before anything is sent.</div>
						<div class="step"><b>Upload your FASTA.gz files</b>, enter your ENA Webin credentials, and hit Submit. Accession numbers are logged and saved automatically.</div>
					</div>
				</div>
				""",
				unsafe_allow_html=True,
		)

		st.divider()

		st.markdown(
				"""
				**References**
				- [GSC MIMAGS — Checklist: ERC000047](https://www.ebi.ac.uk/ena/browser/view/ERC000047)
				- [MIxS Term Browser](https://w3id.org/mixs/)
				- [ENA Webin Submission Portal](https://www.ebi.ac.uk/ena/browser/submit)
				- [ENVO Ontology](https://www.ebi.ac.uk/ols4/ontologies/envo)
				"""
		)

if __name__ == "__main__":
		runUI()
