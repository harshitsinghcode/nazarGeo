import os
import json
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
import cfg


def _unwrap(angles_deg):
    return np.rad2deg(np.unwrap(np.deg2rad(angles_deg)))


def build_manifest():
    os.makedirs(cfg.OUT_DIR, exist_ok=True)

    df = pd.read_csv(cfg.IMU_CSV_PATH, comment="#")
    df["t_unix"] = pd.to_numeric(df["t_unix"], errors="coerce")
    df = df.dropna(subset=["t_unix", "gnss_latitude", "gnss_longitude", "yaw_deg"])
    df = df.sort_values("t_unix").reset_index(drop=True)

    t0 = df["t_unix"].iloc[0]

    interp_lat = interp1d(df["t_unix"], df["gnss_latitude"],  fill_value="extrapolate")
    interp_lon = interp1d(df["t_unix"], df["gnss_longitude"], fill_value="extrapolate")
    interp_yaw = interp1d(df["t_unix"], _unwrap(df["yaw_deg"].to_numpy()), fill_value="extrapolate")

    records = []
    for fid in range(cfg.KITTI_START_FRAME, cfg.KITTI_END_FRAME + 1):
        t = t0 + fid / cfg.KITTI_FPS
        fstr = f"{fid:010d}"
        records.append({
            "frame_id": fid,
            "timestamp": float(t),
            "camera_data": {
                "lens": "lens1",
                "path": os.path.join(cfg.KITTI_DRIVE_DIR, "image_02", "data", f"{fstr}.png")
            },
            "lidar_data": {
                "path": os.path.join(cfg.KITTI_DRIVE_DIR, "velodyne_points", "data", f"{fstr}.bin")
            },
            "ego_pose": {
                "latitude":    float(interp_lat(t)),
                "longitude":   float(interp_lon(t)),
                "heading_deg": float(interp_yaw(t)) % 360.0
            }
        })

    with open(cfg.MANIFEST_PATH, "w") as f:
        json.dump(records, f, indent=2)

    print(f"[sync] wrote {len(records)} frames → {cfg.MANIFEST_PATH}")
    return cfg.MANIFEST_PATH


if __name__ == "__main__":
    build_manifest()