import streamlit as st
import pandas as pd
import re
from io import StringIO
from pathlib import Path
from typing import List, Set

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

# Helper column for delete checkboxes (first column in editor)
DELETE_COL = "_delete"

# A computed status column (for the read-only mirror table below the editor)
STATUS_COL = "_row_status"  # "Valid" | "Issues" (not shown in editor)

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

    specs = specs[specs["field"].notna()].copy()
    for c in ["regex", "definition", "expected", "example", "structured"]:
        if c in specs.columns:
            specs[c] = specs[c].fillna("").astype(str).str.strip()
    specs.loc[specs["regex"] == "/", "regex"] = ""
    specs = specs.drop_duplicates(subset=["field"], keep="first")

    # Add required extra columns if missing (no regex by default)
    have = set(specs["field"].str.strip().str.lower())
    to_add = [c for c in REQUIRED_EXTRA_COLUMNS if c.lower() not in have]
    if to_add:
        add_df = pd.DataFrame({
            "field": to_add,
            "regex": [""] * len(to_add),
            "definition": ["" ] * len(to_add),
            "expected":  ["" ] * len(to_add),
            "example":   ["" ] * len(to_add),
            "structured":["" ] * len(to_add),
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

# =========================
# Date helpers (to avoid DateColumn dtype errors)
# =========================
def expand_date_aliases(date_cols: list[str]) -> list[str]:
    """Also include aliases with space/underscore swapped (e.g., collection date <-> collection_date)."""
    s = set(date_cols)
    for c in list(date_cols):
        s.add(c.replace("_", " "))
        s.add(c.replace(" ", "_"))
    return list(s)

def coerce_date_dtypes(df: pd.DataFrame, date_cols: list[str]) -> pd.DataFrame:
    """Ensure DateColumn fields are actually datetime64[ns] for the editor to accept."""
    out = df.copy()
    for col in date_cols:
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], errors="coerce")
    return out

# =========================
# Helpers: keep one blank row, exports, etc.
# =========================
def _is_blank_row(series: pd.Series) -> bool:
    return all((pd.isna(v) or str(v).strip() == "" or (isinstance(v, bool) and v is False)) for v in series.values)

def ensure_tail_blank(df: pd.DataFrame) -> pd.DataFrame:
    """Keep exactly one blank row at the end, respecting dtypes (and helper cols)."""
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
    """Remove trailing blank row and helper columns for export/validation."""
    out = df.copy()
    if DELETE_COL in out.columns:
        out = out.drop(columns=[DELETE_COL])
    if STATUS_COL in out.columns:
        out = out.drop(columns=[STATUS_COL])
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
def validate_required(df: pd.DataFrame, specs: pd.DataFrame) -> pd.DataFrame:
    """Required fields must be non-empty for all non-blank rows."""
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
    """Regex per cell (empties OK here; required handled separately)."""
    results = []
    regex_map = {r["field"]: r.get("regex", "") for _, r in specs.iterrows()}
    kind_map  = {r["field"]: r.get("kind", "text") for _, r in specs.iterrows()}
    for i, row in df.iterrows():
        for field in df.columns:
            raw  = row[field]
            kind = kind_map.get(field, "text")
            s    = to_str_for_regex(raw, kind)
            rx = regex_map.get(field, "")
            if s == "":
                results.append({"row_index": i, "field": field, "value": s, "valid": True, "message": "Empty (ok if not required)."})
                continue
            if rx:
                try:
                    ok = re.fullmatch(rx, s) is not None
                except re.error as e:
                    ok = False
                    rx = f"(invalid regex: {e})"
                results.append({"row_index": i, "field": field, "value": s, "valid": ok, "message": "OK" if ok else f"Regex mismatch: {rx}"})
            else:
                results.append({"row_index": i, "field": field, "value": s, "valid": True, "message": "No regex"})
    return pd.DataFrame(results)

def resolve_unique_key(df: pd.DataFrame) -> str:
    for k in UNIQUE_KEY_ALIASES:
        if k in df.columns:
            return k
    return UNIQUE_KEY_ALIASES[0]

def validate_unique_key(df: pd.DataFrame, key_field: str) -> pd.DataFrame:
    """Validate uniqueness for the given key_field (ignores blank keys)."""
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

# For heatmap styling (read-only mirror below the editor)
def build_invalid_mask(df: pd.DataFrame, reports: list[pd.DataFrame]) -> pd.DataFrame:
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

def style_with_mask(df: pd.DataFrame, mask: pd.DataFrame):
    def highlight(val, flag):
        return "background-color: #ffe6e6" if flag else ""
    return df.style.apply(
        lambda row: [highlight(row[c], mask.loc[row.name, c]) for c in df.columns],
        axis=1
    )

# =========================
# UI
# =========================
def runUI():
    # -------- Step header (guidance) --------
    st.markdown("## Create & Validate Metadata")
    st.info("**Step 1: Fill the table** → **Step 2: Fix errors** (see Validation panel) → **Step 3: Download**", icon="🧭")

    #with st.expander("Specification source CSV", expanded=False):
    #    st.code(str(CSV_SPEC_PATH))

    # Load spec
    try:
        specs = load_specs(CSV_SPEC_PATH)
    except Exception as e:
        st.error(f"Error reading spec CSV: {e}")
        return

    fields = specs["field"].tolist()
    if not fields:
        st.warning("No fields found in specification.")
        return

    # Date columns
    date_cols = specs.loc[specs["kind"] == "date", "field"].tolist()
    date_cols = expand_date_aliases(date_cols)  # include underscore/space aliases

    # Column config (labels include expected hint and '*' for required)
    col_cfg = {}
    for _, r in specs.iterrows():
        field = r["field"]
        kind  = r["kind"]
        is_required = field.strip().lower() in REQUIRED_FIELDS
        expected = r.get("expected", "").strip()
        label = field if not expected else f"{field} ({expected})"
        if is_required:
            label = f"{label} *"
        help_text = column_help(r)
        if kind == "lat":
            col_cfg[field] = st.column_config.NumberColumn(label, help=help_text, min_value=-90.0, max_value=90.0, step=0.000001)
        elif kind == "lon":
            col_cfg[field] = st.column_config.NumberColumn(label, help=help_text, min_value=-180.0, max_value=180.0, step=0.000001)
        elif kind == "number":
            col_cfg[field] = st.column_config.NumberColumn(label, help=help_text)
        elif kind == "date":
            col_cfg[field] = st.column_config.DateColumn(label, help=help_text, format="YYYY-MM-DD")
        else:
            col_cfg[field] = st.column_config.TextColumn(label, help=help_text)

    # Initialize session-state DataFrame with dtypes
    if "metadata_df" not in st.session_state:
        init = {c: pd.Series(dtype="object") for c in fields}
        for c in date_cols:
            if c in init:
                init[c] = pd.Series(dtype="datetime64[ns]")
        st.session_state.metadata_df = pd.DataFrame(init)
        st.session_state.metadata_df[DELETE_COL] = False
        # Ensure proper date dtypes
        st.session_state.metadata_df = coerce_date_dtypes(st.session_state.metadata_df, date_cols)
        st.session_state.metadata_df = ensure_tail_blank(st.session_state.metadata_df)

    # Realign schema if spec changed (preserve delete col)
    current_non_helper = [c for c in st.session_state.metadata_df.columns if c not in (DELETE_COL, STATUS_COL)]
    if current_non_helper != fields:
        old = st.session_state.metadata_df.drop(columns=[DELETE_COL, STATUS_COL], errors="ignore")
        init = {c: pd.Series(dtype="object") for c in fields}
        for c in date_cols:
            if c in init:
                init[c] = pd.Series(dtype="datetime64[ns]")
        new_df = pd.DataFrame(init)
        for c in old.columns:
            if c in new_df.columns:
                new_df[c] = old[c]
        st.session_state.metadata_df = new_df
        st.session_state.metadata_df[DELETE_COL] = False
        st.session_state.metadata_df = coerce_date_dtypes(st.session_state.metadata_df, date_cols)
        st.session_state.metadata_df = ensure_tail_blank(st.session_state.metadata_df)

    # --- CSS to freeze ✖ column on the left ---
    st.markdown(
        """
        <style>
        [data-testid="stDataFrame"] table tbody tr td:first-child,
        [data-testid="stDataFrame"] table thead tr th:first-child {
            position: sticky;
            left: 0;
            z-index: 1;
            background: white;
            box-shadow: 1px 0 0 #eee;
        }
        [data-testid="stDataFrame"] table thead tr th:first-child {
            z-index: 2;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # ---------- Toolbar ----------
    st.markdown("### Metadata editor")
    st.caption("Use the toolbar to add, select, and delete rows. The last row is always blank for quick entry.")

    t1, t2, t3, t4 = st.columns([1.1, 1.1, 1.1, 6])
    with t1:
        if st.button("➕ Add example row"):
            # Build a sample row using the spec "example" values when available
            row = {}
            for _, r in specs.iterrows():
                f = r["field"]
                if r.get("example"):
                    if r["kind"] == "date":
                        try:
                            row[f] = pd.to_datetime(str(r["example"])).to_pydatetime()
                        except Exception:
                            row[f] = pd.NaT
                    else:
                        row[f] = r["example"]
                else:
                    row[f] = pd.NaT if r["kind"] == "date" else ""
            new = pd.DataFrame([row])
            base = st.session_state.metadata_df.drop(columns=[DELETE_COL], errors="ignore")
            merged = pd.concat([drop_tail_blank_for_export(base), new], ignore_index=True)
            st.session_state.metadata_df = merged
            st.session_state.metadata_df[DELETE_COL] = False
            # ensure dates are proper dtype
            st.session_state.metadata_df = coerce_date_dtypes(st.session_state.metadata_df, date_cols)
            st.session_state.metadata_df = ensure_tail_blank(st.session_state.metadata_df)

    with t2:
        if st.button("Select all (non-empty)"):
            df_no_tail = drop_tail_blank_for_export(st.session_state.metadata_df)
            st.session_state.metadata_df.loc[:, DELETE_COL] = False
            st.session_state.metadata_df.loc[df_no_tail.index, DELETE_COL] = True

    with t3:
        if st.button("Clear selection"):
            st.session_state.metadata_df.loc[:, DELETE_COL] = False

    # Ensure trailing blank & ✖ first
    st.session_state.metadata_df = ensure_tail_blank(st.session_state.metadata_df)
    cols = [DELETE_COL] + [c for c in st.session_state.metadata_df.columns if c != DELETE_COL]
    st.session_state.metadata_df = st.session_state.metadata_df[cols]

    # Make sure date columns have datetime64[ns] dtype before rendering the editor
    st.session_state.metadata_df = coerce_date_dtypes(st.session_state.metadata_df, date_cols)

    # ---------- Editor ----------
    edited = st.data_editor(
        st.session_state.metadata_df,
        column_config={
            DELETE_COL: st.column_config.CheckboxColumn("✖", help="Tick to mark this row for deletion."),
            **col_cfg,
        },
        hide_index=True,
        num_rows="dynamic",
        use_container_width=True
    )

    # Apply edits and keep last row blank; coerce date dtypes again (cheap & safe)
    st.session_state.metadata_df = ensure_tail_blank(edited)
    st.session_state.metadata_df = coerce_date_dtypes(st.session_state.metadata_df, date_cols)
    # Keep ✖ first
    cols = [DELETE_COL] + [c for c in st.session_state.metadata_df.columns if c != DELETE_COL]
    st.session_state.metadata_df = st.session_state.metadata_df[cols]

    # Delete action (kept separate, obvious)
    if st.button("🗑️ Delete selected rows", type="secondary", use_container_width=True):
        mask = st.session_state.metadata_df[DELETE_COL] != True
        st.session_state.metadata_df = st.session_state.metadata_df.loc[mask].drop(columns=[DELETE_COL])
        st.session_state.metadata_df[DELETE_COL] = False
        st.session_state.metadata_df = coerce_date_dtypes(st.session_state.metadata_df, date_cols)
        st.session_state.metadata_df = ensure_tail_blank(st.session_state.metadata_df)
        cols = [DELETE_COL] + [c for c in st.session_state.metadata_df.columns if c != DELETE_COL]
        st.session_state.metadata_df = st.session_state.metadata_df[cols]

    # ---------- Normalized copy for validation/export ----------
    export_df = drop_tail_blank_for_export(st.session_state.metadata_df).copy()
    # normalize dates for validation/export
    for c in date_cols:
        if c in export_df.columns:
            export_df[c] = pd.to_datetime(export_df[c]).dt.date.astype("string")

    # ===== Live validation =====
    key_field = resolve_unique_key(export_df)
    required_report = validate_required(export_df, specs)
    regex_report    = validate_regex(export_df, specs)
    unique_report   = validate_unique_key(export_df, key_field)

    reports = [required_report, regex_report, unique_report]
    full_report = pd.concat(
        [r for r in reports if r is not None and not r.empty],
        ignore_index=True
    ) if any((r is not None and not r.empty) for r in reports) else pd.DataFrame(columns=["row_index","field","value","valid","message"])

    # Build per-row status for the mirror view
    if not export_df.empty:
        invalid_mask = build_invalid_mask(export_df, reports)
        row_has_issue = invalid_mask.any(axis=1)
        status_series = row_has_issue.map(lambda x: "Issues" if x else "Valid")
        mirror = export_df.copy()
        mirror[STATUS_COL] = status_series
    else:
        invalid_mask = pd.DataFrame(columns=export_df.columns)
        mirror = export_df.copy()

    issues_count = (~full_report["valid"]).sum() if not full_report.empty else 0

    # ---------- Validation panel ----------
    st.markdown("### Validation")
    st.caption("Fix red cells. All checks must pass to enable Download.")
    c1, c2 = st.columns([1, 5])
    with c1:
        st.metric("Issues found", issues_count)
    with c2:
        st.write("")

    tabs = st.tabs(["Heatmap", "Issues by column", "All issues"])
    with tabs[0]:
        if not export_df.empty:
            # Attach status as first column in the heatmap mirror
            mirror_show = mirror[[STATUS_COL] + [c for c in mirror.columns if c != STATUS_COL]]
            # style on the original columns only
            style_mask = invalid_mask.reindex(columns=[c for c in mirror_show.columns if c != STATUS_COL], fill_value=False)
            styled = mirror_show.style.apply(
                lambda row: [""] + ["background-color: #ffe6e6" if style_mask.loc[row.name, col] else "" for col in style_mask.columns],
                axis=1
            )
            st.dataframe(styled, use_container_width=True)
        else:
            st.info("No data yet. Start filling the table above.")

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

    # ---------- Download (only when all good) ----------
    all_ok = full_report.empty
    if all_ok and not export_df.empty:
        buf = StringIO(); export_df.to_csv(buf, index=False)
        st.success("✅ All checks passed. You can download your CSV.")
        st.download_button("⬇️ Download CSV", buf.getvalue().encode("utf-8"),
                           file_name="metadata_edited.csv", mime="text/csv",
                           use_container_width=True)
    else:
        st.info("Complete Step 2 (fix all issues) to enable Download.")
