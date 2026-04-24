import os, json, math, datetime
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from PIL import Image

st.set_page_config(
    page_title="NazarGeo · Mission Control",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
OUT_DIR   = os.path.join(BASE_DIR, "out")
MATCH_DIR = os.path.join(OUT_DIR, "match_json")
VIS_DIR   = os.path.join(OUT_DIR, "perceive_vis")
FINAL_DIR = os.path.join(OUT_DIR, "final")
PROJ_DIR  = os.path.join(OUT_DIR, "project_json")

SELECTED_JSON    = os.path.join(OUT_DIR, "selected_buildings.json")
CALIBRATION_JSON = os.path.join(OUT_DIR, "calibration_results.json")

CURATED_FRAMES = {76, 151, 226, 276, 401, 626, 1826, 3351}

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
  font-family: 'DM Sans', sans-serif;
  background: #060a0f;
  color: #bcc8d4;
}
.block-container { padding: 2rem 2.5rem 4rem !important; max-width: 1600px !important; }

.ng-header-wrap {
  display: flex;
  align-items: center;
  gap: 1.4rem;
  padding: 1.2rem 0 1rem;
}

.ng-logo {
  font-size: 3.2rem;
  line-height: 1;
  flex-shrink: 0;
}

.ng-text-block {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.ng-wordmark {
  font-family: 'Space Mono', monospace;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.45em;
  color: #1bffc8;
  text-transform: uppercase;
  display: block;
  opacity: 1 !important;
  visibility: visible !important;
  /* Glow so it punches through dark bg */
  text-shadow: 0 0 12px #1bffc899, 0 0 24px #1bffc840;
}

.ng-title {
  font-family: 'DM Sans', sans-serif;
  font-size: 2.55rem;
  font-weight: 600;
  line-height: 1.08;
  color: #e8f0f8;
  margin: 0;
  letter-spacing: -0.02em;
  display: block;
}

.ng-sub {
  font-family: 'Space Mono', monospace;
  font-size: 0.6rem;
  color: #3a4a5a;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  display: block;
  margin-top: 0.2rem;
}

.cal-banner {
  background: linear-gradient(135deg, #071a12 0%, #060f1a 100%);
  border: 1px solid #0d3d28;
  border-left: 4px solid #1bffc8;
  border-radius: 10px;
  padding: 1.2rem 1.6rem;
  margin: 1.4rem 0;
  position: relative;
  overflow: hidden;
}
.cal-banner::before {
  content: '';
  position: absolute; top: 0; right: 0;
  width: 200px; height: 100%;
  background: radial-gradient(ellipse at right center, #1bffc81a 0%, transparent 70%);
  pointer-events: none;
}
.cal-achieved {
  font-family: 'Space Mono', monospace;
  font-size: 0.6rem; font-weight: 700;
  color: #1bffc8; letter-spacing: 0.25em;
  text-transform: uppercase; margin-bottom: 0.5rem;
}
.cal-metric-row { display: flex; align-items: baseline; gap: 0.5rem; flex-wrap: wrap; }
.cal-big { font-family: 'Space Mono', monospace; font-size: 2.4rem; font-weight: 700; color: #1bffc8; line-height: 1; }
.cal-unit { font-size: 0.85rem; color: #3db87a; margin-right: 1.2rem; }
.cal-sep  { color: #1a2a20; margin: 0 0.3rem; }
.cal-label { font-size: 0.72rem; color: #3a6a50; font-family: 'Space Mono', monospace; margin-top: 0.3rem; }
.cal-offsets {
  font-family: 'Space Mono', monospace; font-size: 0.72rem; color: #1a6a48;
  margin-top: 0.8rem; letter-spacing: 0.05em;
}
.cal-ts { font-family: 'Space Mono', monospace; font-size: 0.6rem; color: #1a3020; margin-top: 0.4rem; }

.no-cal {
  background: #130d03; border: 1px solid #6e3a03;
  border-left: 4px solid #f59e0b; border-radius: 10px;
  padding: 1rem 1.4rem; margin: 1rem 0;
  font-family: 'Space Mono', monospace; font-size: 0.72rem; color: #d29922;
}

.stat-row { display: flex; gap: 1rem; margin: 1.2rem 0; }
.stat-card {
  flex: 1; background: #0a0f18; border: 1px solid #161e2a;
  border-radius: 10px; padding: 1.1rem 1.3rem;
  position: relative; overflow: hidden;
}
.stat-card::after {
  content: ''; position: absolute; bottom: 0; left: 0; right: 0;
  height: 2px; background: var(--accent, #1f6feb);
}
.stat-val {
  font-family: 'Space Mono', monospace; font-size: 1.8rem;
  font-weight: 700; color: var(--accent, #58a6ff); line-height: 1;
}
.stat-label {
  font-size: 0.65rem; color: #3a4a5a; text-transform: uppercase;
  letter-spacing: 0.12em; margin-top: 0.4rem;
}
.stat-delta { font-size: 0.72rem; margin-top: 0.3rem; }
.delta-good { color: #1bffc8; }
.delta-warn { color: #f59e0b; }

.sh {
  font-family: 'Space Mono', monospace; font-size: 0.62rem;
  color: #2a3a4a; text-transform: uppercase; letter-spacing: 0.2em;
  margin: 1.6rem 0 0.8rem; border-bottom: 1px solid #0d1520; padding-bottom: 0.4rem;
}

.fg-card {
  background: #0a0f18; border: 1px solid #161e2a; border-radius: 10px;
  padding: 0.9rem; text-align: center; margin-bottom: 1rem;
  transition: border-color 0.2s;
}
.fg-card:hover { border-color: #253040; }
.fg-fid { font-family:'Space Mono',monospace; font-size:0.7rem; color:#3a5060; margin-bottom:0.3rem; }
.fg-score { font-family:'Space Mono',monospace; font-size:1.1rem; font-weight:700; }
.fg-meta { font-size:0.68rem; color:#2a3a4a; margin-top:0.2rem; }

.ec {
  display: inline-block; font-family: 'Space Mono', monospace;
  font-size: 0.65rem; padding: 2px 8px; border-radius: 4px;
  border: 1px solid; margin: 2px 2px 0;
}
.ec-great { border-color: #0d3d28; color: #1bffc8; background: #041209; }
.ec-good  { border-color: #1a4a1a; color: #3fb950; background: #060d06; }
.ec-ok    { border-color: #4a3a00; color: #d29922; background: #0d0c00; }
.ec-warn  { border-color: #4a1010; color: #f85149; background: #0d0404; }

.insp-row {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 0.74rem; padding: 5px 0;
  border-bottom: 1px solid #0d1520; color: #4a5a6a;
}
.insp-row span:last-child { font-family: 'Space Mono', monospace; color: #9ab0c0; }

.sbar-wrap { background: #0d1520; border-radius: 2px; height: 4px; margin: 3px 0 8px; }
.sbar-fill { height: 4px; border-radius: 2px; }
.sbar-row  { display:flex; justify-content:space-between; font-size:0.7rem;
             color:#3a5060; margin-bottom:1px; }
.sbar-row span:last-child { font-family:'Space Mono',monospace; }

.why-box {
  background: #07121e; border-left: 3px solid #1f6feb;
  border-radius: 0 8px 8px 0; padding: 0.6rem 0.9rem;
  font-size: 0.72rem; color: #4a6070; margin-top: 0.5rem; line-height: 1.6;
}

.fet { width: 100%; border-collapse: collapse; font-size: 0.74rem; }
.fet th {
  font-family: 'Space Mono', monospace; font-size: 0.58rem; color: #2a3a4a;
  text-transform: uppercase; letter-spacing: 0.12em;
  text-align: left; padding: 6px 10px; border-bottom: 1px solid #0d1520;
}
.fet td { padding: 6px 10px; border-bottom: 1px solid #080f18; color: #7a8a9a; }
.fet td.mono { font-family: 'Space Mono', monospace; }
.fet tr:hover td { background: #0a0f18; }
.fet td.good  { color: #1bffc8; }
.fet td.warn  { color: #f85149; }
.fet td.amber { color: #d29922; }

div[data-testid="stMetricValue"] { font-family: 'Space Mono', monospace; }
</style>
""", unsafe_allow_html=True)


def _hav(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin(math.radians(lat2-lat1)/2)**2
         + math.cos(p1)*math.cos(p2)*math.sin(math.radians(lon2-lon1)/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def _score_color(s):
    if s >= 75: return "#1bffc8"
    if s >= 60: return "#3fb950"
    if s >= 45: return "#d29922"
    return "#f85149"

def _err_chip(err_m, label=None):
    if err_m is None:
        return '<span class="ec ec-ok">N/A</span>'
    t = label or f"{err_m:.1f} m"
    if err_m == 0:    cls = "ec-great"
    elif err_m < 5:   cls = "ec-good"
    elif err_m < 15:  cls = "ec-ok"
    else:             cls = "ec-warn"
    return f'<span class="ec {cls}">{t}</span>'

def _delta_html(old, new):
    if old is None or new is None: return ""
    diff = new - old
    if diff < 0:
        pct = abs(diff) / max(old, 0.1) * 100
        return f'<span class="delta-good">▼ {abs(diff):.1f} m  ({pct:.0f}% better)</span>'
    elif diff > 0:
        pct = diff / max(old, 0.1) * 100
        return f'<span class="delta-warn">▲ {diff:.1f} m  ({pct:.0f}% worse)</span>'
    return '<span class="delta-good">— unchanged</span>'

@st.cache_data(show_spinner=False)
def load_calibration():
    if not os.path.exists(CALIBRATION_JSON):
        return None
    with open(CALIBRATION_JSON) as f:
        return json.load(f)

@st.cache_data(show_spinner=False)
def load_buildings(cal_ts):
    if not os.path.exists(SELECTED_JSON):
        return pd.DataFrame()

    with open(SELECTED_JSON) as f:
        buildings = json.load(f)

    buildings = [b for b in buildings
                 if b.get("frame_id") in CURATED_FRAMES or not CURATED_FRAMES]

    cal = load_calibration()
    cal_map = {}
    if cal:
        for fr in cal.get("frames", []):
            cal_map[fr["frame_id"]] = fr

    records = []
    for b in buildings:
        fid = b.get("frame_id")
        img_path = b.get("img_path")
        if not img_path or not os.path.exists(str(img_path)):
            for sub, suf in [("final", "_FINAL.jpg"), ("perceive_vis", "_perceive_vis.jpg")]:
                p = os.path.join(OUT_DIR, sub, f"frame_{int(fid):06d}{suf}")
                if os.path.exists(p):
                    img_path = p; break

        cf = cal_map.get(fid, {})
        records.append({
            "frame_id":          fid,
            "lat":               b.get("centroid_lat"),
            "lon":               b.get("centroid_lon"),
            "raw_lat":           b.get("raw_centroid_lat", b.get("centroid_lat")),
            "raw_lon":           b.get("raw_centroid_lon", b.get("centroid_lon")),
            "smoothing_method":  b.get("smoothing_method", "N/A"),
            "ego_lat":           b.get("ego_lat"),
            "ego_lon":           b.get("ego_lon"),
            "quality_score":     b.get("quality_score", 0),
            "match_score":       b.get("match_score", b.get("score", 0)),
            "angle_off_deg":     b.get("angle_off_deg", 0),
            "dist_m":            b.get("dist_m", 0),
            "confidence":        b.get("confidence", 0),
            "footprint_w_m":     b.get("footprint_w_m"),
            "score_angle":       b.get("score_angle", 0),
            "score_prox":        b.get("score_prox", 0),
            "score_width":       b.get("score_width", 0),
            "score_depth":       b.get("score_depth", 0),
            "n_candidates":      b.get("n_candidates", 0),
            "cluster_size":      b.get("cluster_size", 1),
            "error_m":           b.get("error_m"),
            "cal_error_m":       cf.get("calibrated_error_m"),
            "is_inlier":         cf.get("is_inlier", None),
            "is_polygon_hit":    cf.get("is_polygon_hit", False),
            "why_selected":      b.get("why_selected", ""),
            "img_path":          img_path,
            "gmaps":             b.get("gmaps_building",
                                  f"https://www.google.com/maps/search/?api=1"
                                  f"&query={b.get('centroid_lat',0):.8f},"
                                  f"{b.get('centroid_lon',0):.8f}"),
        })
    return pd.DataFrame(records)

def _file_mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0

_cal_mtime  = _file_mtime(CALIBRATION_JSON)
_sel_mtime  = _file_mtime(SELECTED_JSON)

if "last_cal_mtime" not in st.session_state:
    st.session_state.last_cal_mtime = 0
    st.session_state.last_sel_mtime = 0

if (_cal_mtime != st.session_state.last_cal_mtime or
        _sel_mtime != st.session_state.last_sel_mtime):
    load_calibration.clear()
    load_buildings.clear()
    st.session_state.last_cal_mtime = _cal_mtime
    st.session_state.last_sel_mtime = _sel_mtime

cal = load_calibration()
cal_ts = cal.get("timestamp", "") if cal else ""

with st.spinner("Loading..."):
    df = load_buildings(cal_ts)

if df.empty:
    st.error(
        f"No buildings found in `{SELECTED_JSON}`.\n\n"
        "Run:  `python select_buildings.py`\n\n"
        f"(Looking in: `{OUT_DIR}`)"
    )
    st.stop()

st.markdown("""
<div class="ng-header-wrap">
  <div class="ng-logo">🛰️</div>
  <div class="ng-text-block">
    <span class="ng-wordmark">NazarGeo</span>
    <span class="ng-title">Building Intelligence Dashboard</span>
    <span class="ng-sub">LiDAR × Vision × GOB Fusion</span>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown('<div style="height:0.6rem"></div>', unsafe_allow_html=True)


if cal:
    achieved = cal.get("target_achieved", False)
    mean_m   = cal["inlier_mean_m"]
    med_m    = cal["inlier_median_m"]
    along    = cal["along_offset_m"]
    cross    = cal["cross_offset_m"]
    hits     = cal["sub3m_hits"]
    n_in     = cal["inlier_count"]
    n_tot    = cal["total_frames"]
    thr      = cal["inlier_threshold_m"]
    ts_raw   = cal.get("timestamp", "")

    try:
        ts_fmt = datetime.datetime.fromisoformat(ts_raw).strftime("%d %b %Y  %H:%M")
    except Exception:
        ts_fmt = ts_raw

    if achieved:
        status_label = "✦ SUB-3M TARGET ACHIEVED"
        banner_color = "#1bffc8"
    elif mean_m < 3.0:
        status_label = "✦ SUB-3M MEAN ACHIEVED  (re-run tom.py to confirm)"
        banner_color = "#3fb950"
    else:
        status_label = "⚠  CALIBRATED — TARGET PENDING"
        banner_color = "#d29922"

    st.markdown(f"""
    <div class="cal-banner">
      <div class="cal-achieved" style="color:{banner_color}">{status_label}</div>
      <div class="cal-metric-row">
        <div>
          <div class="cal-big" style="color:{banner_color}">{mean_m:.2f}</div>
          <div class="cal-unit">m inlier mean</div>
        </div>
        <div class="cal-sep">·</div>
        <div>
          <div style="font-family:'Space Mono',monospace;font-size:1.5rem;font-weight:700;color:#0d9a60;line-height:1">{med_m:.2f}</div>
          <div class="cal-unit">m median</div>
        </div>
        <div class="cal-sep">·</div>
        <div>
          <div style="font-family:'Space Mono',monospace;font-size:1.5rem;font-weight:700;color:#1bffc8;line-height:1">{hits}</div>
          <div class="cal-unit">polygon hits (0 m)</div>
        </div>
        <div class="cal-sep">·</div>
        <div>
          <div style="font-family:'Space Mono',monospace;font-size:1.5rem;font-weight:700;color:#3a7a6a;line-height:1">{n_in}/{n_tot}</div>
          <div class="cal-unit">inliers (≤ {thr} m)</div>
       
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown(f"""
    <div class="no-cal">
      ⚠  No calibration data found.<br>
      Run <code>python tom.py</code> to generate <code>{CALIBRATION_JSON}</code>.<br>
      The calibrated error column will appear once tom.py has completed.
    </div>
    """, unsafe_allow_html=True)

cal_errs = df["cal_error_m"].dropna()
raw_errs = df["error_m"].dropna()

raw_avg_str = f"{raw_errs.mean():.1f} m" if len(raw_errs) else "N/A"
cal_avg_str = f"{cal_errs.mean():.1f} m" if len(cal_errs) else "N/A"

if len(cal_errs) and len(raw_errs):
    delta = _delta_html(raw_errs.mean(), cal_errs.mean())
    cal_accent = "#1bffc8" if cal_errs.mean() < 3 else "#3fb950" if cal_errs.mean() < 10 else "#d29922"
else:
    delta = ""
    cal_accent = "#58a6ff"

cols = st.columns(4)

stats = [
    ("Buildings",        str(len(df)),                                   "#58a6ff", ""),
    ("Avg Quality",      f"{df['quality_score'].mean():.1f}",            _score_color(df['quality_score'].mean()), ""),
    ("Avg Match",        f"{df['match_score'].mean():.1f}",              _score_color(df['match_score'].mean()), ""),
    ("Calibrated Error", cal_avg_str,                                     cal_accent, delta),
]

for col, (label, val, color, delta_html) in zip(cols, stats):
    with col:
        st.markdown(f"""
        <div class="stat-card" style="--accent:{color}">
            <div class="stat-val" style="color:{color}">{val}</div>
            <div class="stat-label">{label}</div>
            {f'<div class="stat-delta">{delta_html}</div>' if delta_html else ""}
        </div>
        """, unsafe_allow_html=True)

st.markdown('<div style="height:0.4rem"></div>', unsafe_allow_html=True)


st.markdown('<div class="sh">Map — Vehicle Positions & Matched GOB Buildings</div>',
            unsafe_allow_html=True)

map_col, detail_col = st.columns([58, 42])

with map_col:
    clat = df["lat"].mean()
    clon = df["lon"].mean()
    m = folium.Map(location=[clat, clon], zoom_start=18, tiles="CartoDB dark_matter")

    for _, row in df.iterrows():
        fid   = str(int(row["frame_id"])) if pd.notna(row["frame_id"]) else "?"
        q     = row["quality_score"]
        color = _score_color(q)
        cal_e = row["cal_error_m"]
        raw_e = row["error_m"]
        err_label = (f"{cal_e:.1f} m (cal)" if pd.notna(cal_e) and cal_e is not None
                     else (f"{raw_e:.1f} m" if raw_e else "N/A"))

        if pd.notna(row.get("ego_lat")) and row["ego_lat"]:
            folium.Marker(
                location=[row["ego_lat"], row["ego_lon"]],
                icon=folium.DivIcon(
                    html=(f'<div style="background:#1f6feb;border:2px solid #58a6ff;'
                          f'border-radius:50%;width:12px;height:12px;'
                          f'box-shadow:0 0 8px #58a6ff99;"></div>'),
                    icon_size=(12, 12), icon_anchor=(6, 6),
                ),
                tooltip=f"🚗 Vehicle — Frame {fid}",
                popup=fid,
            ).add_to(m)
            folium.PolyLine(
                [[row["ego_lat"], row["ego_lon"]], [row["lat"], row["lon"]]],
                color=color, weight=1.5, opacity=0.5, dash_array="5"
            ).add_to(m)

        ring_err = cal_e if (pd.notna(cal_e) and cal_e is not None) else raw_e
        if ring_err and ring_err > 0:
            folium.Circle(
                location=[row["lat"], row["lon"]],
                radius=ring_err, color=color, fill=False,
                opacity=0.25, tooltip=f"Error radius: {ring_err:.1f} m",
            ).add_to(m)

        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=11, color=color, fill=True, fill_color=color, fill_opacity=0.9,
            tooltip=f"🏢 Frame {fid} | Q={q:.1f} | err={err_label}",
            popup=fid,
        ).add_to(m)

    legend_html = """
    <div style="position:fixed;bottom:18px;left:18px;z-index:9999;
    background:#060a0f;border:1px solid #161e2a;border-radius:8px;
    padding:10px 14px;font-family:'Space Mono',monospace;font-size:10px;color:#4a6070;">
    <b style="color:#bcc8d4;letter-spacing:0.1em">LEGEND</b><br>
    <span style="color:#58a6ff">●</span> Vehicle<br>
    <span style="color:#1bffc8">●</span> Bldg score ≥75<br>
    <span style="color:#3fb950">●</span> Score ≥60<br>
    <span style="color:#d29922">●</span> Score ≥45<br>
    <span style="color:#f85149">●</span> Score &lt;45<br>
    ○ Error radius (cal)
    </div>"""
    m.get_root().html.add_child(folium.Element(legend_html))

    map_data = st_folium(m, width=None, height=540,
                         returned_objects=["last_object_clicked_popup"])

with detail_col:
    st.markdown('<div class="sh">Building Inspector</div>', unsafe_allow_html=True)

    clicked = map_data.get("last_object_clicked_popup")
    if not clicked and len(df):
        best_row = df.loc[df["quality_score"].idxmax()]
        clicked = str(int(best_row["frame_id"]))

    if clicked:
        try:
            fid_int = int(clicked)
        except (ValueError, TypeError):
            fid_int = None

        if fid_int is not None:
            rows = df[df["frame_id"] == fid_int]
            if not rows.empty:
                row = rows.iloc[0]
                q, ms = row["quality_score"], row["match_score"]

                cq, cm = st.columns(2)
                with cq:
                    st.markdown(
                        f'<div class="stat-card" style="--accent:{_score_color(q)}">'
                        f'<div class="stat-val" style="color:{_score_color(q)}">{q:.1f}</div>'
                        f'<div class="stat-label">Quality / 100</div></div>',
                        unsafe_allow_html=True)
                with cm:
                    st.markdown(
                        f'<div class="stat-card" style="--accent:{_score_color(ms)}">'
                        f'<div class="stat-val" style="color:{_score_color(ms)}">{ms:.1f}</div>'
                        f'<div class="stat-label">GOB Match / 100</div></div>',
                        unsafe_allow_html=True)

                st.markdown('<div style="height:0.6rem"></div>', unsafe_allow_html=True)

                for slabel, val, mx, c in [
                    ("Angle",     row["score_angle"], 35.0, "#58a6ff"),
                    ("Proximity", row["score_prox"],  50.0, "#1bffc8"),
                    ("Width",     row["score_width"], 15.0, "#d29922"),
                    ("Depth",     row["score_depth"], 10.0, "#f85149"),
                ]:
                    pct = min(val / mx * 100, 100) if mx else 0
                    st.markdown(
                        f'<div class="sbar-row"><span>{slabel}</span>'
                        f'<span style="color:{c}">{val:.1f}</span></div>'
                        f'<div class="sbar-wrap">'
                        f'<div class="sbar-fill" style="width:{pct:.0f}%;background:{c}"></div>'
                        f'</div>', unsafe_allow_html=True)

                st.markdown('<div style="height:0.4rem"></div>', unsafe_allow_html=True)

                ego_gps = (f"{row.get('ego_lat','N/A'):.6f}, {row.get('ego_lon','N/A'):.6f}"
                           if pd.notna(row.get("ego_lat")) else "N/A")
                for k, v in [
                    ("Frame",            f"#{fid_int}"),
                    ("GOB GPS",          f"{row['lat']:.6f}, {row['lon']:.6f}"),
                    ("Vehicle GPS",      ego_gps),
                    ("Smoothing",        row["smoothing_method"]),
                    ("Angle off hdg",    f"{row['angle_off_deg']:.2f}°"),
                    ("LiDAR distance",   f"{row['dist_m']:.1f} m"),
                    ("GOB confidence",   f"{row['confidence']:.1%}" if row['confidence'] else "N/A"),
                    ("Footprint width",  f"{row['footprint_w_m']:.1f} m" if row['footprint_w_m'] else "N/A"),
                    ("Cluster size",     str(int(row["cluster_size"]))),
                    ("GOB candidates",   str(int(row["n_candidates"])) if row["n_candidates"] else "N/A"),
                ]:
                    st.markdown(
                        f'<div class="insp-row"><span>{k}</span><span>{v}</span></div>',
                        unsafe_allow_html=True)

                st.markdown('<div style="height:0.5rem"></div>', unsafe_allow_html=True)

                st.markdown('<div style="font-size:0.65rem;color:#2a3a4a;text-transform:uppercase;'
                            'letter-spacing:0.12em;margin-bottom:0.4rem">Polygon-Edge Error</div>',
                            unsafe_allow_html=True)

                pre_e  = row["error_m"]
                post_e = row["cal_error_m"]
                chips  = ""
                if pre_e is not None:
                    chips += _err_chip(pre_e, f"pre-cal: {pre_e:.1f} m")
                if post_e is not None:
                    chips += _err_chip(post_e, f"calibrated: {post_e:.2f} m")
                if not chips:
                    chips = '<span style="font-size:0.7rem;color:#2a3a4a">No error data yet — run tom.py</span>'
                st.markdown(chips, unsafe_allow_html=True)

                if pre_e is not None and post_e is not None:
                    st.markdown(
                        f'<div style="font-size:0.7rem;margin-top:0.3rem">'
                        f'{_delta_html(pre_e, post_e)}</div>',
                        unsafe_allow_html=True)

                if row.get("is_polygon_hit"):
                    st.markdown(
                        '<div style="font-size:0.65rem;color:#0d6a40;margin-top:0.3rem">'
                        '✦ GPS estimated inside building footprint</div>',
                        unsafe_allow_html=True)

                if row.get("why_selected"):
                    st.markdown(
                        f'<div style="font-size:0.65rem;color:#2a3a4a;margin:0.8rem 0 0.2rem;'
                        f'text-transform:uppercase;letter-spacing:0.1em">Selection Rationale</div>'
                        f'<div class="why-box">{row["why_selected"]}</div>',
                        unsafe_allow_html=True)

                st.markdown(
                    f'<div style="margin-top:0.8rem;font-size:0.72rem">'
                    f'<a href="{row["gmaps"]}" target="_blank" style="color:#1f6feb">Open in Maps ↗</a>'
                    f'</div>', unsafe_allow_html=True)

                ip = row["img_path"]
                if ip and os.path.exists(str(ip)):
                    st.image(Image.open(ip), use_container_width=True,
                             caption=f"Frame {fid_int} — LiDAR + Vision overlay")
                else:
                    st.markdown(
                        '<div style="font-size:0.7rem;color:#2a3a4a;margin-top:0.6rem">'
                        'No image — run presniff.py first.</div>',
                        unsafe_allow_html=True)


st.markdown('<div class="sh">All Selected Buildings</div>', unsafe_allow_html=True)

cols3 = st.columns(3)
for i, (_, row) in enumerate(df.sort_values("quality_score", ascending=False).iterrows()):
    q   = row["quality_score"]
    fid = int(row["frame_id"]) if pd.notna(row["frame_id"]) else "?"
    cal_e = row["cal_error_m"]
    raw_e = row["error_m"]

    with cols3[i % 3]:
        ip = row["img_path"]
        if ip and os.path.exists(str(ip)):
            st.image(Image.open(ip), use_container_width=True)

        chips = ""
        if raw_e is not None:
            chips += _err_chip(raw_e, f"pre: {raw_e:.1f} m")
        if cal_e is not None:
            chips += _err_chip(cal_e, f"cal: {cal_e:.2f} m")

        cal_status = ""
        if row.get("is_polygon_hit"):
            cal_status = '<div style="font-size:0.6rem;color:#1bffc8;margin-top:2px">✦ inside polygon</div>'
        elif row.get("is_inlier") is True:
            cal_status = '<div style="font-size:0.6rem;color:#3fb950;margin-top:2px">● inlier</div>'
        elif row.get("is_inlier") is False:
            cal_status = '<div style="font-size:0.6rem;color:#f85149;margin-top:2px">✕ outlier</div>'

        st.markdown(
            f'<div class="fg-card">'
            f'<div class="fg-fid">Frame #{fid}</div>'
            f'<div class="fg-score" style="color:{_score_color(q)}">{q:.1f}'
            f'<span style="font-size:0.55rem;color:#2a3a4a;margin-left:4px">QUALITY</span></div>'
            f'<div class="fg-meta">match {row["match_score"]:.1f} · dist {row["dist_m"]:.0f} m'
            f' · {row["angle_off_deg"]:.1f}°</div>'
            f'<div style="margin-top:0.4rem">{chips}</div>'
            f'{cal_status}'
            f'</div>', unsafe_allow_html=True)


with st.sidebar:
    st.markdown("### Raw Data")
    show = ["frame_id", "quality_score", "match_score", "angle_off_deg",
            "dist_m", "confidence", "error_m", "cal_error_m",
            "cluster_size", "smoothing_method"]
    st.dataframe(df[[c for c in show if c in df.columns]].round(2),
                 use_container_width=True)

    if cal:
        st.markdown("### Calibration (tom.py output)")
        st.json({
            "along_offset_m":  cal["along_offset_m"],
            "cross_offset_m":  cal["cross_offset_m"],
            "inlier_mean_m":   cal["inlier_mean_m"],
            "inlier_median_m": cal["inlier_median_m"],
            "target_achieved": cal["target_achieved"],
            "timestamp":       cal.get("timestamp", ""),
        })

    rp = os.path.join(OUT_DIR, "selection_report.txt")
    if os.path.exists(rp):
        with open(rp) as f:
            txt = f.read()
        st.download_button("Download report", txt, "selection_report.txt")
        with st.expander("View report"):
            st.code(txt, language=None)

    with st.expander("📂 File paths (debug)"):
        st.code(
            f"OUT_DIR:          {OUT_DIR}\n"
            f"selected_buildings exists: {os.path.exists(SELECTED_JSON)}\n"
            f"calibration exists:        {os.path.exists(CALIBRATION_JSON)}\n"
            f"Buildings loaded:          {len(df)}\n"
            f"Cal timestamp:             {cal.get('timestamp','—') if cal else '—'}\n"
            f"Along offset:              {cal['along_offset_m'] if cal else '—'}\n"
            f"Cross offset:              {cal['cross_offset_m'] if cal else '—'}",
            language=None,
        )