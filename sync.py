# import os
# import json
# import numpy as np
# import pandas as pd
# from scipy.interpolate import interp1d
# import cfg


# def _unwrap(angles_deg):
#     return np.rad2deg(np.unwrap(np.deg2rad(angles_deg)))


# def build_manifest():
#     os.makedirs(cfg.OUT_DIR, exist_ok=True)

#     df = pd.read_csv(cfg.IMU_CSV_PATH, comment="#")
#     df["t_unix"] = pd.to_numeric(df["t_unix"], errors="coerce")
#     df = df.dropna(subset=["t_unix", "gnss_latitude", "gnss_longitude", "yaw_deg"])
#     df = df.sort_values("t_unix").reset_index(drop=True)

#     t0 = df["t_unix"].iloc[0]

#     interp_lat = interp1d(df["t_unix"], df["gnss_latitude"],  fill_value="extrapolate")
#     interp_lon = interp1d(df["t_unix"], df["gnss_longitude"], fill_value="extrapolate")
#     interp_yaw = interp1d(df["t_unix"], _unwrap(df["yaw_deg"].to_numpy()), fill_value="extrapolate")

#     records = []
#     for fid in range(cfg.KITTI_START_FRAME, cfg.KITTI_END_FRAME + 1):
#         t = t0 + fid / cfg.KITTI_FPS
#         fstr = f"{fid:010d}"
#         records.append({
#             "frame_id": fid,
#             "timestamp": float(t),
#             "camera_data": {
#                 "lens": "lens1",
#                 "path": os.path.join(cfg.KITTI_DRIVE_DIR, "image_02", "data", f"{fstr}.png")
#             },
#             "lidar_data": {
#                 "path": os.path.join(cfg.KITTI_DRIVE_DIR, "velodyne_points", "data", f"{fstr}.bin")
#             },
#             "ego_pose": {
#                 "latitude":    float(interp_lat(t)),
#                 "longitude":   float(interp_lon(t)),
#                 "heading_deg": float(interp_yaw(t)) % 360.0
#             }
#         })

#     with open(cfg.MANIFEST_PATH, "w") as f:
#         json.dump(records, f, indent=2)

#     print(f"[sync] wrote {len(records)} frames → {cfg.MANIFEST_PATH}")
#     return cfg.MANIFEST_PATH


# if __name__ == "__main__":
#     build_manifest()


#--------------------------

# import os
# import json
# import numpy as np
# import pandas as pd
# from scipy.interpolate import interp1d
# import cfg


# def _unwrap(angles_deg):
#     return np.rad2deg(np.unwrap(np.deg2rad(angles_deg)))


# def _frame_path(frame_id):
#     return os.path.join(cfg.LENS1_DIR, f"frame_{frame_id:06d}.jpg")


# def build_manifest():
#     os.makedirs(cfg.OUT_DIR, exist_ok=True)

#     df = pd.read_csv(cfg.IMU_CSV_PATH, comment="#")
#     df["t_unix"] = pd.to_numeric(df["t_unix"], errors="coerce")

#     for col in ["filter_lla_lat", "filter_lla_lon", "yaw_deg"]:
#         df[col] = pd.to_numeric(df[col], errors="coerce")

#     df = df.dropna(subset=["t_unix", "filter_lla_lat", "filter_lla_lon", "yaw_deg"])
#     df = df.sort_values("t_unix").reset_index(drop=True)

#     t0 = df["t_unix"].iloc[0]

#     interp_lat = interp1d(df["t_unix"], df["filter_lla_lat"],  fill_value="extrapolate")
#     interp_lon = interp1d(df["t_unix"], df["filter_lla_lon"], fill_value="extrapolate")
#     interp_yaw = interp1d(df["t_unix"], _unwrap(df["yaw_deg"].to_numpy()), fill_value="extrapolate")

#     records = []
#     for fid in range(cfg.FRAME_START, cfg.FRAME_END + 1):
#         t = t0 + (fid - cfg.FRAME_START) / cfg.CAMERA_FPS

#         img_path = _frame_path(fid)

#         records.append({
#             "frame_id":    fid,
#             "timestamp":   float(t),
#             "camera_data": {
#                 "lens": "lens1",
#                 "path": img_path
#             },
#             "lidar_data": {
#                 "l1": cfg.L1_PCAP_PATH,
#                 "l2": cfg.L2_PCAP_PATH
#             },
#             "ego_pose": {
#                 "latitude":    float(interp_lat(t)),
#                 "longitude":   float(interp_lon(t)),
#                 "heading_deg": float(interp_yaw(t)) % 360.0
#             }
#         })

#     with open(cfg.MANIFEST_PATH, "w") as f:
#         json.dump(records, f, indent=2)

#     print(f"[sync] wrote {len(records)} frames → {cfg.MANIFEST_PATH}")
#     return cfg.MANIFEST_PATH


# if __name__ == "__main__":
#     build_manifest()

#---------------------------------------------------------

import os
import json
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
import cfg

def _unwrap(angles_deg):
    return np.rad2deg(np.unwrap(np.deg2rad(angles_deg)))

def _frame_path(frame_id):
    # This formats '1' into 'frame_000001.jpg' exactly like your screenshot
    return os.path.join(cfg.LENS1_DIR, f"frame_{frame_id:06d}.jpg")

def build_manifest():
    os.makedirs(cfg.OUT_DIR, exist_ok=True)

    # Load sliced CSV, strictly using commas and ignoring comments
    df = pd.read_csv(cfg.IMU_CSV_PATH, comment="#")
    df.columns = df.columns.str.strip()
    df["t_unix"] = pd.to_numeric(df["t_unix"], errors="coerce")

    for col in ["filter_lla_lat", "filter_lla_lon", "yaw_deg"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["t_unix", "filter_lla_lat", "filter_lla_lon", "yaw_deg"])
    df = df.sort_values("t_unix").reset_index(drop=True)

    # t0 is automatically locked to the very first row of your 460s sliced CSV
    t0 = df["t_unix"].iloc[0]

    interp_lat = interp1d(df["t_unix"], df["filter_lla_lat"],  fill_value="extrapolate")
    interp_lon = interp1d(df["t_unix"], df["filter_lla_lon"], fill_value="extrapolate")
    interp_yaw = interp1d(df["t_unix"], _unwrap(df["yaw_deg"].to_numpy()), fill_value="extrapolate")

    records = []
    for fid in range(cfg.FRAME_START, cfg.FRAME_END + 1):
        # Frame 1 = t0. Frame 840 = t0 + 27.9 seconds.
        t = t0 + (fid - cfg.FRAME_START) / cfg.CAMERA_FPS

        img_path = _frame_path(fid)

        records.append({
            "frame_id":    fid,
            "timestamp":   float(t),
            "camera_data": {
                "lens": "lens1",
                "path": img_path
            },
            "lidar_data": {
                "l1": cfg.L1_PCAP_PATH,
                "l2": cfg.L2_PCAP_PATH
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