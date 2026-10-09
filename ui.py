"""
ui.py - Shared look-and-feel for the dashboard (presentation only, no analytics).

Contains:
  * two colour palettes (LIGHT / DARK) and theme_toggle() to switch between them
  * global CSS driven by CSS variables (cards, tabs, sidebar, alerts, widgets)
  * HTML helpers: hero(), kpi_cards(), sidebar_heading(), section_title(), insight_cards()
  * style_fig() / show_chart() so every Plotly chart follows the active theme
  * style_table() to colour severity / type cells in tables

The active theme lives in st.session_state["dark_mode"] (per user session) and
is mirrored to the URL (?theme=dark) so it survives a page refresh.
"""

import base64
import html as html_lib
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# --------------------------------------------------------------------------
# Palettes
# --------------------------------------------------------------------------
LIGHT = dict(
    bg="#F4F7FC", card="#FFFFFF", sidebar="#FFFFFF", input="#EEF2FA", code="#F8FAFC",
    text="#172554", text2="#334155", muted="#64748B", border="#E2E8F0", grid="#EEF2F7",
    blue="#4361EE", teal="#0D9488", violet="#7C3AED", coral="#F05D5E", amber="#F59E0B",
    soft="#EEF2FF", soft_border="#DCE3FB", hover="#F1F5FF",
    hero="linear-gradient(120deg, #172554 0%, #1E3A8A 45%, #4361EE 80%, #7C3AED 100%)",
    shadow="0 1px 2px rgba(16,24,40,.04), 0 4px 14px rgba(16,24,40,.05)",
    chart=["#4361EE", "#0D9488", "#7C3AED", "#F05D5E", "#F59E0B", "#0EA5E9", "#EC4899",
           "#84CC16", "#6366F1", "#14B8A6"],
    heat_mid="#FFFFFF",
)
DARK = dict(
    bg="#0B1120", card="#151F32", sidebar="#101827", input="#1B2840", code="#0F172A",
    text="#F1F5F9", text2="#CBD5E1", muted="#94A3B8", border="#293548", grid="#22304A",
    blue="#60A5FA", teal="#2DD4BF", violet="#A78BFA", coral="#F87171", amber="#FBBF24",
    soft="rgba(96,165,250,.14)", soft_border="rgba(96,165,250,.32)", hover="rgba(96,165,250,.10)",
    hero="linear-gradient(120deg, #0F1A33 0%, #1E3A8A 50%, #3B4FD8 82%, #6D4BD8 100%)",
    shadow="0 1px 2px rgba(0,0,0,.35), 0 6px 18px rgba(0,0,0,.25)",
    chart=["#60A5FA", "#2DD4BF", "#A78BFA", "#F87171", "#FBBF24", "#38BDF8", "#F472B6",
           "#A3E635", "#818CF8", "#5EEAD4"],
    heat_mid="#151F32",
)

# Severity colours are identical in both themes (consistent meaning)
SEVERITY_COLORS = {"High": "#F05D5E", "Medium": "#F59E0B", "Low": "#10B981"}
# Badge colours: (background, text) per theme
BADGES = {
    False: {"High": ("#FDE8E8", "#C53030"), "Medium": ("#FEF3C7", "#B45309"), "Low": ("#D1FAE5", "#047857"),
            "trend": ("#E8EDFD", "#4361EE"), "outlier": ("#F1EAFE", "#7C3AED"),
            "correlation": ("#DDF4F1", "#0D9488"), "threshold_breach": ("#FFE9E3", "#C2410C")},
    True: {"High": ("rgba(240,93,94,.18)", "#FCA5A5"), "Medium": ("rgba(245,158,11,.18)", "#FCD34D"),
           "Low": ("rgba(16,185,129,.18)", "#6EE7B7"),
           "trend": ("rgba(96,165,250,.16)", "#93C5FD"), "outlier": ("rgba(167,139,250,.16)", "#C4B5FD"),
           "correlation": ("rgba(45,212,191,.16)", "#5EEAD4"), "threshold_breach": ("rgba(251,146,60,.16)", "#FDBA74")},
}
FONT = "Inter, 'Segoe UI', sans-serif"
LOGO_PATH = Path(__file__).parent / "assets" / "logo.png"

# Light colorway is the Plotly default; dark charts get their colours remapped in style_fig()
pio.templates["health"] = go.layout.Template(layout=dict(colorway=LIGHT["chart"], font=dict(family=FONT)))
pio.templates.default = "plotly_white+health"
# Severity colours are never remapped, so they stay identical in both themes
_TO_DARK = {lt: dk for lt, dk in zip(LIGHT["chart"], DARK["chart"])
            if lt not in SEVERITY_COLORS.values()}


# --------------------------------------------------------------------------
# Theme state
# --------------------------------------------------------------------------
def theme_toggle():
    """Sidebar switch. Initial value comes from the URL so a refresh keeps the theme."""
    if "dark_mode" not in st.session_state:
        st.session_state.dark_mode = st.query_params.get("theme") == "dark"
    st.sidebar.toggle(":material/dark_mode: Dark mode", key="dark_mode")
    st.query_params["theme"] = "dark" if st.session_state.dark_mode else "light"


def is_dark():
    return bool(st.session_state.get("dark_mode", False))


def P():
    """Palette for the current session's theme."""
    return DARK if is_dark() else LIGHT


# --------------------------------------------------------------------------
# Plotly helpers
# --------------------------------------------------------------------------
def style_fig(fig, title, subtitle=None, height=340):
    """Apply the active theme + a consistent title, size and margins to any figure."""
    p = P()
    axis = dict(gridcolor=p["grid"], linecolor=p["border"], zerolinecolor=p["border"],
                tickfont=dict(color=p["muted"], size=12), title_font=dict(color=p["muted"], size=12))
    fig.update_layout(
        title=dict(text=f"<b>{title}</b>", x=0, xanchor="left", font=dict(size=15, color=p["text"]),
                   subtitle=dict(text=subtitle or "", font=dict(size=12, color=p["muted"]))),
        height=height, margin=dict(l=10, r=10, t=70 if subtitle else 50, b=10),
        paper_bgcolor=p["card"], plot_bgcolor=p["card"],   # explicit: Streamlit overrides template bg
        font=dict(family=FONT, color=p["text"], size=13),
        legend=dict(font=dict(color=p["muted"], size=12), bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor=p["card"], bordercolor=p["border"], font=dict(family=FONT, color=p["text"])),
        modebar=dict(bgcolor="rgba(0,0,0,0)", color=p["muted"], activecolor=p["blue"]),
        coloraxis_colorbar=dict(tickfont=dict(color=p["muted"]), title_font=dict(color=p["muted"])),
    )
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    if is_dark():                                   # swap light chart colours for dark ones
        for trace in fig.data:
            for part in ("marker", "line"):
                obj = getattr(trace, part, None)
                if obj is not None and isinstance(obj.color, str) and obj.color in _TO_DARK:
                    obj.color = _TO_DARK[obj.color]
    return fig


def heat_scale():
    """Diverging scale: coral (-1) -> card colour (0) -> blue (+1)."""
    p = P()
    high = "#2563EB" if is_dark() else p["blue"]   # deeper blue keeps light cell text readable
    return [[0, SEVERITY_COLORS["High"]], [0.5, p["heat_mid"]], [1, high]]


def show_chart(fig):
    """Render a chart with OUR theme (theme=None stops Streamlit overriding it)."""
    st.plotly_chart(fig, width="stretch", theme=None,
                    config={"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]})


# --------------------------------------------------------------------------
# Global CSS (all colours come from CSS variables set per theme)
# --------------------------------------------------------------------------
BASE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, .stApp, button, input, textarea, [data-testid="stMarkdownContainer"] { font-family: __FONT__; }
.stApp { background: var(--bg); color: var(--text); }
[data-testid="stHeader"] { background: transparent; }
.block-container, [data-testid="stMainBlockContainer"] { padding-top: 2.2rem; padding-bottom: 2rem; max-width: 1500px; }
h1, h2, h3, h4 { color: var(--text); letter-spacing: -0.01em; }

/* ---------- Sidebar ---------- */
[data-testid="stSidebar"] { background: var(--sidebar); border-right: 1px solid var(--border); }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0.75rem; }
[data-testid="stSidebar"] label p { font-weight: 600; color: var(--text); font-size: 0.86rem; }
.side-brand { display:flex; align-items:center; gap:10px; padding: 4px 0 8px; }
.side-brand .logo { width:34px; height:34px; border-radius:10px; display:flex; align-items:center; justify-content:center;
    background: linear-gradient(135deg, var(--blue), var(--violet)); color:#fff; font-weight:800; font-size:15px; }
/* Logo tiles: white tile = same contrast in both themes. The PNG has transparent padding,
   so the image is drawn slightly taller than the tile and centred (only empty space is hidden). */
.logo-tile { flex: none; display:flex; align-items:center; justify-content:center; overflow:hidden; background:#FFFFFF; }
.logo-tile img { width:auto; max-width:none; }
.side-brand .logo-tile { width:38px; height:38px; border-radius:10px; border:1px solid var(--border); }
.side-brand .logo-tile img { height:46px; }
.side-brand b { color:var(--text); font-size: 0.98rem; display:block; line-height:1.1; }
.side-brand span { color:var(--muted); font-size: 0.75rem; }
.side-heading { display:flex; align-items:center; gap:8px; margin: 14px 0 2px; padding-top: 12px;
    border-top: 1px solid var(--border); font-size: 0.72rem; font-weight: 700; letter-spacing: .12em; color: var(--muted); }
.side-heading i { width:8px; height:8px; border-radius:50%; display:inline-block; }
[data-testid="stMultiSelectTagsContainer"] > span > span { background: var(--soft) !important; color: var(--blue) !important;
    border: 1px solid var(--soft-border); border-radius: 6px !important; }
[data-testid="stMultiSelectTagsContainer"] > span > span * { color: var(--blue) !important; fill: var(--blue); }

/* ---------- Hero ---------- */
.hero { position:relative; overflow:hidden; border-radius:18px; padding: 24px 30px; margin-bottom: 18px; color:#fff;
    background: var(--hero); border: 1px solid rgba(255,255,255,.06); box-shadow: 0 10px 30px rgba(23,37,84,.18); }
.hero-row { display:flex; align-items:center; gap:20px; position:relative; z-index:1; }
.hero .logo-tile { width:76px; height:76px; border-radius:18px; box-shadow: 0 6px 18px rgba(0,0,0,.18); }
.hero .logo-tile img { height:92px; }
.hero-row > div { min-width: 0; }   /* let the text column shrink and wrap instead of overflowing */
@media (max-width: 640px) {
    .hero { padding: 20px; }
    .hero-row { flex-direction: column; align-items: flex-start; gap: 12px; }
    .hero .logo-tile { width:56px; height:56px; border-radius:14px; } .hero .logo-tile img { height:68px; }
    .hero .hero-row h1 { font-size:1.6rem; } }
.hero .eyebrow { font-size: .72rem; font-weight: 700; letter-spacing: .18em; color: #A5B4FC; }
.hero h1 { color:#fff; font-size: 2rem; font-weight: 800; margin: 4px 0 6px; padding:0; }
.hero p { color: #DBEAFE; margin:0; max-width: 680px; font-size: .95rem; }
.hero .badges { margin-top: 14px; display:flex; gap:8px; flex-wrap:wrap; }
.hero .badge { background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.25); border-radius: 999px;
    padding: 4px 12px; font-size: .78rem; color:#fff; }
.hero .badge .dot { display:inline-block; width:7px; height:7px; border-radius:50%; background:#34D399; margin-right:6px;
    box-shadow: 0 0 0 3px rgba(52,211,153,.25); }
.hero svg { position:absolute; right: 24px; top: 50%; transform: translateY(-50%); opacity: .9; }
@media (max-width: 900px) { .hero svg { display:none; } }

/* ---------- KPI cards ---------- */
.kpi-grid { display:grid; grid-template-columns: repeat(5, minmax(0,1fr)); gap: 14px; margin-bottom: 18px; }
@media (max-width: 1000px) { .kpi-grid { grid-template-columns: repeat(2, minmax(0,1fr)); } }
.kpi { background:var(--card); border:1px solid var(--border); border-radius:14px; padding: 14px 16px; position:relative;
    overflow:hidden; box-shadow: var(--shadow); }
.kpi::before { content:""; position:absolute; left:0; top:0; right:0; height:4px; background: var(--accent); }
.kpi .top { display:flex; justify-content:space-between; align-items:center; }
.kpi .label { color:var(--muted); font-size:.8rem; font-weight:600; }
.kpi .icon { width:32px; height:32px; border-radius:9px; display:flex; align-items:center; justify-content:center;
    background: var(--tint); color: var(--accent); }
.kpi .value { font-size: 1.85rem; font-weight: 800; color:var(--text); line-height:1.1; margin-top: 6px; }
.kpi .sub { color:var(--muted); font-size:.75rem; margin-top: 2px; }

/* ---------- Tabs ---------- */
.stTabs [data-baseweb="tab-list"] { gap: 4px; background:var(--card); padding: 5px; border-radius: 12px;
    border:1px solid var(--border); box-shadow: var(--shadow); }
.stTabs [data-baseweb="tab"] { height: 40px; padding: 0 18px; border-radius: 9px; color:var(--muted); font-weight:600;
    background: transparent; }
.stTabs [data-baseweb="tab"] p { font-weight:600; font-size: .9rem; color: var(--muted); }
.stTabs [data-baseweb="tab"]:hover { background:var(--hover); }
.stTabs [aria-selected="true"] { background: var(--soft); }
.stTabs [aria-selected="true"] p, .stTabs [aria-selected="true"] span { color:var(--blue) !important; }
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] { display:none; }
.stTabs [data-baseweb="tab-panel"] { padding-top: 16px; }

/* ---------- White/dark cards (st.container(key="card_...")) ---------- */
[class*="st-key-card"] { background:var(--card); border:1px solid var(--border); border-radius:14px; padding: 16px 18px;
    box-shadow: var(--shadow); }
.section-title { margin: 2px 0 8px; }
.section-title b { color:var(--text); font-size: 1.02rem; }
.section-title span { color:var(--muted); font-size: .82rem; display:block; }

/* ---------- Insight cards ---------- */
.ins-grid { display:grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 12px; }
@media (max-width: 1000px) { .ins-grid { grid-template-columns: 1fr; } }
.ins { background:var(--card); border:1px solid var(--border); border-left: 5px solid var(--sev); border-radius: 12px;
    padding: 12px 16px; box-shadow: var(--shadow); }
.ins .head { display:flex; gap:6px; align-items:center; flex-wrap:wrap; margin-bottom: 6px; }
.ins .id { color:var(--muted); font-size:.75rem; margin-left:auto; }
.pill { display:inline-block; border-radius:999px; padding: 2px 10px; font-size:.72rem; font-weight:700; letter-spacing:.02em; }
.ins .title { color:var(--text); font-weight:700; font-size:.95rem; }
.ins .nums { color:var(--muted); font-size:.82rem; margin: 2px 0 6px; }
.ins .nums b { color:var(--text); font-size: 1.05rem; }
.ins .text { color:var(--text2); font-size:.86rem; line-height:1.45; }

/* ---------- Trends table (themed HTML table, scoped to .data-table only) ---------- */
.data-table-wrap { max-height: 440px; overflow: auto; border:1px solid var(--border); border-radius: 10px; margin: 6px 0 12px; }
.data-table { width:100%; border-collapse: separate; border-spacing:0; font-size:.85rem; color: var(--text); }
.data-table th { position: sticky; top: 0; z-index: 1; background: var(--input); color: var(--muted); font-weight: 700;
    font-size: .7rem; text-transform: uppercase; letter-spacing: .05em; text-align: left; padding: 9px 10px;
    line-height: 1.25; vertical-align: bottom; }
.data-table td { padding: 8px 10px; vertical-align: middle; white-space: nowrap; background: var(--card); }
/* reset Streamlit's default markdown-table borders, keep only row separators */
.data-table th, .data-table td { border: none; border-bottom: 1px solid var(--border); }
.data-table tbody:last-child tr:last-child td { border-bottom: none; }
.data-table tbody tr:hover td { background: var(--hover); }
.data-table .num { text-align: right; font-variant-numeric: tabular-nums; }
.data-table .center { text-align: center; }
.data-table .strong { font-weight: 700; }
.data-table .dim { color: var(--muted); }
/* All-insights table: one <tbody class="grp"> per insight = data row + full-width explanation row */
.data-table tbody.grp tr.main td { border-bottom: none; padding-bottom: 3px; }
.data-table tbody.grp tr.sub td { white-space: normal; padding-top: 0; padding-bottom: 10px; line-height: 1.45;
    font-size: .82rem; color: var(--text2); }
.data-table tbody.grp:hover td { background: var(--hover); }
.data-table .flag { display:inline-flex; align-items:center; justify-content:center; width:22px; height:22px; border-radius:6px;
    font-size:.8rem; font-weight:800; }

/* ---------- Alerts, buttons, code, tables ---------- */
[data-testid="stAlertContainer"] { border-radius: 12px; }
[data-testid="stDownloadButton"] button { border-radius: 10px; border:1px solid var(--border); background:var(--card);
    color:var(--text); font-weight:600; }
[data-testid="stDownloadButton"] button:hover { border-color:var(--blue); color:var(--blue); background:var(--hover); }
[data-testid="stDataFrame"] { border-radius: 10px; overflow:hidden; }
[data-testid="stCode"] pre { background:var(--code) !important; border:1px solid var(--border); border-radius:10px; font-size:.78rem; }
[data-testid="stCode"] code { color: var(--text2) !important; }
"""

# Extra rules only for dark mode: the native widgets are drawn with the light
# config theme (.streamlit/config.toml), so their surfaces are recoloured here.
DARK_CSS = """
.stApp p, .stApp li, [data-testid="stWidgetLabel"] p, [data-testid="stCaptionContainer"],
[data-testid="stMarkdownContainer"] { color: var(--text); }
[data-testid="stCaptionContainer"] p { color: var(--muted); }
[data-baseweb="select"] > div, [data-baseweb="input"] > div,
[data-testid="stSelectbox"] div:has(> input[role="combobox"]),
[data-testid="stMultiSelect"] div:has(> [data-testid="stMultiSelectTagsContainer"]) {
    background: var(--input) !important; border-color: var(--border) !important; color: var(--text) !important; }
[data-testid="stSelectbox"] input, [data-testid="stMultiSelect"] input {
    background: transparent !important; color: var(--text) !important; }
[data-baseweb="select"] svg { color: var(--muted); fill: var(--muted); }
/* Sidebar collapse / expand buttons: native transparent icon buttons; only the icon colour and
   hover tint need the dark palette (Streamlit colours them from the global light theme). */
[data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"],
[data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"] { color: var(--muted); }
[data-testid="stSidebarCollapseButton"] button:hover, [data-testid="stExpandSidebarButton"]:hover { background: var(--hover); }
[data-testid="stSidebarCollapseButton"] button:hover [data-testid="stIconMaterial"],
[data-testid="stExpandSidebarButton"]:hover [data-testid="stIconMaterial"] { color: var(--text); }
[data-baseweb="select"] [class*="singleValue"], [data-baseweb="select"] div { color: var(--text); }
[data-baseweb="popover"] ul, [data-baseweb="popover"] [role="listbox"], [data-baseweb="menu"],
[data-testid$="VirtualDropdown"] { background: var(--card) !important; color: var(--text); border-color: var(--border); }
[data-testid="stSelectbox"] button svg, [data-testid="stMultiSelect"] button svg { color: var(--muted); fill: var(--muted); }
[data-baseweb="popover"] li, [role="option"] { color: var(--text) !important; }
[role="option"]:hover, [role="option"][aria-selected="true"] { background: var(--hover) !important; }
[data-testid="stFileUploaderDropzone"] { background: var(--input); border: 1px dashed var(--border); }
[data-testid="stFileUploaderDropzoneInstructions"] span, [data-testid="stFileUploaderDropzoneInstructions"] small { color: var(--muted); }
[data-testid="stFileUploaderDropzone"] button { background: var(--card); color: var(--text); border-color: var(--border); }
[data-testid="stSliderThumbValue"], [data-testid="stSliderTickBar"] div { color: var(--text2) !important; }
[data-testid="stAlertContainer"] { background: rgba(96,165,250,.12); color: #BFDBFE; }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) { background: rgba(251,191,36,.12); color: #FDE68A; }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) { background: rgba(248,113,113,.14); color: #FECACA; }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) { background: rgba(52,211,153,.12); color: #A7F3D0; }
[data-testid="stAlertContainer"] p, [data-testid="stAlertContainer"] span { color: inherit !important; }
[data-testid="stToolbar"] button, [data-testid="stMainMenu"] button { color: var(--muted); }
/* st.dataframe is drawn on a canvas with the light theme; invert it into a dark table
   (hue-rotate keeps the severity/type colours recognisable). */
[data-testid="stDataFrame"] { filter: invert(0.9) hue-rotate(180deg); }
"""


def inject_css():
    """Write CSS variables for the active palette + the shared rules."""
    p = P()
    variables = ";".join([f"--{k.replace('_', '-')}:{v}" for k, v in p.items() if isinstance(v, str)])
    css = BASE_CSS.replace("__FONT__", FONT) + (DARK_CSS if is_dark() else "")
    st.markdown(f"<style>:root{{{variables}}}{css}</style>", unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Simple inline SVG icons (Feather-style line icons)
# --------------------------------------------------------------------------
_ICONS = {
    "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>'
                '<path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>',
    "pin": '<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>',
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/>'
                '<line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
    "zap": '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
    "alert": '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>'
             '<line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
}


def icon(name, size=17):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{_ICONS[name]}</svg>')


# --------------------------------------------------------------------------
# HTML building blocks (single-line HTML so Markdown never mistakes it for code)
# --------------------------------------------------------------------------
def hero(dataset_name):
    """Compact gradient header with a decorative chart motif."""
    motif = ('<svg width="220" height="90" viewBox="0 0 220 90" fill="none">'
             '<rect x="10" y="50" width="14" height="30" rx="4" fill="rgba(255,255,255,.18)"/>'
             '<rect x="34" y="36" width="14" height="44" rx="4" fill="rgba(255,255,255,.22)"/>'
             '<rect x="58" y="44" width="14" height="36" rx="4" fill="rgba(255,255,255,.18)"/>'
             '<rect x="82" y="22" width="14" height="58" rx="4" fill="rgba(255,255,255,.28)"/>'
             '<polyline points="110,62 135,48 158,56 182,24 210,34" stroke="#5EEAD4" stroke-width="3" '
             'fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
             '<circle cx="182" cy="24" r="6" fill="#F05D5E" stroke="#fff" stroke-width="2"/></svg>')
    html = ('<div class="hero"><div class="hero-row">'
            f'{logo_tile("Auto-Analytics Engine logo")}<div>'
            '<div class="eyebrow">HEALTHCARE INTELLIGENCE</div>'
            '<h1>Auto-Analytics Engine</h1>'
            '<p>Automated detection of trends, outliers, correlations and threshold breaches across '
            'district healthcare indicators, turned into plain-language insights.</p>'
            '<div class="badges"><span class="badge"><span class="dot"></span>Insights generated '
            f'dynamically from the data</span><span class="badge">Dataset: {dataset_name}</span></div>'
            f'</div></div>{motif}</div>')
    st.markdown(html, unsafe_allow_html=True)


@st.cache_data
def _logo_data_uri():
    """Embed assets/logo.png as a data URI (project-relative path, works on Streamlit Cloud)."""
    if not LOGO_PATH.exists():
        return None
    return "data:image/png;base64," + base64.b64encode(LOGO_PATH.read_bytes()).decode()


def logo_tile(alt):
    """White tile holding the logo; falls back to an 'A' badge if the file is missing."""
    uri = _logo_data_uri()
    if uri is None:
        return '<div class="logo">A</div>'
    return f'<div class="logo-tile"><img src="{uri}" alt="{alt}"></div>'


def kpi_cards(cards):
    """cards = list of (label, value, sub_text, icon_name, accent_colour)."""
    items = []
    for label, value, sub, icon_name, accent in cards:
        items.append(f'<div class="kpi" style="--accent:{accent};--tint:{accent}22">'
                     f'<div class="top"><span class="label">{label}</span>'
                     f'<span class="icon">{icon(icon_name)}</span></div>'
                     f'<div class="value">{value}</div><div class="sub">{sub}</div></div>')
    st.markdown(f'<div class="kpi-grid">{"".join(items)}</div>', unsafe_allow_html=True)


def sidebar_brand():
    st.sidebar.markdown(f'<div class="side-brand">{logo_tile("logo")}<div><b>Control Panel</b>'
                        '<span>Data, filters &amp; detection</span></div></div>', unsafe_allow_html=True)


def sidebar_heading(text, color):
    st.sidebar.markdown(f'<div class="side-heading"><i style="background:{color}"></i>{text}</div>',
                        unsafe_allow_html=True)


def section_title(title, subtitle=""):
    st.markdown(f'<div class="section-title"><b>{title}</b><span>{subtitle}</span></div>',
                unsafe_allow_html=True)


def pill(text, kind="severity"):
    bg, fg = BADGES[is_dark()].get(text, ("rgba(148,163,184,.15)", P()["muted"]))
    label = text.replace("_", " ").upper() if kind == "severity" else text.replace("_", " ").title()
    return f'<span class="pill" style="background:{bg};color:{fg}">{label}</span>'


def _num(v):
    return "—" if pd.isna(v) else f"{v:g}"


def insight_cards(rows):
    """Card grid for the top insights (all values come from the insights DataFrame)."""
    cards = []
    for r in rows.itertuples():
        change = "" if pd.isna(r.change_pct) else f" · change <b>{r.change_pct:+.1f}%</b>"
        ref = "" if pd.isna(r.prev_value) else f" vs <b>{_num(r.prev_value)}</b>"
        cards.append(f'<div class="ins" style="--sev:{SEVERITY_COLORS[r.severity]}">'
                     f'<div class="head">{pill(r.severity)}{pill(r.type, "type")}'
                     f'<span class="id">{r.insight_id} · {r.period}</span></div>'
                     f'<div class="title">{r.entity} — {r.indicator.replace("_", " ")}</div>'
                     f'<div class="nums">value <b>{_num(r.value)}</b>{ref}{change}</div>'
                     f'<div class="text">{r.explanation}</div></div>')
    st.markdown(f'<div class="ins-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Trends table - themed HTML table
# st.dataframe draws on a canvas with the single global (light) Streamlit theme,
# so it cannot follow the per-session dark mode. This table uses the CSS
# variables instead, so header, body, badges and flags match either theme.
# --------------------------------------------------------------------------
def _flag(value, yes_text, no_text, yes_color):
    """Boolean -> small square badge (✓ / –) with a tooltip."""
    if value:
        return (f'<span class="flag" title="{yes_text}" style="background:{yes_color}22;color:{yes_color}">'
                f'<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                f'stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg></span>')
    return f'<span class="flag dim" title="{no_text}">–</span>'


def trend_table(view):
    """Render the trends DataFrame (same rows/columns as the CSV export) as an HTML table."""
    p, esc = P(), html_lib.escape
    head = ("<tr><th>District</th><th>Indicator</th><th>Prev month</th><th>Month</th>"
            "<th class='num'>Prev value</th><th class='num'>Value</th><th class='num'>Change</th>"
            "<th class='center'>Significant</th><th class='center'>Deterioration</th><th>Severity</th></tr>")
    rows = []
    for r in view.itertuples():
        change_color = p["coral"] if r.is_deterioration else p["teal"]   # worse = coral, better = teal
        rows.append(
            f"<tr><td class='strong'>{esc(str(r.district))}</td><td>{esc(str(r.indicator))}</td>"
            f"<td class='dim'>{r.prev_month}</td><td>{r.month}</td>"
            f"<td class='num dim'>{_num(r.prev_value)}</td><td class='num strong'>{_num(r.value)}</td>"
            f"<td class='num strong' style='color:{change_color}'>{r.pct_change:+.1f}%</td>"
            f"<td class='center'>{_flag(r.is_significant, 'Significant', 'Below threshold', p['blue'])}</td>"
            f"<td class='center'>{_flag(r.is_deterioration, 'Deterioration', 'Improvement', p['coral'])}</td>"
            f"<td>{pill(r.severity)}</td></tr>")
    st.markdown(f'<div class="data-table-wrap"><table class="data-table"><thead>{head}</thead>'
                f'<tbody>{"".join(rows)}</tbody></table></div>', unsafe_allow_html=True)


def insight_table(df):
    """Render the insights DataFrame with the same themed .data-table style as the Trends table."""
    esc = html_lib.escape
    head = ("<tr><th>ID</th><th>Type</th><th>Indicator</th><th>Entity</th><th>Period</th>"
            "<th class='num'>Value</th><th class='num'>Reference</th><th class='num'>Change</th>"
            "<th>Severity</th></tr>")
    rows = []
    for r in df.itertuples():
        change = "—" if pd.isna(r.change_pct) else f"{r.change_pct:+.1f}%"
        rows.append(
            f"<tbody class='grp'><tr class='main'><td class='dim'>{r.insight_id}</td><td>{pill(r.type, 'type')}</td>"
            f"<td>{esc(str(r.indicator)).replace(':', ':<wbr>')}</td><td class='strong'>{esc(str(r.entity))}</td>"
            f"<td class='dim'>{str(r.period).replace('..', '..<wbr>')}</td>"
            f"<td class='num strong'>{_num(r.value)}</td>"
            f"<td class='num dim'>{_num(r.prev_value)}</td><td class='num strong'>{change}</td>"
            f"<td>{pill(r.severity)}</td></tr>"
            f"<tr class='sub'><td colspan='9'>{esc(str(r.explanation))}</td></tr></tbody>")
    st.markdown(f'<div class="data-table-wrap"><table class="data-table"><thead>{head}</thead>'
                f'{"".join(rows)}</table></div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Table styling (keeps st.dataframe sorting / searching)
# --------------------------------------------------------------------------
def _badge_css(value):
    # Always the LIGHT colours: in dark mode the CSS filter inverts the whole table
    bg, fg = BADGES[False].get(value, (None, None))
    return f"background-color:{bg};color:{fg};font-weight:700" if bg else ""


def style_table(df):
    """Colour 'severity' and 'type' cells and tidy number formatting."""
    styler = df.style
    for col in ("severity", "type"):
        if col in df.columns:
            styler = styler.map(_badge_css, subset=[col])
    if "value" in df.columns:
        styler = styler.map(lambda v: f"font-weight:700;color:{LIGHT['text']}", subset=["value"])
    for col in ("change_pct", "pct_change", "deviation_pct"):
        if col in df.columns:
            styler = styler.map(lambda v: f"color:{LIGHT['blue']};font-weight:600", subset=[col])
            styler = styler.format(lambda v: "—" if pd.isna(v) else f"{v:+.1f}%", subset=[col])
    # Other decimals: up to 2 places, no trailing zeros (28.00 -> 28, 78.33 stays)
    other = df.select_dtypes("number").columns.difference(["change_pct", "pct_change", "deviation_pct"])
    return styler.format(lambda v: "—" if pd.isna(v) else f"{v:.2f}".rstrip("0").rstrip("."),
                         subset=list(other))
