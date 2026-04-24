import os
import json
import argparse
from collections import defaultdict
import cfg

def load_all_matches(start_frame, end_frame):
    clusters = defaultdict(list)

    for fid in range(start_frame, end_frame + 1):
        match_path = os.path.join(cfg.OUT_DIR, f"match_json/frame_{fid:06d}_match.json")
        if not os.path.exists(match_path):
            continue
        with open(match_path) as f:
            data = json.load(f)
        best = data.get("best_match")
        if not best:
            continue

        lat = best["centroid_lat"]
        lon = best["centroid_lon"]
        key = f"{lat:.5f}_{lon:.5f}"
        clusters[key].append((fid, best))

    return clusters

def build_summary(clusters):
    per_track = []
    track_id = 0

    for key, sightings in clusters.items():
        if not sightings:
            continue

        lats = [s[1]["centroid_lat"] for s in sightings]
        lons = [s[1]["centroid_lon"] for s in sightings]
        mean_lat = sum(lats) / len(lats)
        mean_lon = sum(lons) / len(lons)

        best_sighting = max(sightings, key=lambda x: x[1]["score"])
        best_frame_id, best_match = best_sighting

        frame_ids = [s[0] for s in sightings]
        scores = [s[1]["score"] for s in sightings]
        depths = [s[1].get("depth_m", None) for s in sightings if s[1].get("depth_m")]

        track = {
            "track_id": str(track_id),
            "mean_lat": mean_lat,
            "mean_lon": mean_lon,
            "frames": len(sightings),
            "frame_ids": frame_ids,
            "mean_raw_score": sum(scores) / len(scores),
            "best_frame_id": best_frame_id,
            "best_score": best_match["score"],
            "mean_depth_m": sum(depths) / len(depths) if depths else None,
            "raw_best_match": best_match
        }
        per_track.append(track)
        track_id += 1

    return {
        "summary": {
            "total_tracks": len(per_track),
            "frames_processed": len(clusters),
            "per_track": per_track
        }
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=cfg.FRAME_START)
    ap.add_argument("--end", type=int, default=cfg.FRAME_END)
    ap.add_argument("--out", default="unique_buildings_fullo.json")
    args = ap.parse_args()

    print("[summary] Loading match JSONs...")
    clusters = load_all_matches(args.start, args.end)
    print(f"[summary] Found {len(clusters)} unique building clusters.")

    summary = build_summary(clusters)
    out_path = os.path.join(cfg.OUT_DIR, "summary", args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"[summary] Saved to {out_path}")

if __name__ == "__main__":
    main()