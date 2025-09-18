# modules/create_validate_metadata.py
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

# Helper columns
DELETE_COL = "_delete"
STATUS_COL = "_row_status"      # "Valid" | "Issues" (para mirror/heatmap)
ISSUES_COL = "⚠︎ issues"        # lista compacta de campos com erro por linha (somente leitura no editor)

# Allowed ENA checklists (exemplos — troque pela lista real quando tiver)
ENA_CHECKLIST_ALLOWED = ["ERC000011", "ERC000012", "ERC000013"]

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

    # Kind inference para UX no editor
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
# Date helpers
# =========================
def expand_date_aliases(date_cols: list[str]) -> list[str]:
    s = set(date_cols)
    for c in list(date_cols):
        s.add(c.replace("_", " "))
        s.add(c.replace(" ", "_"))
    return list(s)

def coerce_date_dtypes(df: pd.DataFrame, date_cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in date_cols:
        if col in out.columns:
            out[col] = pd.to_datetime(out[col], errors="coerce")
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
    if DELETE_COL in out.columns:
        out = out.drop(columns=[DELETE_COL])
    if STATUS_COL in out.columns:
        out = out.drop(columns=[STATUS_COL])
    if ISSUES_COL in out.columns:
        out = out.drop(columns=[ISSUES_COL])
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

# Semântica mínima (shape) para alguns campos
def validate_envo_like(s: str) -> bool:
    return bool(re.fullmatch(r"(ENVO:)?\d{7}", str(s).strip()))

def validate_chebi_like(s: str) -> bool:
    s = str(s).strip().split(";")[0]  # aceita "CHEBI:12345;timestamp"
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

    fields = specs["field"].tolist()
    if not fields:
        st.warning("No fields found in specification.")
        return

    # Date columns (+ aliases)
    date_cols = specs.loc[specs["kind"] == "date", "field"].tolist()
    date_cols = expand_date_aliases(date_cols)

    # Column config (labels com expected e * para required)
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

    if "ENA-CHECKLIST" in fields:
        col_cfg["ENA-CHECKLIST"] = st.column_config.SelectboxColumn(
            "ENA-CHECKLIST *",
            options=ENA_CHECKLIST_ALLOWED,
            help="Select an allowed ENA checklist identifier.",
            disabled=False
        )

    # ========== Upload OU Criação ==========
    left, right = st.columns([1.2, 1.8])
    with left:
        up = st.file_uploader("Upload CSV/Excel", type=["csv", "xlsx"], help="Upload to replace the current table with file content.")
        if up is not None:
            try:
                if up.name.lower().endswith(".csv"):
                    incoming = pd.read_csv(up)
                else:
                    incoming = pd.read_excel(up)
                # manter somente colunas da spec + criar faltantes
                keep = [c for c in incoming.columns if c in fields]
                incoming = incoming[keep].copy() if keep else pd.DataFrame(columns=fields)
                for c in fields:
                    if c not in incoming.columns:
                        incoming[c] = pd.Series(dtype="object")
                # coerção de dtypes (datas) e setar no editor
                incoming = coerce_date_dtypes(incoming, date_cols)
                incoming[DELETE_COL] = False
                st.session_state.metadata_df = ensure_tail_blank(incoming)
                st.session_state.page_mode = "Validation (uploaded)"
                st.success(f"Loaded {len(incoming)} rows from {up.name}.")
            except Exception as e:
                st.error(f"Failed to load file: {e}")

    with right:
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

    # Se ainda não existe nada em sessão (primeira carga): cria vazio
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

    # ========= PRÉ-VALIDAÇÃO (para preencher a coluna "⚠︎ issues" no editor) =========
    pre_export = drop_tail_blank_for_export(st.session_state.metadata_df).copy()
    # normaliza datas para a checagem
    for c in [x for x in pre_export.columns if x.lower() in [dc.lower() for dc in date_cols]]:
        pre_export[c] = pd.to_datetime(pre_export[c], errors="coerce").dt.date.astype("string")

    pre_key = resolve_unique_key(pre_export)
    pre_req = validate_required(pre_export, specs)
    pre_rx  = validate_regex(pre_export, specs)
    pre_uniq= validate_unique_key(pre_export, pre_key)
    pre_ena = validate_ena_checklist(pre_export)
    pre_sem = validate_semantics(pre_export)

    pre_reports = [pre_req, pre_rx, pre_uniq, pre_ena, pre_sem]
    pre_full = pd.concat([r for r in pre_reports if r is not None and not r.empty],
                         ignore_index=True) if any((r is not None and not r.empty) for r in pre_reports) \
                         else pd.DataFrame(columns=["row_index","field","value","valid","message"])

    # issues por linha para exibir no editor
    issues_by_row = {}
    for _, r in pre_full[~pre_full["valid"]].iterrows():
        i = r["row_index"]; f = str(r["field"])
        if i is None:
            continue
        issues_by_row.setdefault(i, set()).add(f)

    # Monta um DF de exibição: adiciona coluna "⚠︎ issues" somente leitura
    display_df = st.session_state.metadata_df.copy()
    issue_col = []
    # alinhar ao tamanho do display_df (inclui linha em branco no final)
    n_rows = len(display_df)
    for i in range(n_rows):
        if i < len(pre_export):
            short = ", ".join(sorted(issues_by_row.get(i, [])))
        else:
            short = ""
        issue_col.append(short)
    display_df[ISSUES_COL] = issue_col

    # -------- Toolbar --------
    st.markdown("### Metadata editor")
    st.caption("Use the toolbar to add, select, and delete rows. The last row is always blank for quick entry.")

    t1, t2, t3, t4, t5 = st.columns([1.1, 1.1, 1.1, 1.4, 4])
    with t1:
        if st.button("➕ Add example row"):
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
            base = st.session_state.metadata_df.drop(columns=[DELETE_COL, ISSUES_COL], errors="ignore")
            merged = pd.concat([drop_tail_blank_for_export(base), new], ignore_index=True)
            st.session_state.metadata_df = merged
            st.session_state.metadata_df[DELETE_COL] = False
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

    with t4:
        if st.button("🧹 Auto-fix common issues"):
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

    # garantir trailing blank e ORDER: ✖ primeiro; issues logo após
    st.session_state.metadata_df = ensure_tail_blank(st.session_state.metadata_df)
    # reconstruir display_df (pois toolbar pode ter alterado base)
    display_df = st.session_state.metadata_df.copy()
    # reanexar a coluna de issues calculada
    display_df[ISSUES_COL] = issue_col if len(issue_col) == len(display_df) else [""] * len(display_df)

    ordered_cols = [DELETE_COL] + [c for c in display_df.columns if c not in (DELETE_COL, ISSUES_COL)] + [ISSUES_COL]
    display_df = display_df[ordered_cols]
    display_df = coerce_date_dtypes(display_df, date_cols)

    # ---------- Editor (fallback) ----------
    edited = st.data_editor(
        display_df,
        column_config={
            DELETE_COL: st.column_config.CheckboxColumn("✖", help="Tick to mark this row for deletion."),
            **col_cfg,
            ISSUES_COL: st.column_config.TextColumn(ISSUES_COL, help="List of fields with issues in this row.", disabled=True),
        },
        hide_index=True,
        num_rows="dynamic",
        use_container_width=True
    )

    # aplicar edits → remover coluna de issues antes de salvar no estado
    if ISSUES_COL in edited.columns:
        edited_no_issues = edited.drop(columns=[ISSUES_COL])
    else:
        edited_no_issues = edited

    st.session_state.metadata_df = ensure_tail_blank(edited_no_issues)
    st.session_state.metadata_df = coerce_date_dtypes(st.session_state.metadata_df, date_cols)

    # deletar selecionados
    if st.button("🗑️ Delete selected rows", type="secondary", use_container_width=True):
        mask = st.session_state.metadata_df[DELETE_COL] != True
        st.session_state.metadata_df = st.session_state.metadata_df.loc[mask].drop(columns=[DELETE_COL], errors="ignore")
        st.session_state.metadata_df[DELETE_COL] = False
        st.session_state.metadata_df = coerce_date_dtypes(st.session_state.metadata_df, date_cols)
        st.session_state.metadata_df = ensure_tail_blank(st.session_state.metadata_df)

    # ---------- Validação "oficial" pós-edição ----------
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

    # status por linha (mirror/heatmap)
    if not export_df.empty:
        invalid_mask = build_invalid_mask(export_df, reports)
        row_has_issue = invalid_mask.any(axis=1)
        mirror = export_df.copy()
        mirror[STATUS_COL] = row_has_issue.map(lambda x: "Issues" if x else "Valid")
    else:
        invalid_mask = pd.DataFrame(columns=export_df.columns)
        mirror = export_df.copy()

    issues_count = (~full_report["valid"]).sum() if not full_report.empty else 0

    # ---------- Dataset summary ----------
    st.markdown("### Dataset summary")
    r1, r2, r3 = st.columns(3)
    with r1: st.metric("Rows (non-empty)", len(export_df))
    with r2: st.metric("Required fields", len(REQUIRED_FIELDS))
    with r3: st.metric("All issues", issues_count)

    # ---------- Cell inspector (detalhes dos erros por linha) ----------
    st.markdown("### Cell inspector")
    if len(export_df) == 0:
        st.info("No data yet. Start filling the table above or upload a CSV/Excel.")
    else:
        row_to_inspect = st.number_input(
            "Row number (1-based)", min_value=1, max_value=len(export_df), value=1, step=1
        )
        ri = row_to_inspect - 1
        probs = full_report[(full_report["row_index"] == ri) & (~full_report["valid"])]
        if not probs.empty:
            st.write("**Errors in this row:**")
            # ordenar por campo para facilitar a correção
            st.dataframe(probs[["field", "value", "message"]].sort_values("field").reset_index(drop=True), use_container_width=True)
        else:
            st.success("No errors in this row.")

    # ---------- Validation panel extra (heatmap e relatórios) ----------
    st.markdown("### Validation")
    st.caption("Fix red cells in the heatmap below. All checks must pass to enable Download.")

    tabs = st.tabs(["Heatmap", "Issues by column", "All issues"])
    with tabs[0]:
        if not export_df.empty:
            mirror_show = mirror[[STATUS_COL] + [c for c in mirror.columns if c != STATUS_COL]]
            style_mask = invalid_mask.reindex(columns=[c for c in mirror_show.columns if c != STATUS_COL], fill_value=False)
            styled = mirror_show.style.apply(
                lambda row: [""] + ["background-color: #ffe6e6" if style_mask.loc[row.name, col] else "" for col in style_mask.columns],
                axis=1
            )
            st.dataframe(styled, use_container_width=True)
        else:
            st.info("No data yet.")

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
    all_ok = full_report.empty
    if all_ok and not export_df.empty:
        buf = StringIO(); export_df.to_csv(buf, index=False)
        st.success("✅ All checks passed. You can download your CSV.")
        st.download_button("⬇️ Download CSV", buf.getvalue().encode("utf-8"),
                           file_name="metadata_validated.csv", mime="text/csv",
                           use_container_width=True)
    else:
        st.info("Complete Step 2 (fix all issues) to enable Download.")
