"""
Comparison Analysis - Streamlit app
Sales_SalesRtn dataset

Field mapping (same as analytics chatbot):
  Quantity      = SUM(QTY)                         (sales qty)
  Return Qty    = SUM(RTN_QTY)
  Net Quantity  = SUM(QTY - RTN_QTY)               (all rows)
  Sales Value   = SUM(NET_AMT) WHERE Trj_Type='Sales'
  Return Value  = SUM(NET_AMT) WHERE Trj_Type='Sales Rtn'
  Net Value     = Sales Value - Return Value
  Bill count    = COUNT(DISTINCT PDOC_NO)

Run:  streamlit run comparison_analysis.py
"""

import datetime as dt

import pandas as pd
import plotly.express as px
import streamlit as st

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
DATA_FILE = "Sales_SalesRtn.csv"

# metric -> (axis title, is_currency)
METRICS = {
    "Quantity":     ("Quantity (units)",      False),
    "Return Qty":   ("Return Qty (units)",    False),
    "Net Quantity": ("Net Quantity (units)",  False),
    "Sales Value":  ("Sales Value (\u20b9)",  True),
    "Return Value": ("Return Value (\u20b9)", True),
    "Net Value":    ("Net Value (\u20b9)",    True),
    "Bill count":   ("Bill Count",            False),
}

GRANULARITY = {
    "Year wise":  "Y",
    "Month wise": "M",
    "Week wise":  "W",
    "Day wise":   "D",
}

# separate colours for the two comparison series
COLOR_MAIN = "#2E86C1"   # blue  -> selected period
COLOR_CMP = "#E67E22"    # orange -> compare-with period

st.set_page_config(page_title="Comparison Analysis", layout="wide")


def fmt_value(v, currency):
    """Compact label for on-bar display / metrics."""
    if currency:
        av = abs(v)
        if av >= 1e7:
            return f"\u20b9{v/1e7:,.2f} Cr"
        if av >= 1e5:
            return f"\u20b9{v/1e5:,.2f} L"
        return f"\u20b9{v:,.0f}"
    return f"{v:,.0f}"


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #
@st.cache_data
def load_data(path):
    df = pd.read_csv(path, low_memory=False)
    df["DOC_DT"] = pd.to_datetime(df["DOC_DT"], errors="coerce")
    for col in ["QTY", "RTN_QTY", "NET_AMT"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    df = df.dropna(subset=["DOC_DT"])
    return df


# --------------------------------------------------------------------------- #
# Bucketing + metric computation
# --------------------------------------------------------------------------- #
def add_bucket(df, freq):
    """Add a sortable period key and a display label per row."""
    d = df.copy()
    if freq == "Y":
        d["_key"] = d["DOC_DT"].dt.to_period("Y")
        d["_label"] = d["DOC_DT"].dt.year.astype(str)
    elif freq == "M":
        p = d["DOC_DT"].dt.to_period("M")
        d["_key"] = p
        d["_label"] = p.dt.strftime("%b %Y")
    elif freq == "W":
        p = d["DOC_DT"].dt.to_period("W")
        d["_key"] = p
        # label = ISO week number, year-prefixed so weeks stay unique/ordered
        # across the 2023 -> 2024 boundary (e.g. "2024-W05")
        iso = p.dt.start_time.dt.isocalendar()
        d["_label"] = (
            iso["year"].astype(str)
            + "-W"
            + iso["week"].astype(int).map("{:02d}".format)
        )
    else:  # daily
        d["_key"] = d["DOC_DT"].dt.to_period("D")
        d["_label"] = d["DOC_DT"].dt.strftime("%d %b %Y")
    return d


def compute_metric(df, metric):
    """Return a DataFrame [_key, _label, value] aggregated by bucket."""
    keys = df[["_key", "_label"]].drop_duplicates()

    if metric == "Quantity":
        s = df.groupby("_key")["QTY"].sum()
    elif metric == "Return Qty":
        s = df.groupby("_key")["RTN_QTY"].sum()
    elif metric == "Net Quantity":
        s = (df["QTY"] - df["RTN_QTY"]).groupby(df["_key"]).sum()
    elif metric == "Sales Value":
        s = df[df["Trj_Type"] == "Sales"].groupby("_key")["NET_AMT"].sum()
    elif metric == "Return Value":
        s = df[df["Trj_Type"] == "Sales Rtn"].groupby("_key")["NET_AMT"].sum()
    elif metric == "Net Value":
        sales = df[df["Trj_Type"] == "Sales"].groupby("_key")["NET_AMT"].sum()
        ret = df[df["Trj_Type"] == "Sales Rtn"].groupby("_key")["NET_AMT"].sum()
        s = sales.sub(ret, fill_value=0)
    else:  # Bill count
        s = df.groupby("_key")["PDOC_NO"].nunique()

    out = s.rename("value").reset_index()
    out = keys.merge(out, on="_key", how="left").fillna({"value": 0})
    out = out.sort_values("_key")
    return out


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
try:
    df = load_data(DATA_FILE)
except FileNotFoundError:
    st.error(f"'{DATA_FILE}' not found next to this script.")
    up = st.file_uploader("Upload Sales_SalesRtn.csv", type="csv")
    if up is None:
        st.stop()
    df = load_data(up)

min_dt = df["DOC_DT"].min().date()
max_dt = df["DOC_DT"].max().date()

st.sidebar.header("Filters")

from_date = st.sidebar.date_input("From date", value=min_dt,
                                  min_value=min_dt, max_value=max_dt)
to_date = st.sidebar.date_input("To date", value=max_dt,
                                min_value=min_dt, max_value=max_dt)

metric = st.sidebar.selectbox("Compare for", list(METRICS.keys()))

gran_label = st.sidebar.radio(
    "Group by", list(GRANULARITY.keys()), index=1  # default: Month wise
)

if from_date > to_date:
    st.sidebar.error("From date must be on or before To date.")
    st.stop()

# --- Compare with (period-over-period overlay) ------------------------------ #
st.sidebar.markdown("---")
st.sidebar.subheader("Compare with")
compare_on = st.sidebar.checkbox("Enable comparison period", value=False)

cfrom = cto = None
if compare_on:
    # default = an equal-length window ending just before the main From date
    span = to_date - from_date
    def_cto = max(min_dt, from_date - dt.timedelta(days=1))
    def_cfrom = max(min_dt, def_cto - span)
    cfrom = st.sidebar.date_input("From date ", value=def_cfrom,
                                  min_value=min_dt, max_value=max_dt, key="cfrom")
    cto = st.sidebar.date_input("To date ", value=def_cto,
                                min_value=min_dt, max_value=max_dt, key="cto")
    if cfrom > cto:
        st.sidebar.error("Compare From date must be on or before Compare To date.")
        st.stop()


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
st.title("Comparison analysis")

mask = (df["DOC_DT"].dt.date >= from_date) & (df["DOC_DT"].dt.date <= to_date)
scoped = df.loc[mask]

if scoped.empty:
    st.warning("No records in the selected date range.")
    st.stop()

freq = GRANULARITY[gran_label]
result = compute_metric(add_bucket(scoped, freq), metric)

y_title, is_currency = METRICS[metric]
x_title = gran_label.replace(" wise", "").strip()

main_lbl = f"{from_date:%d %b %Y} \u2013 {to_date:%d %b %Y}"

# --- compute comparison series (if enabled) --------------------------------- #
result_cmp = None
cmp_lbl = None
if compare_on:
    cmask = (df["DOC_DT"].dt.date >= cfrom) & (df["DOC_DT"].dt.date <= cto)
    cscoped = df.loc[cmask]
    cmp_lbl = f"{cfrom:%d %b %Y} \u2013 {cto:%d %b %Y}"
    if cscoped.empty:
        st.warning("No records in the comparison date range \u2014 showing main series only.")
        compare_on = False
    else:
        result_cmp = compute_metric(add_bucket(cscoped, freq), metric)


# --- difference summary ----------------------------------------------------- #
def _fmt(v):
    return fmt_value(v, is_currency)

if compare_on and result_cmp is not None:
    main_total = result["value"].sum()
    cmp_total = result_cmp["value"].sum()
    diff = main_total - cmp_total
    pct = (diff / cmp_total * 100) if cmp_total else float("nan")
    c1, c2, c3 = st.columns(3)
    c1.metric(f"Selected  ({main_lbl})", _fmt(main_total))
    c2.metric(f"Compare  ({cmp_lbl})", _fmt(cmp_total))
    pct_txt = "n/a" if pd.isna(pct) else f"{pct:+.1f}%"
    c3.metric("Difference", _fmt(diff), pct_txt)
else:
    total = result["value"].sum()
    st.caption(
        f"**{metric}** \u2022 {main_lbl} \u2022 {gran_label}  |  Total: {_fmt(total)}"
    )

# --- build aligned plotting frame (position-based overlay) ------------------ #
main_r = result.reset_index(drop=True)
rows, order = [], []


def _push(x, series, value, period):
    if x not in order:
        order.append(x)
    rows.append({"x": x, "series": series, "value": value,
                 "period": period, "text": fmt_value(value, is_currency)})


if compare_on and result_cmp is not None:
    cmp_r = result_cmp.reset_index(drop=True)
    n = max(len(main_r), len(cmp_r))
    for i in range(n):
        # shared x tick = main period at this position (fallback to compare's)
        xlab = (main_r.loc[i, "_label"] if i < len(main_r)
                else cmp_r.loc[i, "_label"])
        if i < len(main_r):
            _push(xlab, main_lbl, main_r.loc[i, "value"], main_r.loc[i, "_label"])
        if i < len(cmp_r):
            _push(xlab, cmp_lbl, cmp_r.loc[i, "value"], cmp_r.loc[i, "_label"])
    color_map = {main_lbl: COLOR_MAIN, cmp_lbl: COLOR_CMP}
    series_order = [main_lbl, cmp_lbl]
else:
    for _, r in main_r.iterrows():
        _push(r["_label"], main_lbl, r["value"], r["_label"])
    color_map = {main_lbl: COLOR_MAIN}
    series_order = [main_lbl]

plot_df = pd.DataFrame(rows)

fig = px.bar(
    plot_df,
    x="x",
    y="value",
    color="series",
    text="text",
    barmode="group",
    labels={"x": x_title, "value": y_title, "series": "Period"},
    category_orders={"x": order, "series": series_order},
    color_discrete_map=color_map,
    custom_data=["period"],
)

hover_val = "\u20b9 %{y:,.0f}" if is_currency else "%{y:,.0f}"
fig.update_traces(
    textposition="outside",
    cliponaxis=False,
    # customdata[0] = the series' true period (x tick may show the main period)
    hovertemplate=(f"<b>%{{customdata[0]}}</b><br>{y_title}: {hover_val}"
                   f"<extra>%{{fullData.name}}</extra>"),
)
fig.update_layout(
    xaxis=dict(
        type="category",
        title=dict(text=x_title, font=dict(size=14)),
        tickangle=-45,
    ),
    yaxis=dict(title=dict(text=y_title, font=dict(size=14))),
    bargap=0.25,
    bargroupgap=0.05,
    height=560,
    margin=dict(t=50, b=80),
    uniformtext=dict(minsize=9, mode="hide"),
    legend=dict(orientation="h", yanchor="bottom", y=1.02,
                xanchor="left", x=0, title_text=""),
    showlegend=compare_on,
)

st.plotly_chart(fig, use_container_width=True)

with st.expander("View data table"):
    tbl = result[["_label", "value"]].rename(
        columns={"_label": x_title, "value": f"{metric} (selected)"}
    )
    if compare_on and result_cmp is not None:
        # align both series side by side by ordinal position
        a = result.reset_index(drop=True)[["_label", "value"]]
        b = result_cmp.reset_index(drop=True)[["_label", "value"]]
        tbl = pd.DataFrame({
            x_title: a["_label"],
            "Selected period": a["value"],
            f"Compare period ({x_title.lower()})": b["_label"].reindex(a.index),
            "Compare value": b["value"].reindex(a.index),
        })
    st.dataframe(tbl, use_container_width=True, hide_index=True)
