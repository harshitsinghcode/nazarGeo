import streamlit as st
import json
import os
import cv2
import numpy as np
import glob
import pandas as pd
import sys

sys.path.insert(0, os.path.dirname(__file__))

st.set_page_config(
    page_title="GeoAssign — Building Association Pipeline",
    layout="wide",
    initial_sidebar_state="expanded"
)

OUT_DIR = os.path.join(os.path.dirname(__file__), "out")

st.markdown("""
<style>
.metric-card {
    background: #1e1e2e;
    border-radius: 10px;
    padding: 16px;
    margin: 4px 0;
    border-left: 4px solid #7c3aed;
}
.score-high  { border-left-color: #22c55e; }
.score-med   { border-left-color: #eab308; }
.score-low   { border-left-color: #ef4444; }
.track-badge {
    display: inline-block;
    background: #7c3aed;
    color: white;
    border-radius: 12px;
    padding: 2px 10px;
    font-size: 12px;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)


def load_manifest():
    path = os.path.join(OUT_DIR, "manifest.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def load_result(frame_id, kind):
    path = os.path.join(OUT_DIR, f"frame_{frame_id:06d}_{kind}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def load_stable(frame_id):
    path = os.path.join(OUT_DIR, f"frame_{frame_id:06d}_stable.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def available_frames():
    files = glob.glob(os.path.join(OUT_DIR, "frame_*_perceive.json"))
    frames = []
    for f in files:
        base = os.path.basename(f)
        try:
            fid = int(base.split("_")[1])
            frames.append(fid)
        except Exception:
            pass
    return sorted(frames)


def score_color(score):
    if score >= 65:
        return "score-high", "🟢"
    elif score >= 45:
        return "score-med", "🟡"
    else:
        return "score-low", "🔴"


def sidebar_controls():
    st.sidebar.title("⚙️ Controls")

    frames = available_frames()
    if not frames:
        st.sidebar.warning("No processed frames found in `out/`")
        st.sidebar.info("Run: `python run_batch.py --frames 716,717,840`")
        return None, None

    st.sidebar.markdown(f"**{len(frames)} processed frames**")

    frame_id = st.sidebar.selectbox(
        "Select frame",
        frames,
        index=len(frames) - 1
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Run pipeline**")

    run_frame_input = st.sidebar.text_input("Frame to run", "840")
    if st.sidebar.button("▶ Run single frame", use_container_width=True):
        with st.spinner(f"Running frame {run_frame_input}..."):
            ret = os.system(
                f"cd {os.path.dirname(__file__)} && "
                f"python run_batch.py --frame {run_frame_input} --skip-sync"
            )
            if ret == 0:
                st.sidebar.success("Done!")
            else:
                st.sidebar.error("Error — check terminal")
        st.rerun()

    range_input = st.sidebar.text_input("Frame range (e.g. 716-730)", "716-730")
    step_input  = st.sidebar.number_input("Step", 1, 10, 2)
    if st.sidebar.button("▶ Run range", use_container_width=True):
        with st.spinner(f"Running range {range_input}..."):
            ret = os.system(
                f"cd {os.path.dirname(__file__)} && "
                f"python run_batch.py --range {range_input} --step {step_input} --skip-sync"
            )
            if ret == 0:
                st.sidebar.success("Done!")
            else:
                st.sidebar.error("Error — check terminal")
        st.rerun()

    return frame_id, frames


def render_frame_view(frame_id):
    perc   = load_result(frame_id, "perceive")
    proj   = load_result(frame_id, "project")
    match  = load_result(frame_id, "match")
    stable = load_stable(frame_id)

    col_img, col_info = st.columns([2, 1])

    with col_img:
        st.subheader(f"Frame {frame_id:06d}")

        vis_candidates = [
            os.path.join(OUT_DIR, f"frame_{frame_id:06d}_FINAL.jpg"),
            os.path.join(OUT_DIR, f"frame_{frame_id:06d}_perceive_vis.jpg"),
            os.path.join(OUT_DIR, f"frame_{frame_id:06d}_raw.jpg"),
        ]
        vis_path = next((p for p in vis_candidates if os.path.exists(p)), None)

        if vis_path:
            img = cv2.imread(vis_path)
            if img is not None:
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                st.image(img_rgb, use_container_width=True,
                         caption=os.path.basename(vis_path))
        else:
            st.info("No visualization found. Run the pipeline on this frame.")

    with col_info:
        if perc:
            st.markdown("### Perception")
            depth = perc.get("median_depth", 0)
            n_pts = perc.get("depth_pts", 0)
            conf  = perc.get("det_conf", 0)
            bbox  = perc.get("bbox") or perc.get("bbox_px")

            st.metric("Depth", f"{depth:.2f} m")
            st.metric("LiDAR pts in mask", f"{n_pts:,}")
            st.metric("Detection conf", f"{conf:.2f}")
            if bbox:
                st.caption(f"BBox: {bbox}")

        if match:
            st.markdown("### Match")
            best = match["best_match"]
            sc   = best["score"]
            css, icon = score_color(sc)
            st.markdown(
                f'<div class="metric-card {css}">'
                f'{icon} Score: <b>{sc:.1f}/100</b><br>'
                f'ang={best["score_angle"]:.1f} '
                f'prox={best["score_prox"]:.1f} '
                f'w={best["score_width"]:.1f} '
                f'dep={best.get("score_depth", 0):.1f}'
                f'</div>',
                unsafe_allow_html=True
            )
            st.metric("Distance to match", f"{best['dist_m']:.1f} m")
            st.metric("Angle offset", f"{best['angle_off_deg']:.1f}°")
            if best.get("confidence"):
                st.metric("GOB confidence", f"{best['confidence']:.3f}")

        if stable:
            st.markdown("### Stable GPS (Kalman)")
            s = stable["stable"]
            st.markdown(
                f'<span class="track-badge">Track #{s["track_id"]} '
                f'· {s["track_hits"]} hits</span>',
                unsafe_allow_html=True
            )
            st.metric("Stable lat", f"{s['stable_lat']:.6f}")
            st.metric("Stable lon", f"{s['stable_lon']:.6f}")
            st.metric("Smoothed by", f"{s['smoothing_delta_m']:.1f} m")
            st.markdown(f"[📍 Open in Maps]({s['gmaps']})")

        elif proj and match:
            best = match["best_match"]
            st.markdown("### GPS (raw, no tracker)")
            st.metric("Lat", f"{best['centroid_lat']:.6f}")
            st.metric("Lon", f"{best['centroid_lon']:.6f}")
            gmaps = f"https://www.google.com/maps/search/?api=1&query={best['centroid_lat']},{best['centroid_lon']}"
            st.markdown(f"[📍 Open in Maps]({gmaps})")


def render_candidates_table(frame_id):
    match = load_result(frame_id, "match")
    if not match:
        return

    st.subheader("All candidates")
    cands = match.get("all_candidates", [])
    if not cands:
        return

    rows = []
    for i, c in enumerate(cands):
        rows.append({
            "rank":        i + 1,
            "score":       c["score"],
            "ang":         c["score_angle"],
            "prox":        c["score_prox"],
            "width":       c["score_width"],
            "depth_bonus": c.get("score_depth", 0),
            "dist_m":      c["dist_m"],
            "angle_off":   c["angle_off_deg"],
            "lat":         round(c["centroid_lat"], 6),
            "lon":         round(c["centroid_lon"], 6),
            "gob_conf":    c.get("confidence", ""),
        })

    df = pd.DataFrame(rows)
    st.dataframe(
        df.style.background_gradient(subset=["score"], cmap="RdYlGn"),
        use_container_width=True,
        height=300
    )


def render_batch_chart(frames):
    st.subheader("Batch — scores across frames")

    data = []
    for fid in frames:
        m = load_result(fid, "match")
        p = load_result(fid, "perceive")
        s = load_stable(fid)
        if m:
            row = {
                "frame":     fid,
                "score":     m["best_match"]["score"],
                "depth":     p["median_depth"] if p else None,
                "dist_m":    m["best_match"]["dist_m"],
                "stable":    s["stable"]["track_hits"] if s else 0,
            }
            data.append(row)

    if not data:
        st.info("No batch data yet.")
        return

    df = pd.DataFrame(data).set_index("frame")
    st.line_chart(df[["score"]], height=200)

    col1, col2 = st.columns(2)
    with col1:
        if "depth" in df.columns:
            st.line_chart(df[["depth"]], height=160)
            st.caption("LiDAR depth per frame")
    with col2:
        if "dist_m" in df.columns:
            st.line_chart(df[["dist_m"]], height=160)
            st.caption("GOB match distance per frame")


def render_batch_summary():
    path = os.path.join(OUT_DIR, "batch_summary.json")
    if not os.path.exists(path):
        return
    with open(path) as f:
        data = json.load(f)
    s = data.get("summary", {})
    if not s:
        return

    st.subheader("Batch summary")
    cols = st.columns(4)
    cols[0].metric("Frames", s.get("frames_processed", 0))
    cols[1].metric("Lat spread", f"{s.get('lat_spread_m', 0):.2f} m")
    cols[2].metric("Lon spread", f"{s.get('lon_spread_m', 0):.2f} m")
    cols[3].metric("Mean smoothing", f"{s.get('mean_smoothing_delta_m', 0):.2f} m")

    mean_lat = s.get("mean_lat", 0)
    mean_lon = s.get("mean_lon", 0)
    if mean_lat and mean_lon:
        gmaps = f"https://www.google.com/maps/search/?api=1&query={mean_lat:.8f},{mean_lon:.8f}"
        st.markdown(f"**Mean stable GPS:** `{mean_lat:.6f}, {mean_lon:.6f}` — [📍 Maps]({gmaps})")


def main():
    st.title("🏢 GeoAssign — Building Geo-Association Pipeline")
    st.caption("Visual debugger for the 4-phase sensor fusion pipeline")

    frame_id, frames = sidebar_controls()

    if frame_id is None:
        st.info("No processed frames found. Use the sidebar controls to run the pipeline.")
        return

    tab1, tab2, tab3 = st.tabs(["🖼 Frame view", "📊 Candidates", "📈 Batch analysis"])

    with tab1:
        render_frame_view(frame_id)

    with tab2:
        render_candidates_table(frame_id)

    with tab3:
        render_batch_summary()
        if frames:
            render_batch_chart(frames)


if __name__ == "__main__":
    main()