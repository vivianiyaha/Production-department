"""
Cardstel Solutions Ltd - Financial Card Perso Production KPI Tracker
--------------------------------------------------------------------
Tracks daily / monthly / quarterly / yearly production output against targets.

Data files (in ./data):
  production_data.csv : Production Date, Shift Type, Client, Card Type,
                        Quantity Produced, Machine Used, Operator Name
  kpi_targets.csv     : created automatically, editable from the Targets tab

NOTE: No "Job ID" field is stored, displayed or exported (sensitive data).
      If an uploaded CSV contains one, it is dropped on load.

Run:  streamlit run app.py
"""
from __future__ import annotations

import calendar
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
DATA_DIR = Path(__file__).parent / "data"
PROD_FILE = DATA_DIR / "production_data.csv"
TARGET_FILE = DATA_DIR / "kpi_targets.csv"

DATE, SHIFT, CLIENT, CARD, QTY, MACHINE, OPERATOR = (
    "Production Date", "Shift Type", "Client", "Card Type",
    "Quantity Produced", "Machine Used", "Operator Name",
)
COLS = [DATE, SHIFT, CLIENT, CARD, QTY, MACHINE, OPERATOR]
DATE_FMT = "%d/%m/%y"  # e.g. 13/08/26

VIEWS = ["Daily Entry & Tracking", "Monthly", "Quarterly", "Yearly Performance Summary"]
SHIFTS = ["Morning", "Afternoon", "Night"]
MACHINES = ["MATICA 1", "MATICA 2", "MS 5000-1", "MS 5000-2", "PIOTEC-1", "PIOTEC-2"]
DEFAULT_OPERATORS = ["Jennifer", "Emmanuel", "Godday", "Kingsley", "Judith", "Naomi"]
DEFAULT_CLIENTS = ["Opay", "Polaris", "Moniepoint", "Access Bank", "GTBank", "Zenith Bank"]
DEFAULT_CARDS = ["Verve", "Afrigo", "Mastercard", "Visa"]

TARGET_COLS = ["Scope", "Name", "Daily Target", "Monthly Target", "Yearly Target"]
# A target of 0 on an Operator/Machine row means "not set": an equal share of the
# global target is used instead.
DEFAULT_GLOBAL = {"Daily Target": 60_000, "Monthly Target": 1_300_000, "Yearly Target": 15_600_000}

st.set_page_config(page_title="Perso Production KPI Tracker", page_icon="💳", layout="wide")


# ----------------------------------------------------------------------------
# Data loading
# ----------------------------------------------------------------------------
def clean_production(df: pd.DataFrame) -> pd.DataFrame:
    """Validate, type-cast and tidy a raw production dataframe."""
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    # Privacy guard: never keep a Job ID column
    df = df.drop(columns=[c for c in df.columns if c.lower().replace(" ", "").replace("_", "") == "jobid"])
    missing = [c for c in COLS if c not in df.columns]
    if missing:
        raise ValueError(f"CSV is missing required column(s): {', '.join(missing)}")
    df = df[COLS]
    raw = df[DATE].astype(str).str.strip()
    parsed = pd.to_datetime(raw, format=DATE_FMT, errors="coerce")  # dd/mm/yy
    df[DATE] = parsed.fillna(pd.to_datetime(raw, dayfirst=True, errors="coerce", format="mixed"))
    df[QTY] = pd.to_numeric(df[QTY].astype(str).str.replace(",", ""), errors="coerce")
    df = df.dropna(subset=[DATE, QTY]).copy()
    df[QTY] = df[QTY].astype(int)
    for col in (SHIFT, CLIENT, CARD, MACHINE, OPERATOR):
        df[col] = df[col].astype(str).str.strip()
    return df.sort_values(DATE).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_default(path: str, mtime: float) -> pd.DataFrame:
    """Cached load of the repo CSV (mtime busts the cache when the file changes)."""
    return clean_production(pd.read_csv(path))


def load_targets(operators: list[str]) -> pd.DataFrame:
    """Load saved targets, making sure every operator/machine has a row."""
    if TARGET_FILE.exists():
        t = pd.read_csv(TARGET_FILE)
    else:
        t = pd.DataFrame([{"Scope": "Global", "Name": "All", **DEFAULT_GLOBAL}])
    have = set(zip(t["Scope"], t["Name"]))
    rows = [("Operator", o) for o in operators] + [("Machine", m) for m in MACHINES]
    extra = [{"Scope": s, "Name": n, "Daily Target": 0, "Monthly Target": 0, "Yearly Target": 0}
             for s, n in rows if (s, n) not in have]
    return pd.concat([t, pd.DataFrame(extra)], ignore_index=True)[TARGET_COLS]


# ----------------------------------------------------------------------------
# Period filtering & target maths
# ----------------------------------------------------------------------------
def sidebar_filters(df: pd.DataFrame) -> tuple[str, dict]:
    """Render sidebar view + date selectors; return (view, selection dict)."""
    view = st.sidebar.radio("View", VIEWS)
    lo, hi = df[DATE].min().date(), max(df[DATE].max().date(), date.today())
    years = sorted(df[DATE].dt.year.unique(), reverse=True)
    latest = df[DATE].max()
    sel: dict = {}

    if view == VIEWS[0]:
        picked = st.sidebar.date_input("Date", value=latest.date(), min_value=lo, max_value=hi)
        sel["date"] = pd.Timestamp(picked)
        sel["label"] = sel["date"].strftime("%d %b %Y")
    else:
        sel["year"] = st.sidebar.selectbox("Year", years)
        if view == VIEWS[1]:
            default_m = latest.month - 1 if sel["year"] == latest.year else 0
            sel["month"] = st.sidebar.selectbox(
                "Month", range(1, 13), index=default_m, format_func=lambda m: calendar.month_name[m])
            sel["label"] = f"{calendar.month_name[sel['month']]} {sel['year']}"
        elif view == VIEWS[2]:
            default_q = (latest.quarter - 1) if sel["year"] == latest.year else 0
            sel["quarter"] = st.sidebar.selectbox("Quarter", [1, 2, 3, 4], index=default_q,
                                                  format_func=lambda q: f"Q{q}")
            sel["label"] = f"Q{sel['quarter']} {sel['year']}"
        else:
            sel["label"] = str(sel["year"])
    return view, sel


def filter_period(df: pd.DataFrame, view: str, sel: dict) -> pd.DataFrame:
    d = df[DATE]
    if view == VIEWS[0]:
        return df[d == sel["date"]]
    mask = d.dt.year == sel["year"]
    if view == VIEWS[1]:
        mask &= d.dt.month == sel["month"]
    elif view == VIEWS[2]:
        mask &= d.dt.quarter == sel["quarter"]
    return df[mask]


def target_basis(view: str) -> tuple[str, int]:
    """Which target column applies to a view, and its multiplier."""
    return {VIEWS[0]: ("Daily Target", 1), VIEWS[1]: ("Monthly Target", 1),
            VIEWS[2]: ("Monthly Target", 3), VIEWS[3]: ("Yearly Target", 1)}[view]


def resolve_target(tdf: pd.DataFrame, scope: str, name: str, col: str, mult: int, n_entities: int) -> float:
    """Target for one operator/machine/global entity for the selected period."""
    glob = float(tdf.loc[tdf["Scope"] == "Global", col].iloc[0])
    if scope == "Global":
        return glob * mult
    row = tdf[(tdf["Scope"] == scope) & (tdf["Name"] == name)]
    own = float(row[col].iloc[0]) if not row.empty else 0
    return (own if own > 0 else glob / max(n_entities, 1)) * mult


def variance_table(period_df, tdf, scope, names, col, mult) -> pd.DataFrame:
    """Actual vs target per operator or machine, incl. variance and achievement %."""
    key = OPERATOR if scope == "Operator" else MACHINE
    actual = period_df.groupby(key)[QTY].sum().reindex(names, fill_value=0)
    out = pd.DataFrame({scope: names, "Actual": actual.values})
    out["Target"] = [resolve_target(tdf, scope, n, col, mult, len(names)) for n in names]
    out["Variance"] = out["Actual"] - out["Target"]
    out["Achievement %"] = (out["Actual"] / out["Target"].replace(0, pd.NA) * 100).astype(float).round(1)
    return out


def build_kpi_report(period_df, tdf, operators, col, mult, label) -> pd.DataFrame:
    """Flat KPI report (overall + operator + machine) used for CSV export."""
    total = int(period_df[QTY].sum())
    tgt = resolve_target(tdf, "Global", "All", col, mult, 1)
    overall = pd.DataFrame([{"Level": "Overall", "Name": "All", "Actual": total, "Target": tgt,
                             "Variance": total - tgt,
                             "Achievement %": round(total / tgt * 100, 1) if tgt else None}])
    ops = variance_table(period_df, tdf, "Operator", operators, col, mult).rename(columns={"Operator": "Name"})
    mch = variance_table(period_df, tdf, "Machine", MACHINES, col, mult).rename(columns={"Machine": "Name"})
    ops.insert(0, "Level", "Operator")
    mch.insert(0, "Level", "Machine")
    rep = pd.concat([overall, ops, mch], ignore_index=True)
    rep.insert(0, "Period", label)
    return rep


# ----------------------------------------------------------------------------
# UI sections
# ----------------------------------------------------------------------------
def kpi_cards(period_df, target, top_operator):
    total = int(period_df[QTY].sum())
    shifts = period_df[[DATE, SHIFT]].drop_duplicates().shape[0]
    ach = total / target * 100 if target else 0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Cards Produced", f"{total:,}", delta=f"{total - target:,.0f} vs target")
    c2.metric("Target Achievement Rate", f"{ach:.1f}%")
    c3.metric("Total Shifts Completed", f"{shifts:,}")
    c4.metric("Top Performing Operator", top_operator)


def chart_operators(op_tbl):
    fig = px.bar(op_tbl.sort_values("Actual"), x="Actual", y="Operator", orientation="h",
                 text="Actual", color="Achievement %", color_continuous_scale="RdYlGn",
                 title="Total Output by Operator")
    fig.update_traces(texttemplate="%{text:,}")
    fig.update_layout(coloraxis_colorbar_title="Ach. %", yaxis_title=None, xaxis_title="Cards")
    st.plotly_chart(fig, width="stretch")


def chart_machines(period_df):
    by = period_df.groupby([MACHINE, SHIFT])[QTY].sum().reset_index()
    fig = px.bar(by, x=MACHINE, y=QTY, color=SHIFT, title="Machine Output by Shift",
                 category_orders={MACHINE: MACHINES, SHIFT: SHIFTS}, barmode="stack")
    fig.update_layout(xaxis_title=None, yaxis_title="Cards")
    st.plotly_chart(fig, width="stretch")

    # Utilization = shifts a machine actually ran / shifts available (3 per production day)
    days = period_df[DATE].nunique()
    runs = period_df.groupby(MACHINE)[[DATE, SHIFT]].apply(lambda g: g.drop_duplicates().shape[0])
    util = pd.DataFrame({"Machine": MACHINES})
    util["Shifts Run"] = [int(runs.get(m, 0)) for m in MACHINES]
    util["Utilization %"] = [round(r / (days * 3) * 100, 1) if days else 0 for r in util["Shifts Run"]]
    util["Output"] = [int(period_df.loc[period_df[MACHINE] == m, QTY].sum()) for m in MACHINES]
    st.dataframe(util, hide_index=True, width="stretch")


def chart_trend(full_df, view, sel, tdf):
    """Daily output (month view) or monthly output (quarter/year view) against target."""
    if view in (VIEWS[0], VIEWS[1]):
        ref = sel["date"] if view == VIEWS[0] else pd.Timestamp(sel["year"], sel["month"], 1)
        data = full_df[(full_df[DATE].dt.year == ref.year) & (full_df[DATE].dt.month == ref.month)]
        series = data.groupby(DATE)[QTY].sum().reset_index()
        tgt, title = resolve_target(tdf, "Global", "All", "Daily Target", 1, 1), \
            f"Daily Output vs Daily Target - {ref:%B %Y}"
        x = DATE
    else:
        data = full_df[full_df[DATE].dt.year == sel["year"]]
        if view == VIEWS[2]:
            data = data[data[DATE].dt.quarter == sel["quarter"]]
        data = data.assign(Month=data[DATE].dt.to_period("M").dt.to_timestamp())
        series = data.groupby("Month")[QTY].sum().reset_index()
        tgt, title = resolve_target(tdf, "Global", "All", "Monthly Target", 1, 1), \
            f"Monthly Output vs Monthly Target - {sel['label']}"
        x = "Month"
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=series[x], y=series[QTY], mode="lines+markers", name="Actual"))
    fig.add_trace(go.Scatter(x=series[x], y=[tgt] * len(series), mode="lines", name="Target",
                             line=dict(dash="dash", color="crimson")))
    fig.update_layout(title=title, yaxis_title="Cards", xaxis_title=None, hovermode="x unified")
    st.plotly_chart(fig, width="stretch")


def targets_tab(tdf, operators, period_df, view, col, mult):
    st.subheader("Set Production Targets")
    st.caption("Set the Global row, and optionally per-Operator / per-Machine targets. "
               "A value of 0 means 'not set' - an equal share of the global target is used.")
    edited = st.data_editor(
        tdf, hide_index=True, width="stretch", disabled=["Scope", "Name"],
        column_config={c: st.column_config.NumberColumn(c, min_value=0, step=1000, format="%d")
                       for c in TARGET_COLS[2:]})
    if st.button("💾 Save targets", type="primary"):
        DATA_DIR.mkdir(exist_ok=True)
        edited.to_csv(TARGET_FILE, index=False)
        st.success("Targets saved. Commit data/kpi_targets.csv to keep them in GitHub.")
        st.rerun()

    st.subheader("Variance: Actual vs Target")
    a, b = st.columns(2)
    for holder, scope, names in ((a, "Operator", operators), (b, "Machine", MACHINES)):
        tbl = variance_table(period_df, tdf, scope, names, col, mult)
        with holder:
            st.markdown(f"**By {scope}**")
            st.dataframe(tbl.style.format({"Actual": "{:,.0f}", "Target": "{:,.0f}",
                                           "Variance": "{:+,.0f}", "Achievement %": "{:.1f}%"}),
                         hide_index=True, width="stretch")


def entry_tab(full_df, operators, sel):
    st.subheader("Log Production")
    if st.session_state.pop("flash", None):
        st.success("Entry saved to data/production_data.csv")
    with st.form("entry_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        d = c1.date_input("Production Date", value=sel["date"].date())
        shift = c2.selectbox(SHIFT, SHIFTS)
        machine = c3.selectbox(MACHINE, MACHINES)
        operator = c4.selectbox(OPERATOR, operators)
        c5, c6, c7 = st.columns(3)
        client = c5.selectbox(CLIENT, sorted(set(DEFAULT_CLIENTS) | set(full_df[CLIENT])))
        card = c6.selectbox(CARD, sorted(set(DEFAULT_CARDS) | set(full_df[CARD])))
        qty = c7.number_input(QTY, min_value=1, step=500, value=5000)
        if st.form_submit_button("Add entry", type="primary"):
            row = pd.DataFrame([{DATE: d.strftime(DATE_FMT), SHIFT: shift, CLIENT: client, CARD: card,
                                 QTY: int(qty), MACHINE: machine, OPERATOR: operator}])
            row.to_csv(PROD_FILE, mode="a", header=not PROD_FILE.exists(), index=False)
            st.cache_data.clear()
            st.session_state["flash"] = True
            st.rerun()

    st.markdown(f"**Entries for {sel['label']}**")
    day = full_df[full_df[DATE] == sel["date"]]
    if day.empty:
        st.info("No production recorded for this date yet.")
    else:
        pivot = day.pivot_table(index=SHIFT, columns=MACHINE, values=QTY, aggfunc="sum", fill_value=0)
        st.dataframe(pivot.reindex(index=SHIFTS, columns=MACHINES).fillna(0).astype(int),
                     width="stretch")


def records_tab(period_df, report, label):
    st.subheader("Production Records")
    show = period_df.assign(**{DATE: period_df[DATE].dt.strftime(DATE_FMT)})
    st.dataframe(show, hide_index=True, width="stretch")
    safe = label.replace(" ", "_")
    c1, c2, _ = st.columns([1, 1, 2])
    c1.download_button("⬇️ Production records (CSV)", show.to_csv(index=False).encode("utf-8"),
                       file_name=f"production_{safe}.csv", mime="text/csv")
    c2.download_button("⬇️ KPI report (CSV)", report.to_csv(index=False).encode("utf-8"),
                       file_name=f"kpi_report_{safe}.csv", mime="text/csv")
    st.caption("KPI report: overall, per-operator and per-machine actual vs target.")


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    st.title("💳 Financial Card Perso Production - KPI Tracker")
    st.caption("Cardstel Solutions Ltd")

    st.sidebar.header("Filters")
    upload = st.sidebar.file_uploader("Load a different production CSV (optional)", type="csv")
    try:
        if upload:
            df = clean_production(pd.read_csv(upload))
        else:
            df = load_default(str(PROD_FILE), PROD_FILE.stat().st_mtime)
    except Exception as exc:  # missing file, bad columns, etc.
        st.error(f"Could not load production data: {exc}")
        st.stop()
    if df.empty:
        st.warning("No valid production rows found.")
        st.stop()

    operators = sorted(set(DEFAULT_OPERATORS) | set(df[OPERATOR]))
    tdf = load_targets(operators)
    view, sel = sidebar_filters(df)
    col, mult = target_basis(view)

    period_df = filter_period(df, view, sel)
    target = resolve_target(tdf, "Global", "All", col, mult, 1)
    op_tbl = variance_table(period_df, tdf, "Operator", operators, col, mult)
    top = "-" if period_df.empty else period_df.groupby(OPERATOR)[QTY].sum().idxmax()

    st.subheader(f"{view} - {sel['label']}")
    kpi_cards(period_df, target, top)
    st.divider()

    tab_names = ["📊 Analytics", "🎯 Targets & Variance", "🗂 Records & Export"]
    if view == VIEWS[0]:
        tab_names.insert(0, "➕ Log Production")
    tabs = dict(zip(tab_names, st.tabs(tab_names)))

    if "➕ Log Production" in tabs:
        with tabs["➕ Log Production"]:
            if upload:
                st.info("Entry is disabled while viewing an uploaded CSV.")
            else:
                entry_tab(df, operators, sel)
    with tabs["📊 Analytics"]:
        if period_df.empty:
            st.info("No production data for the selected period.")
        else:
            left, right = st.columns(2)
            with left:
                chart_operators(op_tbl)
            with right:
                chart_machines(period_df)
        chart_trend(df, view, sel, tdf)
    with tabs["🎯 Targets & Variance"]:
        targets_tab(tdf, operators, period_df, view, col, mult)
    with tabs["🗂 Records & Export"]:
        records_tab(period_df, build_kpi_report(period_df, tdf, operators, col, mult, sel["label"]),
                    sel["label"])


if __name__ == "__main__":
    main()
