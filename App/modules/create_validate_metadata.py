# modules/create_validate_metadata.py
import streamlit as st
import pandas as pd
import re
from io import StringIO
from pathlib import Path
from typing import List, Set, Dict, Tuple
from functools import lru_cache

# Optional: rich grid with per-cell styling (heatmap)
try:
    from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
    HAS_AGGRID = True
except Exception:
    HAS_AGGRID = False

# =========================
# Required metadata columns (also enforced as REQUIRED)
# =========================
REQUIRED_EXTRA_COLUMNS: List[str] = [
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
REQUIRED_FIELDS: Set[str] = {c.lower() for c in REQUIRED_EXTRA_COLUMNS}

# Accept either of these as the unique key (first one found wins)
UNIQUE_KEY_ALIASES = ["project name", "project_name"]

# Helper columns
DELETE_COL = "_delete"
STATUS_COL = "_row_status"      # "Valid" | "Issues" (for mirror/heatmap)
ISSUES_COL = "⚠︎ issues"        # compact list of fields with errors per row (read-only in the editor)

# Allowed ENA checklists (examples — replace with the real list when available)
ENA_CHECKLIST_ALLOWED = ["ERC000011", "ERC000012", "ERC000013",  "ERC000047"]

# =========================
# CSV spec path resolver
# =========================
def _resolve_spec_path() -> Path:
    base = Path(__file__).resolve().parent.parent
    p = base / "utils" / "20241111_proposed_terrestrial_metadata_fields.csv"
    return p if p.exists() else Path("20241111_proposed_terrestrial_metadata_fields.csv")

CSV_SPEC_PATH = _resolve_spec_path()

# =========================
# Load and normalize spec
# =========================
def load_specs(csv_path: Path) -> pd.DataFrame:
    specs = pd.read_csv(csv_path)
    rename = {
        "Metadata": "field",
        "regex_pattern": "regex",
        "Definition": "definition",
        "Expected value OR expected unit of measurement": "expected",
        "Example filed field": "example",
        "Structured_pattern": "structured",
    }
    for src, dst in rename.items():
        if src in specs.columns:
            specs = specs.rename(columns={src: dst})

    # ensure string dtype + strip
    if "field" not in specs.columns:
        raise ValueError("Spec CSV must contain a 'field' column.")
    specs["field"] = specs["field"].astype(str).fillna("").str.strip()

    for c in ["regex", "definition", "expected", "example", "structured"]:
        if c in specs.columns:
            specs[c] = specs[c].fillna("").astype(str).str.strip()

    # normalize slashes-only regex
    if "regex" in specs.columns:
        specs.loc[specs["regex"] == "/", "regex"] = ""

    # remove rows without field name
    specs = specs[specs["field"] != ""].copy()

    # dedup by field
    specs = specs.drop_duplicates(subset=["field"], keep="first")

    # Add required extra columns if missing (no regex by default)
    have = set(specs["field"].str.strip().str.lower())
    to_add = [c for c in REQUIRED_EXTRA_COLUMNS if c.lower() not in have]
    if to_add:
        add_df = pd.DataFrame({
            "field": to_add,
            "regex": [""] * len(to_add),
            "definition": [""] * len(to_add),
            "expected":  [""] * len(to_add),
            "example":   [""] * len(to_add),
            "structured":[""] * len(to_add),
        })
        specs = pd.concat([specs, add_df], ignore_index=True)

    # Kind inference for editor UX
    def infer_kind(field: str, rx: str) -> str:
        f = field.lower()
        if "latitude" in f:
            return "lat"
        if "longitude" in f:
            return "lon"
        if "date" in f or "timestamp" in f:
            return "date"
        if any(k in f for k in ["depth", "temperature", "altitude", "elevation", "coverage", "score", "tax_id"]):
            return "number"
        return "text"

    specs["kind"] = specs.apply(lambda r: infer_kind(r["field"], r.get("regex", "")), axis=1)
    return specs

def column_help(row) -> str:
    is_req = row["field"].strip().lower() in REQUIRED_FIELDS
    parts = [f"**Field:** {row['field']}{' (required)' if is_req else ''}"]
    if row.get("definition"): parts.append(f"**Definition:** {row['definition']}")
    if row.get("expected"):   parts.append(f"**Expected:** {row['expected']}")
    if row.get("example"):    parts.append(f"**Example:** {row['example']}")
    if row.get("regex"):      parts.append(f"**Regex:** `{row['regex']}`")
    if row.get("structured"): parts.append(f"**Structured pattern:** {row['structured']}")
    if is_req: parts.append("**Required:** Must not be empty.")
    return "\n\n".join(parts)

# Build editor column_config with dynamic labels (Streamlit native fallback)
def build_editor_column_config(specs: pd.DataFrame, bad_by_col: Set[str]) -> dict:
    cfg = {}
    for _, r in specs.iterrows():
        field = r["field"]
        kind  = r.get("kind", "text")
        is_required = field.strip().lower() in REQUIRED_FIELDS
        expected = r.get("expected","").strip()

        label = field if not expected else f"{field} ({expected})"
        if is_required:
            label = f"{label} *"
        if field in bad_by_col:
            label = f"❗ {label}"

        help_text = column_help(r)
        if kind == "lat":
            cfg[field] = st.column_config.NumberColumn(label, help=help_text, min_value=-90.0, max_value=90.0, step=0.000001)
        elif kind == "lon":
            cfg[field] = st.column_config.NumberColumn(label, help=help_text, min_value=-180.0, max_value=180.0, step=0.000001)
        elif kind == "number":
            cfg[field] = st.column_config.NumberColumn(label, help=help_text)
        elif kind == "date":
            cfg[field] = st.column_config.DateColumn(label, help=help_text, format="YYYY-MM-DD")
        else:
            cfg[field] = st.column_config.TextColumn(label, help=help_text)

    if "ENA-CHECKLIST" in specs["field"].values:
        base = "ENA-CHECKLIST *"
        label = f"❗ {base}" if "ENA-CHECKLIST" in bad_by_col else base
        cfg["ENA-CHECKLIST"] = st.column_config.SelectboxColumn(
            label, options=ENA_CHECKLIST_ALLOWED, help="Select an allowed ENA checklist identifier."
        )
    return cfg

# =========================
# Date helpers
# =========================
def expand_date_aliases(date_cols: List[str]) -> List[str]:
    s = set(date_cols)
    for c in list(date_cols):
        s.add(c.replace("_", " "))
        s.add(c.replace(" ", "_"))
    return list(s)

def coerce_date_dtypes(df: pd.DataFrame, date_cols: List[str]) -> pd.DataFrame:
    out = df.copy()
    for col in date_cols:
        for name in (col, col.replace("_", " "), col.replace(" ", "_")):
            if name in out.columns:
                out[name] = pd.to_datetime(out[name], errors="coerce")
    return out

# =========================
# Helpers: blank row, export, etc.
# =========================
def _is_blank_row(series: pd.Series) -> bool:
    return all((pd.isna(v) or str(v).strip() == "" or (isinstance(v, bool) and v is False)) for v in series.values)

def ensure_tail_blank(df: pd.DataFrame) -> pd.DataFrame:
    keep_rows = [i for i, row in df.iterrows() if not _is_blank_row(row)]
    df = df.loc[keep_rows].copy()

    if DELETE_COL not in df.columns:
        df[DELETE_COL] = False
    df[DELETE_COL] = df[DELETE_COL].fillna(False).astype(bool)

    blank = {}
    for c in df.columns:
        if c == DELETE_COL:
            blank[c] = False
        elif pd.api.types.is_datetime64_any_dtype(df[c].dtype):
            blank[c] = pd.NaT
        else:
            blank[c] = ""
    df = pd.concat([df, pd.DataFrame([blank])], ignore_index=True)
    return df

def drop_tail_blank_for_export(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for aux in (DELETE_COL, STATUS_COL, ISSUES_COL):
        if aux in out.columns:
            out = out.drop(columns=[aux])
    if len(out) == 0:
        return out
    last = out.iloc[-1]
    if all((pd.isna(v) or str(v).strip() == "") for v in last.values):
        return out.iloc[:-1].copy()
    return out

def to_str_for_regex(value, kind: str) -> str:
    if pd.isna(value) or value == "":
        return ""
    if kind == "date":
        try:
            return pd.to_datetime(value).date().isoformat()
        except Exception:
            return str(value)
    if isinstance(value, (int, float)):
        return format(value, "f")
    return str(value)

# =========================
# Validation
# =========================
@lru_cache(maxsize=1)
def _compiled_regex_map_tuple(specs_tuple):
    """Cache compiled regex by turning specs rows into a hashable tuple."""
    rx_map = {}
    for row in specs_tuple:
        f = row[0]
        rx = row[1]
        if rx:
            try:
                rx_map[f] = re.compile(rx)
            except re.error:
                rx_map[f] = None
        else:
            rx_map[f] = None
    return rx_map

def _get_compiled_regex_map(specs: pd.DataFrame):
    specs_tuple = tuple((r['field'], r.get('regex', '')) for _, r in specs.iterrows())
    return _compiled_regex_map_tuple(specs_tuple)

def validate_required(df: pd.DataFrame, specs: pd.DataFrame) -> pd.DataFrame:
    results = []
    kinds = {r["field"]: r.get("kind", "text") for _, r in specs.iterrows()}
    fields_lower = {c.lower(): c for c in df.columns}

    for i, row in df.iterrows():
        if all((pd.isna(v) or str(v).strip() == "") for v in row.values):
            continue
        for f_lower in REQUIRED_FIELDS:
            if f_lower not in fields_lower:
                results.append({"row_index": i, "field": f_lower, "value": "", "valid": False, "message": "Required field missing in table schema."})
                continue
            f_real = fields_lower[f_lower]
            val = row[f_real]
            kind = kinds.get(f_real, "text")
            s = to_str_for_regex(val, kind)
            if s == "":
                results.append({"row_index": i, "field": f_real, "value": s, "valid": False, "message": "Required: must not be empty."})
    return pd.DataFrame(results)

def validate_regex(df: pd.DataFrame, specs: pd.DataFrame) -> pd.DataFrame:
    results = []
    rx_compiled = _get_compiled_regex_map(specs)
    kind_map  = {r["field"]: r.get("kind", "text") for _, r in specs.iterrows()}
    rx_raw    = {r["field"]: r.get("regex", "") for _, r in specs.iterrows()}
    for i, row in df.iterrows():
        for field in df.columns:
            raw  = row[field]
            kind = kind_map.get(field, "text")
            s    = to_str_for_regex(raw, kind)
            rx = rx_compiled.get(field)
            if s == "":
                results.append({"row_index": i, "field": field, "value": s, "valid": True, "message": "Empty (ok if not required)."})
                continue
            if rx is not None:
                ok = rx.fullmatch(s) is not None
                results.append({"row_index": i, "field": field, "value": s, "valid": ok, "message": "OK" if ok else f"Regex mismatch: {rx_raw.get(field,'')}"})
            else:
                results.append({"row_index": i, "field": field, "value": s, "valid": True, "message": "No regex"})
    return pd.DataFrame(results)

def resolve_unique_key(df: pd.DataFrame) -> str:
    for k in UNIQUE_KEY_ALIASES:
        if k in df.columns:
            return k
    return UNIQUE_KEY_ALIASES[0]

def validate_unique_key(df: pd.DataFrame, key_field: str) -> pd.DataFrame:
    if key_field not in df.columns:
        return pd.DataFrame([{"row_index": None, "field": key_field, "value": "", "valid": False, "message": f"Unique key field '{key_field}' missing in schema."}])
    results = []
    key_series = df[key_field].astype(str).fillna("").str.strip()
    counts = key_series.value_counts()
    dups = set(counts[counts > 1].index.tolist())
    for i, v in key_series.items():
        if v != "" and v in dups:
            results.append({"row_index": i, "field": key_field, "value": v, "valid": False, "message": f"Duplicate '{key_field}': must be unique."})
    return pd.DataFrame(results)

# Minimal semantics (shape) for some fields
def validate_envo_like(s: str) -> bool:
    return bool(re.fullmatch(r"(ENVO:)?\d{7}", str(s).strip()))

def validate_chebi_like(s: str) -> bool:
    s = str(s).strip().split(";")[0]  # accepts "CHEBI:12345;timestamp"
    return bool(re.fullmatch(r"(CHEBI:)?\d{1,6}", s))

def validate_taxid_like(s: str) -> bool:
    return bool(re.fullmatch(r"\d{1,9}", str(s).strip()))

SEMANTIC_FIELDS = {
    "env_broad_scale": validate_envo_like,
    "env_local_scale": validate_envo_like,
    "env_medium":      validate_envo_like,
    "chem_administration": validate_chebi_like,
    "samp_taxon_id":   validate_taxid_like,
    "tax_id":          validate_taxid_like,
}

def validate_semantics(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for field, fn in SEMANTIC_FIELDS.items():
        if field not in df.columns:
            continue
        for i, v in df[field].items():
            if pd.isna(v) or str(v).strip()=="":
                continue
            if not fn(v):
                rows.append({"row_index": i, "field": field, "value": v, "valid": False,
                             "message": "Ontology/ID shape mismatch (expected ENVO/CHEBI/TaxID pattern)."})
    return pd.DataFrame(rows)

def validate_ena_checklist(df: pd.DataFrame) -> pd.DataFrame:
    if "ENA-CHECKLIST" not in df.columns:
        return pd.DataFrame([{"row_index": None,"field":"ENA-CHECKLIST","value":"","valid":False,"message":"ENA-CHECKLIST missing in schema."}])
    bad = []
    for i, v in df["ENA-CHECKLIST"].fillna("").items():
        if v == "":
            continue
        if v not in ENA_CHECKLIST_ALLOWED:
            bad.append({"row_index": i, "field":"ENA-CHECKLIST","value":v,"valid":False,"message":"Value not in allowed ENA checklist list."})
    return pd.DataFrame(bad)

def build_invalid_mask(df: pd.DataFrame, reports: List[pd.DataFrame]) -> pd.DataFrame:
    mask = pd.DataFrame(False, index=df.index, columns=df.columns)
    for rep in reports:
        if rep is None or rep.empty:
            continue
        bad = rep[~rep["valid"]]
        for _, r in bad.iterrows():
            i = r["row_index"]
            f = r["field"]
            if i is not None and f in mask.columns and i in mask.index:
                mask.loc[i, f] = True
    return mask

def _lc_map(names: List[str]) -> Dict[str, str]:
    """lower-name -> original name mapping (case-insensitive preservation)."""
    return {str(n).strip().lower(): n for n in names}

def order_fields_required_first(specs: pd.DataFrame) -> List[str]:
    """
    Return field list with required first (based on REQUIRED_EXTRA_COLUMNS order),
    followed by others in the order they appear in the spec CSV.
    """
    spec_fields = [f for f in specs["field"].tolist() if isinstance(f, str)]
    spec_lc = _lc_map(spec_fields)

    # Required fields that exist in the spec (keep spec capitalization)
    req_in_spec = []
    for r in REQUIRED_EXTRA_COLUMNS:
        r_lc = r.strip().lower()
        if r_lc in spec_lc:
            req_in_spec.append(spec_lc[r_lc])

    # Other fields (non-required)
    req_set_lc = {x.strip().lower() for x in req_in_spec}
    others = [f for f in spec_fields if f.strip().lower() not in req_set_lc]

    return req_in_spec + others

# =========================
# UI
# =========================
def runUI():
    st.markdown("## Create & Validate Metadata")
    st.info("**Step 1: Create or Upload** → **Step 2: Fix errors** → **Step 3: Download**", icon="🧭")

    # Load spec
    try:
        specs = load_specs(CSV_SPEC_PATH)
    except Exception as e:
        st.error(f"Error reading spec CSV: {e}")
        return

    fields = order_fields_required_first(specs)
    if not fields:
        st.warning("No fields found in specification.")
        return

    # Date columns (+ aliases)
    date_cols = specs.loc[specs["kind"] == "date", "field"].tolist()
    date_cols = expand_date_aliases(date_cols)

    # ========== Upload OR Create ==========
    top_left, top_right = st.columns([1.2, 1.8])
    with top_left:
        up = st.file_uploader("Upload CSV/Excel", type=["csv", "xlsx"], help="Upload to replace the current table with file content.")
        if up is not None:
            try:
                if up.name.lower().endswith(".csv"):
                    incoming = pd.read_csv(up)
                else:
                    incoming = pd.read_excel(up)

                # Column mapping wizard for unknown columns
                fields_set = set(fields)
                unknown = [c for c in incoming.columns if c not in fields_set]
                if unknown:
                    st.warning(f"Found {len(unknown)} unrecognized column(s) in the file: {unknown}")
                    st.caption("Map them to the standard fields below (or leave as '— ignore —').")
                    mapping = {}
                    options = ["— ignore —"] + fields
                    for u in unknown:
                        mapping[u] = st.selectbox(f"Map '{u}' to", options=options, key=f"map_{u}")
                    ren = {u: m for u, m in mapping.items() if m in fields}
                    incoming = incoming.rename(columns=ren)
                    drop_cols = [u for u, m in mapping.items() if m == "— ignore —"]
                    if drop_cols:
                        incoming = incoming.drop(columns=drop_cols)

                # Keep only spec columns + create missing
                keep = [c for c in incoming.columns if c in fields]
                incoming = incoming[keep].copy() if keep else pd.DataFrame(columns=fields)
                for c in fields:
                    if c not in incoming.columns:
                        incoming[c] = pd.Series(dtype="object")
                incoming = incoming.reindex(columns=fields)
                incoming = coerce_date_dtypes(incoming, date_cols)
                incoming[DELETE_COL] = False
                st.session_state.metadata_df = ensure_tail_blank(incoming)
                st.session_state.page_mode = "Validation (uploaded)"
                st.success(f"Loaded {len(incoming)} rows from {up.name}.")
            except Exception as e:
                st.error(f"Failed to load file: {e}")

    with top_right:
        st.caption("Or start from an empty template:")
        if st.button("Start new (empty template)", type="secondary"):
            init = {c: pd.Series(dtype="object") for c in fields}
            for c in date_cols:
                if c in init:
                    init[c] = pd.Series(dtype="datetime64[ns]")
            df0 = pd.DataFrame(init)
            df0[DELETE_COL] = False
            st.session_state.metadata_df = ensure_tail_blank(coerce_date_dtypes(df0, date_cols))
            st.session_state.page_mode = "Creation"
            st.success("Initialized new empty table.")

    # If session not initialized: create empty
    if "metadata_df" not in st.session_state:
        init = {c: pd.Series(dtype="object") for c in fields}
        for c in date_cols:
            if c in init:
                init[c] = pd.Series(dtype="datetime64[ns]")
        df0 = pd.DataFrame(init)
        df0[DELETE_COL] = False
        st.session_state.metadata_df = ensure_tail_blank(coerce_date_dtypes(df0, date_cols))
        st.session_state.page_mode = "Creation"

    st.caption(f"**Mode:** {st.session_state.get('page_mode','Creation')}  •  Spec: `{CSV_SPEC_PATH.name}`")

    # ========= PRE-VALIDATION (to fill the '⚠︎ issues' column in the editor) =========
    pre_export = drop_tail_blank_for_export(st.session_state.metadata_df).copy()
    for c in [x for x in pre_export.columns if x.lower() in [dc.lower() for dc in date_cols]]:
        pre_export[c] = pd.to_datetime(pre_export[c], errors="coerce").dt.date.astype("string")

    pre_key = resolve_unique_key(pre_export)
    pre_reports = [
        validate_required(pre_export, specs),
        validate_regex(pre_export, specs),
        validate_unique_key(pre_export, pre_key),
        validate_ena_checklist(pre_export),
        validate_semantics(pre_export),
    ]
    pre_full = pd.concat(
        [r for r in pre_reports if r is not None and not r.empty],
        ignore_index=True
    ) if any((r is not None and not r.empty) for r in pre_reports) else pd.DataFrame(columns=["row_index","field","value","valid","message"])

    # issues per row for editor display
    issues_by_row: Dict[int, Set[str]] = {}
    for _, r in pre_full[~pre_full["valid"]].iterrows():
        i = r["row_index"]; f = str(r["field"])
        if i is None: continue
        issues_by_row.setdefault(int(i), set()).add(f)

    display_df = st.session_state.metadata_df.copy()
    issue_col = []
    for i in range(len(display_df)):
        if i < len(pre_export):
            short = ", ".join(sorted(issues_by_row.get(i, [])))
        else:
            short = ""
        issue_col.append(short)
    display_df[ISSUES_COL] = issue_col

    # -------- Toolbar --------
    st.markdown("### Metadata editor")
    st.caption("Use the toolbar to add, select, and delete rows. The last row is always blank for quick entry.")

    b1, b2, b3, b4 = st.columns([1, 1, 1, 1])
    with b1:
        add_example = st.button("➕ Add example row", use_container_width=True)
    with b2:
        select_all = st.button("Select all (non-empty)", use_container_width=True)
    with b3:
        clear_sel = st.button("Clear selection", use_container_width=True)
    with b4:
        auto_fix = st.button("🧹 Auto-fix common issues", use_container_width=True)

    filt_col1, filt_col2, _ = st.columns([1.8, 1.4, 4])
    with filt_col1:
        only_issues = st.toggle("Show only rows with problems (editor)", value=False)
    with filt_col2:
        goto_next = st.button("➡️ Go to next error", use_container_width=True)

    if add_example:
        row = {}
        for _, r in specs.iterrows():
            f = r["field"]
            if r.get("example"):
                if r["kind"] == "date":
                    try:
                        row[f] = pd.to_datetime(str(r["example"]))
                    except Exception:
                        row[f] = pd.NaT
                else:
                    row[f] = r["example"]
            else:
                row[f] = pd.NaT if r["kind"] == "date" else ""
        new = pd.DataFrame([row])
        base = st.session_state.metadata_df.drop(columns=[DELETE_COL, ISSUES_COL], errors="ignore")
        merged = pd.concat([drop_tail_blank_for_export(base), new], ignore_index=True)
        st.session_state.metadata_df = merged
        st.session_state.metadata_df[DELETE_COL] = False
        st.session_state.metadata_df = coerce_date_dtypes(st.session_state.metadata_df, date_cols)
        st.session_state.metadata_df = ensure_tail_blank(st.session_state.metadata_df)

    if select_all:
        df_no_tail = drop_tail_blank_for_export(st.session_state.metadata_df)
        st.session_state.metadata_df.loc[:, DELETE_COL] = False
        st.session_state.metadata_df.loc[df_no_tail.index, DELETE_COL] = True

    if clear_sel:
        st.session_state.metadata_df.loc[:, DELETE_COL] = False

    if auto_fix:
        df = st.session_state.metadata_df.copy()
        for c in df.columns:
            if c in (DELETE_COL, STATUS_COL, ISSUES_COL):
                continue
            if pd.api.types.is_object_dtype(df[c].dtype):
                df[c] = df[c].astype(str).str.strip().replace({"nan": ""})
        for c in df.columns:
            cl = c.lower()
            if "latitude" in cl or "longitude" in cl:
                df[c] = pd.to_numeric(df[c].astype(str).str.replace(",", "."), errors="coerce")
        df = coerce_date_dtypes(df, date_cols)
        st.session_state.metadata_df = ensure_tail_blank(df)
        st.success("Auto-fix applied.")

    # keep trailing blank & required-first order
    st.session_state.metadata_df = ensure_tail_blank(st.session_state.metadata_df)
    display_df = st.session_state.metadata_df.copy()
    display_df[ISSUES_COL] = issue_col if len(issue_col) == len(display_df) else [""] * len(display_df)

    # keep columns ordered (required-first) in the editor
    non_helpers = [c for c in fields if c in display_df.columns]  # already in the chosen order
    ordered_cols = [DELETE_COL] + non_helpers + [ISSUES_COL]
    display_df = display_df.reindex(columns=ordered_cols)

    # ensure datetime for date cols before editor
    for c in display_df.columns:
        if c.lower() in [dc.lower() for dc in date_cols]:
            display_df[c] = pd.to_datetime(display_df[c], errors="coerce")

    # ---- Pre-validation for editor (labels, filtering, per-cell flags/messages)
    pre_export2 = drop_tail_blank_for_export(display_df.drop(columns=[ISSUES_COL], errors="ignore")).copy()
    for c in [x for x in pre_export2.columns if x.lower() in [dc.lower() for dc in date_cols]]:
        pre_export2[c] = pd.to_datetime(pre_export2[c], errors="coerce").dt.date.astype("string")

    pre_key2 = resolve_unique_key(pre_export2)
    pre_reports2 = [
        validate_required(pre_export2, specs),
        validate_regex(pre_export2, specs),
        validate_unique_key(pre_export2, pre_key2),
        validate_ena_checklist(pre_export2),
        validate_semantics(pre_export2),
    ]
    pre_full2 = pd.concat([r for r in pre_reports2 if r is not None and not r.empty], ignore_index=True) \
                 if any((r is not None and not r.empty) for r in pre_reports2) else pd.DataFrame(columns=["row_index","field","value","valid","message"])
    bad_by_col = set(pre_full2.loc[~pre_full2['valid'], 'field'].astype(str)) if not pre_full2.empty else set()

    invalid_mask_tmp = build_invalid_mask(pre_export2, pre_reports2) if not pre_export2.empty else pd.DataFrame(columns=pre_export2.columns)

    # error messages per cell (ri, field) -> message(s)
    cell_msgs: Dict[Tuple[int, str], List[str]] = {}
    if not pre_full2.empty:
        bad = pre_full2[pre_full2["valid"] == False]
        for _, r in bad.iterrows():
            ri = int(r["row_index"]) if pd.notna(r["row_index"]) else None
            f  = str(r["field"])
            if ri is None: 
                continue
            cell_msgs.setdefault((ri, f), []).append(str(r.get("message","")))

    # filter only rows with problems (but keep last blank row)
    base_display_df = display_df.copy()
    if only_issues and not invalid_mask_tmp.empty:
        issue_rows_idx = invalid_mask_tmp.index[invalid_mask_tmp.any(axis=1)].tolist()
        keep_idx = [i for i in base_display_df.index if i in issue_rows_idx]
        if len(base_display_df) > 0 and base_display_df.index[-1] not in keep_idx:
            keep_idx.append(base_display_df.index[-1])
        base_display_df = base_display_df.loc[keep_idx].copy()

    # ---------- Editor ----------
    if HAS_AGGRID:
        # Build grid DF with helper columns for invalid flags + tooltip text
        grid_df = base_display_df.drop(columns=[ISSUES_COL], errors="ignore").copy()
        grid_df.insert(0, "#", grid_df.index + 1)

        # helper flags/messages aligned by original index
        for c in non_helpers + [DELETE_COL]:
            flag = []
            tip  = []
            for idx in grid_df.index:
                bad = False
                msg = ""
                if not invalid_mask_tmp.empty and c in invalid_mask_tmp.columns and idx in invalid_mask_tmp.index:
                    bad = bool(invalid_mask_tmp.loc[idx, c])
                if (idx, c) in cell_msgs:
                    msg = "; ".join(sorted(set(cell_msgs[(idx, c)])))
                flag.append(bad)
                tip.append(msg)
            grid_df[f"__invalid__{c}"] = flag
            grid_df[f"__tip__{c}"] = tip

        # Columns that actually have issues inside the visible grid
        cols_with_issues_grid = {
            c for c in (non_helpers) 
            if f"__invalid__{c}" in grid_df.columns and any(grid_df[f"__invalid__{c}"])
        }

        gb = GridOptionsBuilder.from_dataframe(grid_df[["#"] + [DELETE_COL] + non_helpers])
        gb.configure_column("#", pinned="left", width=70)

        # Style: CSS class + inline style (robust across themes)
        st.markdown("<style>.invalidCell{background-color:#ffe6e6 !important;}</style>", unsafe_allow_html=True)

        # DELETE column config
        gb.configure_column(
            DELETE_COL,
            headerName="✖",
            editable=True,
            width=70,
        )

        for c in non_helpers:
            header = c
            if c in cols_with_issues_grid:
                header = f"❗ {header}"
            if c.strip().lower() in REQUIRED_FIELDS:
                header = f"{header} *"

            rules_js = JsCode(f"function(p){{return p.data['__invalid__{c}'] === true;}}").js_code
            style_js = JsCode(
                f"""
                function(p) {{
                    if (p.data && p.data['__invalid__{c}'] === true) {{
                        return {{ backgroundColor: '#ffe6e6' }};
                    }}
                    return null;
                }}
                """
            ).js_code

            gb.configure_column(
                c,
                headerName=header,
                editable=True,
                tooltipField=f"__tip__{c}",
                cellClassRules={"invalidCell": rules_js},
                cellStyle=style_js,
                wrapText=False,
                autoHeight=False,
                resizable=True,
            )

        gb.configure_grid_options(domLayout='normal', rowHeight=28)
        grid = AgGrid(
            grid_df,
            gridOptions=gb.build(),
            data_return_mode="AS_INPUT",
            update_mode="MODEL_CHANGED",
            height=min(520, 28 * max(10, len(grid_df)) + 120),
            fit_columns_on_grid_load=False,   # <-- as requested
            allow_unsafe_jscode=True,
            enable_enterprise_modules=False,
            theme='streamlit',
        )

        edited = pd.DataFrame(grid["data"])
        # drop helpers and '#' column
        drop_helpers = [c for c in edited.columns if c.startswith("__invalid__") or c.startswith("__tip__")]
        edited = edited.drop(columns=drop_helpers + ["#"], errors="ignore")

        # Persist edits
        st.session_state.metadata_df = ensure_tail_blank(edited)
        st.session_state.metadata_df = coerce_date_dtypes(st.session_state.metadata_df, date_cols)

    else:
        # Fallback: Streamlit data_editor (no per-cell tooltip)
        editor_col_cfg = build_editor_column_config(specs, bad_by_col)
        edited = st.data_editor(
            base_display_df,
            column_config={
                DELETE_COL: st.column_config.CheckboxColumn("✖", help="Tick to mark this row for deletion."),
                **editor_col_cfg,
                ISSUES_COL: st.column_config.TextColumn(ISSUES_COL, help="List of fields with issues in this row.", disabled=True),
            },
            hide_index=True,
            num_rows="dynamic",
            use_container_width=True,
            key="main_editor",
        )
        edited_no_issues = edited.drop(columns=[ISSUES_COL], errors="ignore")
        st.session_state.metadata_df = ensure_tail_blank(edited_no_issues)
        st.session_state.metadata_df = coerce_date_dtypes(st.session_state.metadata_df, date_cols)

    # ---------- Official validation after edits ----------
    export_df = drop_tail_blank_for_export(st.session_state.metadata_df).copy()
    for c in [x for x in export_df.columns if x.lower() in [dc.lower() for dc in date_cols]]:
        export_df[c] = pd.to_datetime(export_df[c], errors="coerce").dt.date.astype("string")

    key_field = resolve_unique_key(export_df)
    required_report = validate_required(export_df, specs)
    regex_report    = validate_regex(export_df, specs)
    unique_report   = validate_unique_key(export_df, key_field)
    ena_report      = validate_ena_checklist(export_df)
    sem_report      = validate_semantics(export_df)

    reports = [required_report, regex_report, unique_report, ena_report, sem_report]
    full_report = pd.concat(
        [r for r in reports if r is not None and not r.empty],
        ignore_index=True
    ) if any((r is not None and not r.empty) for r in reports) else pd.DataFrame(columns=["row_index","field","value","valid","message"])

    # Build invalid mask directly from final report
    invalid_mask = pd.DataFrame(False, index=export_df.index, columns=export_df.columns)
    if not full_report.empty:
        bad = full_report.loc[full_report["valid"] == False].copy()
        for _, r in bad.iterrows():
            i = r.get("row_index"); f = r.get("field")
            if pd.notna(i) and f in invalid_mask.columns and i in invalid_mask.index:
                invalid_mask.loc[int(i), f] = True

    issues_count = (~full_report["valid"]).sum() if not full_report.empty else 0

    # ---------- Error navigator ----------
    error_coords = []
    if not full_report.empty:
        bad = full_report.loc[full_report['valid'] == False].dropna(subset=['row_index'])
        for _, r in bad.iterrows():
            ri = int(r['row_index']); f = str(r['field']); msg = str(r['message'])
            if f in export_df.columns and ri in export_df.index:
                error_coords.append((ri, f, msg))
    if 'error_ptr' not in st.session_state:
        st.session_state.error_ptr = 0
    if goto_next and len(error_coords) > 0:
        st.session_state.error_ptr = (st.session_state.error_ptr + 1) % len(error_coords)
        cur = error_coords[st.session_state.error_ptr]
        st.info(f"Next error → Row {cur[0]+1}, Column '{cur[1]}': {cur[2]}")

    # ---------- Dataset summary ----------
    st.markdown("### Dataset summary")
    r1, r2, r3 = st.columns(3)
    with r1: st.metric("Rows (non-empty)", len(export_df))
    with r2: st.metric("Required fields", len(REQUIRED_FIELDS))
    with r3: st.metric("All issues", issues_count)

    # ---------- Validation ----------
    st.markdown("### Validation")
    st.caption("Fix red cells in the heatmap below. All checks must pass to enable Download.")

    tabs = st.tabs(["Heatmap", "Issues by column", "All issues"])
    with tabs[0]:
        if export_df.empty or invalid_mask.empty or (~invalid_mask).all().all():
            st.success("No invalid cells found.")
        else:
            cols_with_issues = [c for c in export_df.columns if invalid_mask[c].any()]
            show_only_issue_cols = st.toggle("Show only columns with issues (heatmap)", value=True, key="hm_cols_toggle")
            visible_cols = cols_with_issues if show_only_issue_cols else export_df.columns.tolist()

            # Compact Styler table with truncation + fixed layout
            hm_df = export_df[list(visible_cols)].copy()

            def _shorten(x, n=24):
                if pd.isna(x): return ""
                s = str(x)
                return s if len(s) <= n else s[: n - 1] + "…"
            hm_df = hm_df.applymap(_shorten)

            def highlight_row(row):
                idx = row.name
                return ["background-color: #ffe6e6" if bool(invalid_mask.loc[idx, col]) else "" for col in hm_df.columns]

            styled = (
                hm_df.style
                .apply(highlight_row, axis=1)
                .set_table_styles([
                    {"selector": "th", "props": "max-width:160px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; padding:4px; font-size:12px;"},
                    {"selector": "td", "props": "max-width:160px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; padding:4px; font-size:12px; line-height:1.1;"},
                ])
            )
            st.markdown(
                """
                <style>
                [data-testid="stTable"] table { table-layout: fixed; }
                [data-testid="stTable"] td, [data-testid="stTable"] th {
                    max-width: 160px; white-space: nowrap !important; overflow: hidden; text-overflow: ellipsis;
                    padding: 4px 6px; line-height: 1.1; font-size: 12px;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )
            st.table(styled)

    with tabs[1]:
        if not full_report.empty:
            by_col = full_report[~full_report["valid"]].groupby("field").size().sort_values(ascending=False)
            st.dataframe(by_col.to_frame("count"))
        else:
            st.success("No errors by column.")

    with tabs[2]:
        if not full_report.empty:
            proj_col = key_field if key_field in export_df.columns else None
            proj_by_row = export_df[proj_col] if proj_col else pd.Series(index=export_df.index, dtype=str)
            detail = full_report.copy()
            detail["project_name"] = detail["row_index"].map(lambda i: proj_by_row[i] if (proj_col and i in proj_by_row.index) else "")
            cols_detail = ["project_name", "row_index", "field", "value", "message", "valid"]
            cols_detail = [c for c in cols_detail if c in detail.columns]
            st.dataframe(detail[cols_detail].sort_values(["project_name","row_index","field"]).reset_index(drop=True), use_container_width=True)
        else:
            st.success("No issues detected.")

    # ---------- Download ----------
    if (~invalid_mask).all().all():
        buf = StringIO(); export_df.to_csv(buf, index=False)
        st.success("✅ All checks passed. You can download your CSV.")
        st.download_button("⬇️ Download CSV", buf.getvalue().encode("utf-8"),
                           file_name="metadata_validated.csv", mime="text/csv",
                           use_container_width=True)
    else:
        st.info("Complete Step 2 (fix all issues) to enable Download.")

    # ---------- Extra: download issues report ----------
    if not full_report.empty:
        csv_err = full_report.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download issues report (CSV)", csv_err, "validation_issues.csv", "text/csv")
