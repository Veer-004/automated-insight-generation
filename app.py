"""
app.py - Streamlit dashboard for the Auto-Analytics Engine.

Run with:  streamlit run app.py

This file only handles the UI (sidebar filters, sliders, charts, tables,
downloads). All the analytics live in analytics.py; all styling helpers
(colours, CSS, chart theme, cards) live in ui.py.
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

import analytics as an
import ui

DATA_DIR = Path(__file__).parent / "data"
DL_ICON = ":material/download:"

st.set_page_config(page_title="Auto-Analytics Engine", page_icon="📊", layout="wide")


@st.cache_data
def load(source):
    """Cached wrapper so the CSV is not re-read on every slider move."""
    return an.load_data(source)


def download_button(df, label, filename, key):
    """One-line helper for CSV exports."""
    st.download_button(label, df.to_csv(index=False).encode("utf-8"),
                       file_name=filename, mime="text/csv", key=key, icon=DL_ICON)


# ==========================================================================
# Sidebar - data source, filters (Part A) and thresholds (configurable)
# ==========================================================================
ui.sidebar_brand()
ui.theme_toggle()          # Light / Dark switch (kept in session state + URL)
ui.inject_css()
C = ui.P()                 # active colour palette for this session

ui.sidebar_heading("DATA SOURCE", C["blue"])
datasets = sorted(p.name for p in DATA_DIR.glob("*.csv"))
default_idx = datasets.index("sample_data.csv") if "sample_data.csv" in datasets else 0
choice = st.sidebar.selectbox("Bundled dataset", datasets, index=default_idx)
uploaded = st.sidebar.file_uploader("...or upload your own CSV", type="csv")

try:
    raw_df = load(uploaded) if uploaded else load(DATA_DIR / choice)
except Exception as err:                       # bad CSV -> friendly message instead of a crash
    st.error(f"Could not load the CSV: {err}", icon=":material/error:")
    st.stop()

all_indicators = an.get_indicators(raw_df)

ui.sidebar_heading("FILTERS", C["teal"])
districts = st.sidebar.multiselect("District", sorted(raw_df["district"].unique()),
                                   default=sorted(raw_df["district"].unique()))
months = st.sidebar.multiselect("Month", sorted(raw_df["month"].unique()),
                                default=sorted(raw_df["month"].unique()))
indicators = st.sidebar.multiselect("Indicator", all_indicators, default=all_indicators,
                                    format_func=an.pretty_name)

ui.sidebar_heading("DETECTION SETTINGS", C["violet"])
trend_threshold = st.sidebar.slider("Significant change threshold (%)", 1.0, 50.0, 10.0, 1.0)
outlier_method = st.sidebar.radio("Outlier method", ["IQR", "Z-score"], horizontal=True)
if outlier_method == "IQR":
    iqr_k = st.sidebar.slider("IQR multiplier (k)", 0.5, 3.0, 1.5, 0.1)
    z_threshold = 3.0
else:
    z_threshold = st.sidebar.slider("Z-score threshold", 1.0, 4.0, 3.0, 0.1)
    iqr_k = 1.5
corr_threshold = st.sidebar.slider("Correlation threshold |r|", 0.30, 0.95, 0.70, 0.05)
coverage_target = st.sidebar.slider("Coverage target (%) for breaches", 50.0, 100.0, 80.0, 1.0)

# Apply filters - every chart/table below uses this filtered frame (live filters)
df = raw_df[raw_df["district"].isin(districts) & raw_df["month"].isin(months)]
if df.empty or not indicators:
    st.warning("No data for the current filters. Select at least one district, month and indicator.",
               icon=":material/filter_alt_off:")
    st.stop()
df = df[an.ID_COLUMNS + indicators]

# Run the whole engine on the filtered data
results = an.run_pipeline(df, indicators, trend_threshold, outlier_method, iqr_k,
                          z_threshold, corr_threshold, coverage_target)
insights = results["insights"]

# ==========================================================================
# Hero header + KPI cards
# ==========================================================================
ui.hero(uploaded.name if uploaded else choice)

n_high = int((insights["severity"] == "High").sum())
ui.kpi_cards([
    ("Total records", len(df), f"of {len(raw_df)} rows loaded", "database", C["blue"]),
    ("Districts analyzed", df["district"].nunique(),
     f"of {raw_df['district'].nunique()} available", "pin", C["teal"]),
    ("Months covered", df["month"].nunique(), f"{df['month'].min()} → {df['month'].max()}",
     "calendar", C["violet"]),
    ("Total insights", len(insights), "auto-generated findings", "zap", C["amber"]),
    ("High severity", n_high,
     f"{n_high / len(insights):.0%} of insights" if len(insights) else "none found", "alert", C["coral"]),
])

tab_ins, tab_trend, tab_out, tab_corr, tab_data = st.tabs([
    ":material/lightbulb: Insights", ":material/trending_up: Trends",
    ":material/scatter_plot: Outliers", ":material/grid_on: Correlations",
    ":material/table_chart: Data & Validation"])

# ==========================================================================
# Tab 1 - Insights (Part E + severity bar chart)
# ==========================================================================
with tab_ins:
    if insights.empty:
        st.info("No insights for the current filters/thresholds. Try lowering a threshold.",
                icon=":material/info:")
    else:
        c1, c2 = st.columns(2)
        sev_counts = (insights["severity"].value_counts()
                      .reindex(an.SEVERITY_ORDER, fill_value=0).reset_index())
        sev_counts.columns = ["severity", "count"]
        sev_counts["label"] = [f"{c}  ({c / len(insights):.0%})" for c in sev_counts["count"]]
        fig = px.bar(sev_counts, y="severity", x="count", color="severity", text="label",
                     orientation="h", color_discrete_map=ui.SEVERITY_COLORS,
                     category_orders={"severity": an.SEVERITY_ORDER},
                     labels={"count": "Number of insights", "severity": ""})
        fig.update_traces(marker_cornerradius=8, width=0.6, textposition="outside",
                          textfont=dict(size=13, color=C["text"]),
                          hovertemplate="<b>%{y}</b><br>%{x} insights<extra></extra>")
        fig.update_layout(showlegend=False, bargap=0.3)
        fig.update_xaxes(range=[0, sev_counts["count"].max() * 1.35])
        with c1.container(key="card_sev"):
            ui.show_chart(ui.style_fig(fig, "Insights by severity", "How urgent are the findings?", 300))

        type_counts = insights.groupby(["type", "severity"]).size().reset_index(name="count")
        type_counts["type"] = type_counts["type"].str.replace("_", " ").str.title()
        fig = px.bar(type_counts, x="type", y="count", color="severity", text="count",
                     color_discrete_map=ui.SEVERITY_COLORS,
                     category_orders={"severity": an.SEVERITY_ORDER,
                                      "type": [t.replace("_", " ").title() for t in an.TYPE_ORDER]},
                     labels={"type": "", "count": "Number of insights", "severity": "Severity"})
        fig.update_traces(marker_cornerradius=6, textfont=dict(color="#fff", size=12),
                          hovertemplate="<b>%{x}</b><br>%{y} insights<extra>%{fullData.name}</extra>")
        fig.update_layout(bargap=0.4, legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center", title=None))
        with c2.container(key="card_type"):
            ui.show_chart(ui.style_fig(fig, "Insights by type", "Which detector produced them?", 300))

        # Extra filters just for the insight list
        f1, f2 = st.columns(2)
        sev_filter = f1.multiselect("Severity", an.SEVERITY_ORDER, default=an.SEVERITY_ORDER)
        type_filter = f2.multiselect("Insight type", an.TYPE_ORDER, default=an.TYPE_ORDER)
        shown = insights[insights["severity"].isin(sev_filter) & insights["type"].isin(type_filter)]

        ui.section_title(f"Top insights ({len(shown)})", "Highest-priority findings first")
        ui.insight_cards(shown.head(6))

        st.write("")
        with st.container(key="card_ins_table"):
            ui.section_title("All insights", "Severity and type shown as badges · sort with the controls below")
            s1, s2, _ = st.columns([2, 1.3, 2], vertical_alignment="bottom")
            ins_sort_keys = {"Severity": "severity", "Insight ID": "insight_id", "Type": "type",
                             "Entity": "entity", "Change %": "change_pct", "Value": "value"}
            ins_sort = s1.selectbox("Sort by", list(ins_sort_keys), key="ins_sort")
            ins_desc = s2.toggle("Descending", value=ins_sort in ("Severity", "Change %"),
                                 key=f"ins_desc_{ins_sort}")
            ins_col = ins_sort_keys[ins_sort]
            if ins_col == "severity":      # High > Medium > Low, not alphabetical
                ins_key = lambda s: s.map({"Low": 0, "Medium": 1, "High": 2})
            elif ins_col == "change_pct":  # biggest movement first, whatever the direction
                ins_key = lambda s: pd.to_numeric(s, errors="coerce").abs()
            else:
                ins_key = None
            ui.insight_table(shown.sort_values(ins_col, ascending=not ins_desc, key=ins_key,
                                               kind="stable", na_position="last"))
            d1, d2, _ = st.columns([1, 1, 2])
            with d1:
                download_button(shown, "Insights CSV", "insights.csv", "dl_ins")
            with d2:
                st.download_button("Insights JSON", shown.to_json(orient="records", indent=2),
                                   file_name="insights.json", mime="application/json", icon=DL_ICON)

# ==========================================================================
# Tab 2 - Trends (Part B + per-district line chart)
# ==========================================================================
with tab_trend:
    with st.container(key="card_line"):
        line_ind = st.selectbox("Indicator for line chart", indicators, format_func=an.pretty_name)
        fig = px.line(df.sort_values("month"), x="month", y=line_ind, color="district",
                      markers=True, labels={"month": "Month", line_ind: an.pretty_name(line_ind),
                                            "district": "District"})
        fig.update_traces(line=dict(width=3), marker=dict(size=9, line=dict(width=2, color=C["card"])),
                          hovertemplate="<b>%{fullData.name}</b><br>%{x}: %{y}<extra></extra>")
        fig.update_xaxes(type="category")
        fig.update_layout(hovermode="closest")
        ui.show_chart(ui.style_fig(fig, f"{an.pretty_name(line_ind)} by district",
                                   "Month-over-month values for every selected district", 380))

    trends = results["trends"]
    if trends.empty:
        st.info("Trend detection needs at least 2 months per district. Select more months.",
                icon=":material/info:")
    else:
        with st.container(key="card_trend_table"):
            ui.section_title("Detected changes",
                             f"{int(trends['is_significant'].sum())} of {len(trends)} month-over-month "
                             f"changes are significant (|change| ≥ {trend_threshold:g}%)")
            t1, t2, t3 = st.columns([2, 2, 1.3], vertical_alignment="bottom")
            only_sig = t1.toggle("Show only significant trends", value=True)
            # Sorting (the HTML table has no clickable headers, so sort here)
            sort_keys = {"Severity": "severity", "Change %": "pct_change", "District": "district",
                         "Indicator": "indicator", "Value": "value", "Month": "month"}
            sort_by = t2.selectbox("Sort by", list(sort_keys), key="trend_sort")
            descending = t3.toggle("Descending", value=sort_by in ("Severity", "Change %"),
                                   key=f"trend_desc_{sort_by}")
            view = trends[trends["is_significant"]] if only_sig else trends
            col = sort_keys[sort_by]
            if col == "severity":      # High > Medium > Low, not alphabetical
                key = lambda s: s.map({"Low": 0, "Medium": 1, "High": 2})
            elif col == "pct_change":  # biggest movement first, whatever the direction
                key = lambda s: s.abs()
            else:
                key = None
            view = view.sort_values(col, ascending=not descending, key=key, kind="stable")
            cols = ["district", "indicator", "prev_month", "month", "prev_value", "value",
                    "pct_change", "is_significant", "is_deterioration", "severity"]
            ui.trend_table(view[cols])
            download_button(view[cols], "Trends CSV", "trends.csv", "dl_trend")

# ==========================================================================
# Tab 3 - Outliers (Part C)
# ==========================================================================
with tab_out:
    outliers = results["outliers"]
    rule = (f"value < Q1 − {iqr_k:g}·IQR or value > Q3 + {iqr_k:g}·IQR" if outlier_method == "IQR"
            else f"|z| ≥ {z_threshold:g}")

    # Box plot of every indicator, with the outliers marked as coral X's
    long = an.to_long(df, indicators)
    long["indicator"] = long["indicator"].map(an.pretty_name)
    with st.container(key="card_box"):
        fig = px.box(long, x="indicator", y="value", color="indicator", points="all",
                     hover_data=["district", "month"], labels={"indicator": "", "value": "Value"})
        fig.update_traces(marker=dict(size=6, opacity=0.55), line=dict(width=2), showlegend=False)
        if not outliers.empty:
            fig.add_scatter(x=outliers["indicator"].map(an.pretty_name), y=outliers["value"],
                            mode="markers", name="Outlier",
                            marker=dict(color=ui.SEVERITY_COLORS["High"], size=15, symbol="x-thin",
                                        line=dict(width=3, color=ui.SEVERITY_COLORS["High"])),
                            text=outliers["district"] + " · " + outliers["month"],
                            hovertemplate="<b>Outlier</b><br>%{text}<br>%{x}: %{y}<extra></extra>")
        fig.update_layout(legend=dict(orientation="h", y=1.12, x=1, xanchor="right"))
        ui.show_chart(ui.style_fig(fig, "Distribution per indicator",
                                   f"Method: {outlier_method} ({rule}) · {len(outliers)} outlier(s) marked ✕",
                                   400))

    if outliers.empty:
        st.info("No outliers with the current settings.", icon=":material/info:")
    else:
        with st.container(key="card_out_table"):
            ui.section_title("Flagged outliers", "District, indicator, month and value of every outlier")
            cols = ["district", "indicator", "month", "value", "mean", "z_score",
                    "lower_bound", "upper_bound", "deviation_pct", "severity"]
            st.dataframe(ui.style_table(outliers[cols]), width="stretch", hide_index=True)
            download_button(outliers[cols], "Outliers CSV", "outliers.csv", "dl_out")
    if outlier_method == "Z-score" and len(df) < 20:
        st.caption(f"Note: with only {len(df)} rows a |z| of 3 is almost impossible to reach, "
                   f"so IQR or a lower z threshold is more useful on small samples.")

# ==========================================================================
# Tab 4 - Correlations (Part D + heatmap)
# ==========================================================================
with tab_corr:
    corr, pairs = results["corr"], results["corr_pairs"]
    st.warning(f"**Limitation:** this matrix is based on only {len(df)} rows "
               f"({df['district'].nunique()} districts × {df['month'].nunique()} months). "
               f"Pearson r is fragile on samples this small — a single extreme value "
               f"(one district) can create or hide a 'strong' correlation. Treat flagged "
               f"pairs as leads to investigate, not as proof.", icon=":material/warning:")
    if corr.empty:
        st.info("Select at least 2 indicators to compute correlations.", icon=":material/info:")
    else:
        with st.container(key="card_heat"):
            labels = [an.pretty_name(c) for c in corr.columns]   # display names only
            fig = px.imshow(corr.values, x=labels, y=labels, text_auto=".2f", zmin=-1, zmax=1,
                            aspect="auto",
                            color_continuous_scale=ui.heat_scale())
            fig.update_traces(xgap=4, ygap=4, textfont=dict(size=14),
                              hovertemplate="%{y} × %{x}<br>r = %{z:.2f}<extra></extra>")
            fig.update_layout(coloraxis_colorbar=dict(title="r", thickness=12, len=0.8))
            fig.update_xaxes(showgrid=False, side="bottom")
            fig.update_yaxes(showgrid=False)
            ui.show_chart(ui.style_fig(fig, "Pearson correlation matrix",
                                       "Blue = move together · coral = move in opposite directions", 440))
        with st.container(key="card_pairs"):
            ui.section_title("Flagged pairs", f"Pairs with |r| ≥ {corr_threshold:.2f}: {len(pairs)}")
            st.dataframe(ui.style_table(pairs), width="stretch", hide_index=True)
            st.download_button("Correlation matrix CSV", corr.to_csv().encode("utf-8"),
                               file_name="correlation_matrix.csv", mime="text/csv", icon=DL_ICON)
            download_button(pairs, "Flagged pairs CSV", "correlation_pairs.csv", "dl_pairs")

# ==========================================================================
# Tab 5 - Data loading & validation (Part A)
# ==========================================================================
with tab_data:
    report = an.validate_data(raw_df)
    for w in report["warnings"]:
        st.warning(w, icon=":material/warning:")
    if not report["warnings"]:
        st.success("All validation checks passed.", icon=":material/check_circle:")
    st.info(f"Loaded {report['rows']} rows · {report['districts']} districts · {report['months']} months · "
            f"{len(report['indicators'])} indicators · {report['duplicates']} duplicate rows.",
            icon=":material/info:")

    c1, c2 = st.columns([5, 2])
    with c1.container(key="card_head"):
        ui.section_title("df.head()", "First five rows of the loaded CSV")
        st.dataframe(raw_df.head(), width="stretch", hide_index=True)
    with c2.container(key="card_missing"):
        ui.section_title("Missing values", "Count of empty / non-numeric cells per column")
        st.dataframe(report["missing"], width="stretch")

    c1, c2 = st.columns(2)
    with c1.container(key="card_info"):
        ui.section_title("df.info()", "Column types and non-null counts")
        st.code(an.get_info_text(raw_df), language=None)
    with c2.container(key="card_describe"):
        ui.section_title("Summary statistics", "Filtered data")
        st.dataframe(df[indicators].describe().round(2), width="stretch")

    with st.container(key="card_filtered"):
        ui.section_title("Filtered data", f"{len(df)} rows after sidebar filters")
        st.dataframe(df, width="stretch", hide_index=True)
        download_button(df, "Filtered data CSV", "filtered_data.csv", "dl_data")
