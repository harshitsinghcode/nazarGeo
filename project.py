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

    perceive_path = os.path.join(
        cfg.OUT_DIR, f"perceive_json/frame_{frame_id:06d}_perceive.json"
    )
    if not os.path.exists(perceive_path):
        raise FileNotFoundError(f"Perceive output missing: {perceive_path}")

    with open(perceive_path) as f:
        perceive = json.load(f)

    pose    = entry["ego_pose"]
    ego_lat = pose["latitude"]
    ego_lon = pose["longitude"]
    heading = pose["heading_deg"]
    depth   = perceive["median_depth"]

    raw_target = geodesic(meters=depth).destination((ego_lat, ego_lon), heading)
    target_lat = raw_target.latitude  + cfg.PROJECTION_LAT_OFFSET
    target_lon = raw_target.longitude + cfg.PROJECTION_LON_OFFSET

    out = {
        "frame_id":    frame_id,
        "ego_lat":     ego_lat,
        "ego_lon":     ego_lon,
        "heading_deg": heading,
        "depth_m":     depth,

        "raw_target_lat": raw_target.latitude,
        "raw_target_lon": raw_target.longitude,

        "target_lat":  target_lat,
        "target_lon":  target_lon,

        "gmaps": (
            f"https://www.google.com/maps/search/?api=1"
            f"&query={target_lat:.8f},{target_lon:.8f}"
        ),
    }

    out_path = os.path.join(
        cfg.OUT_DIR, f"project_json/frame_{frame_id:06d}_project.json"
    )
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    print(
        f"[project] frame={frame_id}  depth={depth:.1f}m  heading={heading:.1f}°"
        f"  target=({target_lat:.6f}, {target_lon:.6f})"
        + (f"  [offset applied: Δlat={cfg.PROJECTION_LAT_OFFSET:+.6f} "
           f"Δlon={cfg.PROJECTION_LON_OFFSET:+.6f}]"
           if cfg.PROJECTION_LAT_OFFSET != 0 or cfg.PROJECTION_LON_OFFSET != 0
           else "")
        + f"  → {out_path}"
    )
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", type=int, default=840)
    args = ap.parse_args()
    run_frame(args.frame)