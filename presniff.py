import os
import json
import math
import argparse
import statistics

import cv2
import numpy as np

import cfg
import lidar_pcap
import sync
import perceive
import project
import match

def _haversine_m(lat1, lon1, lat2, lon2):
    R    = 6_371_000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a    = (math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _draw_final(perc, proj, best, frame_id):
    
    vis_path = perc.get("vis") or os.path.join(
        cfg.OUT_DIR, "perceive_vis", f"frame_{frame_id:06d}_perceive_vis.jpg"
    )
    img = cv2.imread(vis_path)
    if img is None:
        print(f"  [WARN] could not load vis image: {vis_path}")
        return None

    h, w = img.shape[:2]
    box  = perc.get("bbox_px") or perc.get("bbox")
    bx   = int((box[0] + box[2]) / 2)
    by   = int((box[1] + box[3]) / 2)

    cv2.line(img, (w // 2, h), (bx, by), (0, 255, 255), 3, cv2.LINE_AA)
    cv2.circle(img, (bx, by), 10, (0, 165, 255), -1)

    tx = bx + 20
    if tx > w - 520:
        tx = bx - 540
    tx = max(tx, 10)
    ty = max(by - 50, 70)

    ov = img.copy()
    cv2.rectangle(ov, (tx - 10, ty - 40), (tx + 510, ty + 95), (0, 0, 0), -1)
    cv2.addWeighted(ov, 0.65, img, 0.35, 0, img)

    font = cv2.FONT_HERSHEY_SIMPLEX

    err_m = _haversine_m(
        proj["target_lat"], proj["target_lon"],
        best["centroid_lat"], best["centroid_lon"]
    )

    lines_colors = [
        (f"Depth: {proj['depth_m']:.1f} m",                                      (0, 255, 255), 0.8),
        (f"GOB GPS: {best['centroid_lat']:.6f}, {best['centroid_lon']:.6f}",      (0, 255, 0),   0.7),
        (f"Score: {best['score']:.1f}   Frame: {frame_id}",                       (255, 200, 0), 0.6),
    ]
    for idx, (text, color, scale) in enumerate(lines_colors):
        y_pos = ty + idx * 40
        cv2.putText(img, text, (tx, y_pos), font, scale, (0, 0, 0), 4)
        cv2.putText(img, text, (tx, y_pos), font, scale, color,   2)

    final_dir = os.path.join(cfg.OUT_DIR, "final")
    os.makedirs(final_dir, exist_ok=True)
    out_path = os.path.join(final_dir, f"frame_{frame_id:06d}_FINAL.jpg")
    cv2.imwrite(out_path, img)
    return out_path


def process_frames(start, end, step):

    for sub in ["perceive_json", "perceive_vis", "project_json",
                "match_json", "raw", "final", "summary"]:
        os.makedirs(os.path.join(cfg.OUT_DIR, sub), exist_ok=True)

    print("=" * 60)
    print("=== Phase 0: Building manifest (sync) ===")
    sync.build_manifest()
    print(f"  manifest → {cfg.MANIFEST_PATH}\n")

    print("=== Phase 1: Pre-loading LiDAR (one-time) ===")
    lidar_pcap.load_both(cfg.L1_PCAP_PATH, cfg.L2_PCAP_PATH)
    print("=== LiDAR cached. Starting frame loop ===\n")

    frames  = list(range(start, end + 1, step))
    total   = len(frames)
    success = 0
    skipped = 0

    gps_records = []

    for i, fid in enumerate(frames):
        print(f"\n{'=' * 60}")
        print(f"  Frame {fid:06d}   ({i + 1}/{total})")
        print(f"{'=' * 60}")

        try:
            perc = perceive.run_frame(fid)
        except FileNotFoundError as e:
            print(f"  [SKIP] image missing: {e}")
            skipped += 1
            continue
        except Exception as e:
            print(f"  [SKIP] perceive error: {e}")
            skipped += 1
            continue

        if perc is None:
            print(f"  [SKIP] no building detected")
            skipped += 1
            continue

        try:
            proj = project.run_frame(fid)
        except Exception as e:
            print(f"  [SKIP] project error: {e}")
            skipped += 1
            continue

        if proj is None:
            print(f"  [SKIP] project returned None")
            skipped += 1
            continue

        try:
            result = match.run_frame(fid)
        except Exception as e:
            print(f"  [WARN] match error: {e}")
            continue

        if result is None:
            print(f"  [WARN] no GOB match found for frame {fid}")
            continue

        best = result["best_match"]

        err_m = _haversine_m(
            proj["target_lat"], proj["target_lon"],
            best["centroid_lat"], best["centroid_lon"]
        )

        final_out = _draw_final(perc, proj, best, fid)

        success += 1

        print(f"\n  ✓ Frame {fid}")
        print(f"     Vehicle GPS  : {proj['ego_lat']:.7f}, {proj['ego_lon']:.7f}")
        print(f"     Estimated GPS: {proj['target_lat']:.7f}, {proj['target_lon']:.7f}  (depth={proj['depth_m']:.1f} m, heading={proj['heading_deg']:.1f}°)")
        print(f"     GOB match GPS: {best['centroid_lat']:.7f}, {best['centroid_lon']:.7f}  (score={best['score']:.1f})")
        print(f"  ┌─ ERROR  est_GPS → GOB_GPS  =  {err_m:.2f} m  {'✓ GOOD' if err_m < 15 else '⚠ HIGH' if err_m < 40 else '✗ LARGE'}")
        print(f"  └─ angle_off={best['angle_off_deg']:.1f}°   dist={best['dist_m']:.1f} m   GOB_conf={best.get('confidence') or 'N/A'}")

        if final_out:
            print(f"     final image  → {final_out}")

        gps_records.append({
            "frame_id":      fid,

            "vehicle_gps": {
                "lat":         proj["ego_lat"],
                "lon":         proj["ego_lon"],
                "heading_deg": proj["heading_deg"],
            },

            "estimated_gps": {
                "lat":      proj["target_lat"],
                "lon":      proj["target_lon"],
                "depth_m":  proj["depth_m"],
                "gmaps":    proj.get("gmaps", ""),
            },

            "gob_match_gps": {
                "lat":           best["centroid_lat"],
                "lon":           best["centroid_lon"],
                "score":         best["score"],
                "angle_off_deg": best["angle_off_deg"],
                "dist_m":        best["dist_m"],
                "confidence":    best.get("confidence"),
                "footprint_w_m": best.get("footprint_w_m"),
                "score_angle":   best.get("score_angle"),
                "score_prox":    best.get("score_prox"),
                "score_width":   best.get("score_width"),
                "score_depth":   best.get("score_depth"),
                "gmaps": (
                    f"https://www.google.com/maps/search/?api=1"
                    f"&query={best['centroid_lat']:.8f},{best['centroid_lon']:.8f}"
                ),
            },

            "error_est_to_gob_m": round(err_m, 3),
        })

    if gps_records:
        errors      = [r["error_est_to_gob_m"] for r in gps_records]
        avg_err     = statistics.mean(errors)
        median_err  = statistics.median(errors)
        min_err     = min(errors)
        max_err     = max(errors)
        stdev_err   = statistics.stdev(errors) if len(errors) > 1 else 0.0

        best_frame  = gps_records[errors.index(min_err)]["frame_id"]
        worst_frame = gps_records[errors.index(max_err)]["frame_id"]

        summary_stats = {
            "frames_processed":  success,
            "avg_error_m":       round(avg_err,    3),
            "median_error_m":    round(median_err, 3),
            "min_error_m":       round(min_err,    3),
            "max_error_m":       round(max_err,    3),
            "stdev_error_m":     round(stdev_err,  3),
            "best_frame_id":     best_frame,
            "worst_frame_id":    worst_frame,
            "pct_under_15m":     round(100 * sum(1 for e in errors if e < 15)  / len(errors), 1),
            "pct_under_30m":     round(100 * sum(1 for e in errors if e < 30)  / len(errors), 1),
            "pct_under_50m":     round(100 * sum(1 for e in errors if e < 50)  / len(errors), 1),
        }

        comparison_out = {
            "summary": summary_stats,
            "frames":  gps_records,
        }

        comp_path = os.path.join(cfg.OUT_DIR, "gps_comparison.json")
        with open(comp_path, "w") as f:
            json.dump(comparison_out, f, indent=2)
        print(f"\n[presniff] GPS comparison JSON → {comp_path}")
    else:
        summary_stats = {}
        comp_path     = None

    print(f"\n{'=' * 60}")
    print(f"  DONE — {success} matched  /  {skipped} skipped  /  {total} total frames")
    print(f"{'=' * 60}")

    if gps_records:
        print(f"\n  ┌──────────────────────────────────────────────┐")
        print(f"  │        GPS ERROR SUMMARY (est → GOB)         │")
        print(f"  ├──────────────────────────────────────────────┤")
        print(f"  │  Frames measured : {success:<26}│")
        print(f"  │  Avg   error     : {avg_err:>8.2f} m                    │")
        print(f"  │  Median error    : {median_err:>8.2f} m                    │")
        print(f"  │  Min   error     : {min_err:>8.2f} m   (frame {best_frame})       │")
        print(f"  │  Max   error     : {max_err:>8.2f} m   (frame {worst_frame})       │")
        print(f"  │  Std   dev       : {stdev_err:>8.2f} m                    │")
        print(f"  ├──────────────────────────────────────────────┤")
        print(f"  │  % frames < 15 m : {summary_stats['pct_under_15m']:>5.1f}%                      │")
        print(f"  │  % frames < 30 m : {summary_stats['pct_under_30m']:>5.1f}%                      │")
        print(f"  │  % frames < 50 m : {summary_stats['pct_under_50m']:>5.1f}%                      │")
        print(f"  └──────────────────────────────────────────────┘")

    print(f"\n  Outputs under: {cfg.OUT_DIR}")
    print(f"    raw/                ← raw camera frames (JPG)")
    print(f"    perceive_json/      ← YOLO+SAM+LiDAR depth per frame")
    print(f"    perceive_vis/       ← annotated LiDAR overlay images")
    print(f"    project_json/       ← estimated target GPS per frame")
    print(f"    match_json/         ← best GOB match per frame")
    print(f"    final/              ← final annotated images with GPS overlay")
    print(f"    gps_comparison.json ← vehicle / estimated / GOB GPS + errors")

    print(f"\n  Next steps:")
    print(f"    python select_buildings.py --start {start} --end {end}")
    print(f"    streamlit run viewer.py")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="NazarGeo batch pipeline: sync→perceive→project→match"
    )
    ap.add_argument("--start", type=int, default=cfg.FRAME_START,
                    help="First frame to process")
    ap.add_argument("--end",   type=int, default=cfg.FRAME_END,
                    help="Last frame to process (inclusive)")
    ap.add_argument("--step",  type=int, default=25,
                    help="Process every Nth frame (default: every 25th)")
    args = ap.parse_args()

    process_frames(args.start, args.end, args.step)