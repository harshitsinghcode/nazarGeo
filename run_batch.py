import argparse
import os
import sys
import json
import cv2
import numpy as np
import cfg
import sync
import perceive
import project
import match
from tracker import GPSStabilizer


def _draw_final(perc, proj, best_raw, best_stable, frame_id):
    vis_path = perc.get("vis") or os.path.join(
        cfg.OUT_DIR, f"frame_{frame_id:06d}_perceive_vis.jpg"
    )
    img = cv2.imread(vis_path)
    if img is None:
        return

    h, w = img.shape[:2]
    box  = perc.get("bbox_px") or perc.get("bbox")
    bx   = int((box[0] + box[2]) / 2)
    by   = int((box[1] + box[3]) / 2)

    cv2.line(img, (w // 2, h), (bx, by), (0, 255, 255), 3, cv2.LINE_AA)
    cv2.circle(img, (bx, by), 10, (0, 165, 255), -1)

    tx = min(bx + 20, w - 500)
    ty = max(by - 50, 60)

    ov = img.copy()
    cv2.rectangle(ov, (tx - 10, ty - 35), (tx + 490, ty + 130), (0,0,0), -1)
    cv2.addWeighted(ov, 0.7, img, 0.3, 0, img)

    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(img, f"Depth: {proj['depth_m']:.1f}m",
                (tx, ty),       font, 0.8, (0,255,255), 2)
    cv2.putText(img, f"Raw GPS:    {best_raw['centroid_lat']:.5f}, {best_raw['centroid_lon']:.5f}",
                (tx, ty + 40),  font, 0.6, (200,200,200), 1)
    cv2.putText(img, f"Stable GPS: {best_stable['stable_lat']:.5f}, {best_stable['stable_lon']:.5f}",
                (tx, ty + 78),  font, 0.7, (0,255,0), 2)
    cv2.putText(img, f"Track #{best_stable['track_id']}  hits={best_stable['track_hits']}",
                (tx, ty + 115), font, 0.6, (255,200,0), 1)

    out_path = os.path.join(cfg.OUT_DIR, f"final/frame_{frame_id:06d}_FINAL.jpg")
    cv2.imwrite(out_path, img)
    return out_path


def run_single(frame_id, stabilizer, skip_sync=False):
    if not skip_sync or not os.path.exists(cfg.MANIFEST_PATH):
        sync.build_manifest()

    perc = perceive.run_frame(frame_id)
    if perc is None:
        stabilizer.ingest(frame_id, None, None)
        return None

    proj = project.run_frame(frame_id)
    if proj is None:
        stabilizer.ingest(frame_id, None, None)
        return None

    result = match.run_frame(frame_id)
    if result is None:
        stabilizer.ingest(frame_id, None, None)
        return None

    stable = stabilizer.ingest(frame_id, result, perc)
    if stable is None:
        return None

    best_raw = result["best_match"]

    vis_out = _draw_final(perc, proj, best_raw, stable, frame_id)

    out = {
        "frame_id":       frame_id,
        "raw_match":      best_raw,
        "stable":         stable,
        "depth_m":        proj["depth_m"],
        "ego_lat":        proj["ego_lat"],
        "ego_lon":        proj["ego_lon"],
        "heading_deg":    proj["heading_deg"],
        "vis":            vis_out
    }

    out_path = os.path.join(cfg.OUT_DIR, f"stable_json/frame_{frame_id:06d}_stable.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    print(f"\n{'='*56}")
    print(f"RESULT  frame={frame_id}")
    print(f"  depth         {proj['depth_m']:.2f} m")
    print(f"  raw GPS       {best_raw['centroid_lat']:.6f}, {best_raw['centroid_lon']:.6f}")
    print(f"  stable GPS    {stable['stable_lat']:.6f}, {stable['stable_lon']:.6f}")
    print(f"  smoothed by   {stable['smoothing_delta_m']:.1f} m")
    print(f"  track         #{stable['track_id']}  hits={stable['track_hits']}  age={stable['track_age']}")
    print(f"  raw score     {best_raw['score']:.1f}/100")
    print(f"  gmaps         {stable['gmaps']}")
    print(f"{'='*56}")

    return out


def run_batch(frames, skip_sync=False):
    os.makedirs(cfg.OUT_DIR, exist_ok=True)
    os.makedirs(os.path.join(cfg.OUT_DIR, "perceive_json"), exist_ok=True)
    os.makedirs(os.path.join(cfg.OUT_DIR, "project_json"), exist_ok=True)
    os.makedirs(os.path.join(cfg.OUT_DIR, "match_json"), exist_ok=True)
    os.makedirs(os.path.join(cfg.OUT_DIR, "stable_json"), exist_ok=True)
    os.makedirs(os.path.join(cfg.OUT_DIR, "perceive_vis"), exist_ok=True)
    stabilizer = GPSStabilizer()

    if not skip_sync or not os.path.exists(cfg.MANIFEST_PATH):
        print("=== Phase 1: sync ===")
        sync.build_manifest()

    results = []
    for i, fid in enumerate(frames):
        print(f"\n[batch] ── frame {fid} ({i+1}/{len(frames)}) ──")
        r = run_single(fid, stabilizer, skip_sync=True)
        if r is not None:
            results.append(r)

    summary = stabilizer.summary()
    summary_path = os.path.join(cfg.OUT_DIR, "summary/frame_{frame_id:06d}_batch_summary.json")
    with open(summary_path, "w") as f:
        json.dump({"summary": summary, "frames": len(results)}, f, indent=2)

    print(f"\n{'='*56}")
    print(f"BATCH SUMMARY  ({summary.get('frames_processed', 0)} frames, "
          f"{summary.get('tracks_confirmed', 0)} buildings)")
    print(f"  mean smoothing   {summary.get('mean_smoothing_delta_m', 0):.2f} m")
    print(f"  max  smoothing   {summary.get('max_smoothing_delta_m', 0):.2f} m")
    print(f"  mean score       {summary.get('mean_raw_score', 0):.1f}/100")
    for t in summary.get("per_track", []):
        print(f"\n  track #{t['track_id']}  ({t['frames']} frames)")
        print(f"    mean GPS     {t['mean_lat']:.6f}, {t['mean_lon']:.6f}")
        print(f"    lat spread   {t['lat_spread_m']:.2f} m")
        print(f"    lon spread   {t['lon_spread_m']:.2f} m")
        print(f"    mean score   {t['mean_raw_score']:.1f}/100")
        print(f"    gmaps        {t['gmaps']}")
    print(f"\n  summary → {summary_path}")
    print(f"{'='*56}")

    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame",      type=int,   default=None)
    ap.add_argument("--frames",     type=str,   default=None,
                    help="Comma-separated list, e.g. 716,717,840,3599")
    ap.add_argument("--range",      type=str,   default=None,
                    help="Frame range, e.g. 716-730")
    ap.add_argument("--step",       type=int,   default=1)
    ap.add_argument("--skip-sync",  action="store_true")
    args = ap.parse_args()

    os.makedirs(cfg.OUT_DIR, exist_ok=True)

    if args.frame is not None:
        if not args.skip_sync or not os.path.exists(cfg.MANIFEST_PATH):
            print("=== Phase 1: sync ===")
            sync.build_manifest()
        stabilizer = GPSStabilizer()
        run_single(args.frame, stabilizer, skip_sync=True)

    elif args.frames is not None:
        frames = [int(x.strip()) for x in args.frames.split(",")]
        run_batch(frames, skip_sync=args.skip_sync)

    elif args.range is not None:
        start, end = map(int, args.range.split("-"))
        frames = list(range(start, end + 1, args.step))
        run_batch(frames, skip_sync=args.skip_sync)

    else:
        print("Specify --frame N  or  --frames 716,717,840  or  --range 716-730")
        sys.exit(1)


if __name__ == "__main__":
    main()