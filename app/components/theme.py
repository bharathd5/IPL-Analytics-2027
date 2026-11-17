"""Design tokens + Plotly template for SUPERR INTELLIGENCE (war-room dark theme)."""
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# ---- core palette (owner spec)
BG = "#0B1220"
BG2 = "#101B2D"
CARD = "#111F32"
PANEL = "#0F1A2B"
ACCENT = "#B8F36B"      # pressure / primary series / selection
ACCENT2 = "#42D8D0"     # normal / baseline series
POS = "#35D6A1"
WARN = "#F5B942"
NEG = "#F16C75"
TEXT = "#F1F5F9"
MUTED = "#94A3B8"
FAINT = "#64748B"
BORDER = "#1F2E44"
BORDER2 = "#2A3C57"
VIOLET = "#A78BFA"
SLATE = "#2F4A63"

SERIES = [ACCENT, ACCENT2, WARN, VIOLET, NEG, "#94A3B8"]
LEVEL_COLORS = {"Low": SLATE, "Moderate": ACCENT2, "High": WARN, "Extreme": NEG}
LEVEL_ORDER = ["Low", "Moderate", "High", "Extreme"]
PN_COLORS = {"Pressure": ACCENT, "Normal": ACCENT2}
REL_COLORS = {"High": POS, "Medium": WARN, "Low": NEG}
SEQ = [[0, "#0F1E33"], [0.45, "#1F5F66"], [1, ACCENT]]
DIVERGING = [[0, "#8C3442"], [0.5, "#1C2A3D"], [1, "#1E8463"]]
DIVERGING_REV = [[0, "#1E8463"], [0.5, "#1C2A3D"], [1, "#8C3442"]]

_AX = dict(gridcolor="rgba(148,163,184,0.08)", zerolinecolor="rgba(148,163,184,0.22)", linecolor=BORDER,
           tickfont=dict(color=MUTED, size=11), title_font=dict(color=MUTED, size=11), automargin=True,
           title_standoff=8)
pio.templates["superr"] = go.layout.Template(data=dict(heatmap=[go.Heatmap(textfont=dict(color=TEXT, size=11), xgap=2, ygap=2)]), layout=dict(
    font=dict(family="Inter, system-ui, sans-serif", color=TEXT, size=12),
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", colorway=SERIES,
    margin=dict(l=8, r=12, t=12, b=8), xaxis=_AX, yaxis=_AX,
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=MUTED, size=11), orientation="h",
                yanchor="bottom", y=1.0, xanchor="left", x=0, title=None),
    hoverlabel=dict(bgcolor="#0E1A2C", bordercolor=BORDER2, font=dict(color=TEXT, family="Inter", size=12)),
    bargap=0.28, bargroupgap=0.08,
    coloraxis=dict(colorbar=dict(thickness=8, outlinewidth=0, tickfont=dict(color=MUTED, size=10),
                                 title=dict(font=dict(color=MUTED, size=10)))),
    polar=dict(bgcolor="rgba(0,0,0,0)", radialaxis=dict(gridcolor=BORDER2, tickfont=dict(color=FAINT, size=9)),
               angularaxis=dict(gridcolor=BORDER2, tickfont=dict(color=MUTED, size=11))),
))
pio.templates.default = "superr"

PLOT_CONFIG = {"displayModeBar": False, "displaylogo": False}


def style(fig, height=340, legend=None, title=None):
    """Uniform chart frame. Titles live in the panel header, never inside the figure."""
    has_legend = legend if legend is not None else any(getattr(t, "showlegend", None) is not False and t.name
                                                         for t in fig.data) and len(fig.data) > 1
    fig.update_layout(template="superr", height=height, title=None, showlegend=bool(has_legend),
                      margin=dict(l=8, r=12, t=34 if has_legend else 10, b=8))
    if any(t.type == "scatterpolar" for t in fig.data):
        fig.update_layout(margin=dict(l=70, r=70, t=50 if has_legend else 30, b=30))
    fig.update_traces(selector=dict(type="bar"), marker_line_width=0)
    cb = dict(thickness=8, len=0.75, outlinewidth=0, tickfont=dict(color=MUTED, size=10))
    for t in fig.data:
        if t.type == "heatmap":
            t.update(colorbar=cb)
        elif t.type == "scatter" and t.marker is not None and t.marker.colorscale is not None:
            t.marker.update(colorbar=cb)
    return fig


def show(fig, height=340, legend=None, key=None):
    st.plotly_chart(style(fig, height, legend), width="stretch", config=PLOT_CONFIG, key=key, theme=None)


def arr(df, decimals=None):
    """Numeric numpy array from a frame with nullable dtypes (pd.NA -> nan)."""
    import numpy as np
    a = df.astype("float64").to_numpy(dtype=float, na_value=np.nan) if hasattr(df, "to_numpy") else np.asarray(df, float)
    return a if decimals is None else np.round(a, decimals)


def txt(df, decimals=0):
    """Cell labels for heatmaps: formatted numbers, blank where missing."""
    import numpy as np
    a = arr(df)
    return np.where(np.isnan(a), "", np.vectorize(lambda v: f"{v:.{decimals}f}")(np.nan_to_num(a)))
