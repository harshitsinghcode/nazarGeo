import os
import json
import argparse
from geopy.distance import geodesic
import cfg


def run_frame(frame_id):
    with open(cfg.MANIFEST_PATH) as f:
        manifest = json.load(f)

    entry = next((r for r in manifest if r["frame_id"] == frame_id), None)
    if entry is None:
        raise ValueError(f"Frame {frame_id} not in manifest")

    perceive_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:04d}_perceive.json")
    if not os.path.exists(perceive_path):
        raise FileNotFoundError(f"Perceive output missing: {perceive_path}")

    with open(perceive_path) as f:
        perceive = json.load(f)

    pose    = entry["ego_pose"]
    ego_lat = pose["latitude"]
    ego_lon = pose["longitude"]
    heading = pose["heading_deg"]
    depth   = perceive["median_depth"]

    target = geodesic(meters=depth).destination((ego_lat, ego_lon), heading)

    out = {
        "frame_id":      frame_id,
        "ego_lat":       ego_lat,
        "ego_lon":       ego_lon,
        "heading_deg":   heading,
        "depth_m":       depth,
        "target_lat":    target.latitude,
        "target_lon":    target.longitude,
        "gmaps":         f"https://www.google.com/maps/search/?api=1&query={target.latitude},{target.longitude}"
    }

    out_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:04d}_project.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    print(f"[project] frame {frame_id}: target=({target.latitude:.6f}, {target.longitude:.6f}) → {out_path}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", type=int, default=5)
    args = ap.parse_args()
    run_frame(args.frame)