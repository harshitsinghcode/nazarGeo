# import os
# import re
# import json
# import argparse
# import numpy as np
# import cv2
# from ultralytics import YOLO, SAM
# import cfg

# FALLBACK_CLASSES = [
#     "building", "house", "commercial building", "brick wall", "facade",
#     "wall", "structure", "apartment", "office building", "storefront",
#     "architecture", "construction"
# ]
# FALLBACK_CONF = 0.05


# def _read_calib(path):
#     data = {}
#     with open(path) as f:
#         for line in f:
#             line = line.strip()
#             if not line or ":" not in line:
#                 continue
#             key, val = line.split(":", 1)
#             key, val = key.strip(), val.strip()
#             if val and val[0].isalpha():
#                 continue
#             nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", val)
#             if nums:
#                 data[key] = np.array([float(x) for x in nums])
#     return data


# def _get_mat(d, keys, shape):
#     for k in keys:
#         if k in d and d[k].size == np.prod(shape):
#             return d[k].reshape(shape)
#     raise KeyError(f"None of {keys} found in calibration. Available: {list(d.keys())}")


# class Projector:
#     def __init__(self, calib_dir):
#         cam = _read_calib(os.path.join(calib_dir, "calib_cam_to_cam.txt"))
#         vel = _read_calib(os.path.join(calib_dir, "calib_velo_to_cam.txt"))

#         P2 = _get_mat(cam, ["P_rect_02", "P_rect_2", "P2"], (3, 4))
#         R0 = _get_mat(cam, ["R_rect_00", "R_rect_0", "R0_rect"], (3, 3))
#         R  = _get_mat(vel, ["R"], (3, 3))
#         T  = _get_mat(vel, ["T"], (3, 1))

#         Tr = np.eye(4)
#         Tr[:3, :] = np.hstack((R, T))

#         R0_4 = np.eye(4)
#         R0_4[:3, :3] = R0

#         self._full = P2 @ R0_4 @ Tr

#     def project(self, pts, img_shape):
#         xyz1 = np.hstack((pts[:, :3], np.ones((len(pts), 1))))
#         proj = (self._full @ xyz1.T).T
#         d = proj[:, 2]
#         u = proj[:, 0] / d
#         v = proj[:, 1] / d
#         h, w = img_shape[:2]
#         mask = (d > 0) & (u >= 0) & (u < w) & (v >= 0) & (v < h)
#         return u[mask], v[mask], d[mask]


# def _detect(yolo, img, classes, conf):
#     yolo.set_classes(classes)
#     results = yolo(img, conf=conf, iou=cfg.YOLO_IOU, verbose=False)
#     boxes     = results[0].boxes.xyxy.cpu().numpy()
#     class_ids = results[0].boxes.cls.cpu().numpy()
#     return boxes, class_ids


# def _process_detections(frame_id, entry, img, boxes, class_ids, active_classes):
#     img_path   = entry["camera_data"]["path"]
#     lidar_path = entry["lidar_data"]["path"]

#     sam = SAM(cfg.SAM_MODEL)
#     sam_res = sam(img_path, bboxes=boxes, verbose=False)
#     masks = sam_res[0].masks.data.cpu().numpy()

#     master = np.any(masks, axis=0)
#     master = cv2.resize(master.astype(np.uint8), (img.shape[1], img.shape[0])) > 0

#     proj = Projector(cfg.KITTI_CALIB_DIR)
#     pts  = np.fromfile(lidar_path, dtype=np.float32).reshape(-1, 4)
#     u, v, depths = proj.project(pts, img.shape)

#     inside_depths = [depths[i] for i in range(len(u)) if master[int(v[i]), int(u[i])]]

#     if not inside_depths:
#         print(f"[perceive] frame {frame_id}: detections found but no LiDAR points inside mask")
#         return None

#     median_depth = float(np.median(inside_depths))

#     largest_box = boxes[int(np.argmax(
#         [(b[2]-b[0]) * (b[3]-b[1]) for b in boxes]
#     ))]
#     bbox_px = [float(x) for x in largest_box]
#     img_w   = img.shape[1]

#     vis = img.copy()
#     for i, box in enumerate(boxes):
#         x1, y1, x2, y2 = map(int, box)
#         cid = int(class_ids[i])
#         label = active_classes[cid] if cid < len(active_classes) else "building"
#         cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 0, 0), 2)
#         cv2.putText(vis, label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)

#     vis[master] = (vis[master] * 0.5 + np.array([0, 255, 0]) * 0.5).astype(np.uint8)

#     for i in range(len(u)):
#         if master[int(v[i]), int(u[i])]:
#             cv2.circle(vis, (int(u[i]), int(v[i])), 2, (0, 0, 255), -1)

#     cv2.putText(vis, f"depth: {median_depth:.2f}m", (30, 40),
#                 cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

#     vis_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:04d}_vis.jpg")
#     cv2.imwrite(vis_path, vis)

#     out = {
#         "frame_id":     frame_id,
#         "median_depth": median_depth,
#         "bbox_px":      bbox_px,
#         "img_w":        img_w,
#         "vis":          vis_path
#     }
#     out_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:04d}_perceive.json")
#     with open(out_path, "w") as f:
#         json.dump(out, f, indent=2)

#     print(f"[perceive] frame {frame_id}: depth={median_depth:.2f}m  detections={len(boxes)} → {out_path}")
#     return out


# def run_frame(frame_id):
#     with open(cfg.MANIFEST_PATH) as f:
#         manifest = json.load(f)

#     entry = next((r for r in manifest if r["frame_id"] == frame_id), None)
#     if entry is None:
#         raise ValueError(f"Frame {frame_id} not in manifest")

#     img_path = entry["camera_data"]["path"]
#     print(f"[perceive] loading image: {img_path}")

#     img = cv2.imread(img_path)
#     if img is None:
#         raise FileNotFoundError(f"Image not found: {img_path}")

#     raw_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:04d}_raw.jpg")
#     cv2.imwrite(raw_path, img)
#     print(f"[perceive] raw frame saved → {raw_path}")

#     yolo = YOLO(cfg.YOLO_MODEL)

#     print(f"[perceive] pass 1 — primary classes @ conf={cfg.YOLO_CONF}")
#     boxes, class_ids = _detect(yolo, img, cfg.YOLO_CLASSES, cfg.YOLO_CONF)

#     if len(boxes) == 0:
#         print(f"[perceive] pass 1 found nothing — pass 2: fallback classes @ conf={FALLBACK_CONF}")
#         boxes, class_ids = _detect(yolo, img, FALLBACK_CLASSES, FALLBACK_CONF)
#         active_classes = FALLBACK_CLASSES
#     else:
#         active_classes = cfg.YOLO_CLASSES

#     if len(boxes) == 0:
#         print(f"[perceive] frame {frame_id}: both passes found no detections")
#         print(f"[perceive] check raw frame at: {raw_path}")
#         return None

#     print(f"[perceive] {len(boxes)} detection(s) — passing to SAM")
#     return _process_detections(frame_id, entry, img, boxes, class_ids, active_classes)


# def scan_for_detections(start=0, end=20):
#     with open(cfg.MANIFEST_PATH) as f:
#         manifest = json.load(f)

#     yolo = YOLO(cfg.YOLO_MODEL)

#     print(f"[perceive] scanning frames {start}–{end} for first usable detection...")
#     for fid in range(start, end + 1):
#         entry = next((r for r in manifest if r["frame_id"] == fid), None)
#         if entry is None:
#             continue
#         img = cv2.imread(entry["camera_data"]["path"])
#         if img is None:
#             continue

#         boxes, _ = _detect(yolo, img, cfg.YOLO_CLASSES, cfg.YOLO_CONF)
#         if len(boxes) == 0:
#             boxes, _ = _detect(yolo, img, FALLBACK_CLASSES, FALLBACK_CONF)

#         status = f"{len(boxes)} det" if len(boxes) > 0 else "none"
#         print(f"  frame {fid:03d}: {status}")

#     print("[perceive] scan complete — re-run with the best frame using --frame N")


# if __name__ == "__main__":
#     ap = argparse.ArgumentParser()
#     ap.add_argument("--frame", type=int, default=5)
#     ap.add_argument("--scan", action="store_true", help="Scan frames 0-20 and report detection counts")
#     ap.add_argument("--scan-end", type=int, default=20)
#     args = ap.parse_args()

#     if args.scan:
#         scan_for_detections(0, args.scan_end)
#     else:
#         run_frame(args.frame)

#---------------------------------------------

import os
import json
import argparse
import numpy as np
import cv2
from ultralytics import YOLO, SAM
import cfg
import lidar_pcap


class ApproxProjector:
    def __init__(self):
        # ---------------------------------------------------------
        # SENSOR ALIGNMENT DIAL (TUNE THIS!)
        # ---------------------------------------------------------
        # Twist the LiDAR point cloud horizontally to align with the camera lens.
        # Common mounting angles are 0.0, 90.0, -90.0, or 180.0
        self.YAW_ADJUST_DEG = 90.0 
        # ---------------------------------------------------------
        
        self._K = np.array([
            [cfg.FX,     0,  cfg.CX],
            [0,      cfg.FY,  cfg.CY],
            [0,          0,       1]
        ], dtype=np.float64)

    def project(self, pts, img_shape):
        # 1. Read Raw LiDAR (X=Right, Y=Forward, Z=Up)
        x_lidar = pts[:, 0].astype(np.float64)
        y_lidar = pts[:, 1].astype(np.float64)
        z_lidar = pts[:, 2].astype(np.float64)

        # 2. Spin the cloud to match physical mounting
        import math
        theta = math.radians(self.YAW_ADJUST_DEG)
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        
        x_spun = x_lidar * cos_t - y_lidar * sin_t
        y_spun = x_lidar * sin_t + y_lidar * cos_t
        z_spun = z_lidar

        # 3. Convert to OpenCV Camera System
        cam_z = y_spun   # LiDAR Forward -> Camera Depth
        cam_x = x_spun   # LiDAR Right -> Camera Right
        cam_y = -z_spun  # LiDAR Up -> Camera Down (Negative)

        cam_x += cfg.LIDAR_TO_CAM_X_OFFSET
        cam_y += cfg.LIDAR_TO_CAM_Y_OFFSET
        cam_z += cfg.LIDAR_TO_CAM_Z_OFFSET

        # 4. Cull points BEHIND the camera
        mask_front = cam_z > 0.5
        x, y, z = cam_x[mask_front], cam_y[mask_front], cam_z[mask_front]

        # 5. Project onto 2D image
        u = (cfg.FX * x / z + cfg.CX)
        v = (cfg.FY * y / z + cfg.CY)
        d = z

        h, w = img_shape[:2]
        mask_bounds = (u >= 0) & (u < w) & (v >= 0) & (v < h)
        return u[mask_bounds], v[mask_bounds], d[mask_bounds]

def _detect(yolo, img, classes, conf):
    yolo.set_classes(classes)
    results = yolo(img, conf=conf, iou=cfg.YOLO_IOU, verbose=False)
    boxes     = results[0].boxes.xyxy.cpu().numpy()
    class_ids = results[0].boxes.cls.cpu().numpy()
    return boxes, class_ids


def run_frame(frame_id):
    with open(cfg.MANIFEST_PATH) as f:
        manifest = json.load(f)

    entry = next((r for r in manifest if r["frame_id"] == frame_id), None)
    if entry is None:
        raise ValueError(f"Frame {frame_id} not in manifest")

    img_path = entry["camera_data"]["path"]
    print(f"[perceive] loading: {img_path}")

    img = cv2.imread(img_path)
    if img is None:
        raise FileNotFoundError(f"Image not found: {img_path}")

    raw_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:06d}_raw.jpg")
    cv2.imwrite(raw_path, img)
    print(f"[perceive] raw saved → {raw_path}")

    yolo = YOLO(cfg.YOLO_MODEL)

    print(f"[perceive] pass 1 — primary @ conf={cfg.YOLO_CONF}")
    boxes, class_ids = _detect(yolo, img, cfg.YOLO_CLASSES, cfg.YOLO_CONF)

    if len(boxes) == 0:
        print(f"[perceive] pass 2 — fallback @ conf={cfg.FALLBACK_CONF}")
        boxes, class_ids = _detect(yolo, img, cfg.FALLBACK_CLASSES, cfg.FALLBACK_CONF)
        active_classes = cfg.FALLBACK_CLASSES
    else:
        active_classes = cfg.YOLO_CLASSES

    if len(boxes) == 0:
        print(f"[perceive] no detections — check raw: {raw_path}")
        return None

    print(f"[perceive] {len(boxes)} detection(s) → SAM")

    sam = SAM(cfg.SAM_MODEL)
    sam_res = sam(img_path, bboxes=boxes, verbose=False)
    masks = sam_res[0].masks.data.cpu().numpy()

    master = np.any(masks, axis=0)
    master = cv2.resize(master.astype(np.uint8), (img.shape[1], img.shape[0])) > 0

    print(f"[perceive] loading PCAP...")
    pts = lidar_pcap.load_both(entry["lidar_data"]["l1"], entry["lidar_data"]["l2"])
    print(f"[perceive] {len(pts):,} LiDAR points loaded")

    proj = ApproxProjector()
    u, v, depths = proj.project(pts, img.shape)
    print(f"[perceive] {len(u):,} points projected into frame")

    inside_depths = [depths[i] for i in range(len(u)) if master[int(v[i]), int(u[i])]]

    if not inside_depths:
        print("[perceive] no LiDAR points inside mask")
        return None

    median_depth = float(np.median(inside_depths))

    largest_box = boxes[int(np.argmax(
        [(b[2]-b[0]) * (b[3]-b[1]) for b in boxes]
    ))]
    bbox_px = [float(x) for x in largest_box]

    vis = img.copy()
    for i, box in enumerate(boxes):
        x1, y1, x2, y2 = map(int, box)
        cid = int(class_ids[i])
        label = active_classes[cid] if cid < len(active_classes) else "building"
        cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 0, 0), 2)
        cv2.putText(vis, label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)

    vis[master] = (vis[master] * 0.5 + np.array([0, 255, 0]) * 0.5).astype(np.uint8)

    for i in range(len(u)):
        if master[int(v[i]), int(u[i])]:
            cv2.circle(vis, (int(u[i]), int(v[i])), 2, (0, 0, 255), -1)

    cv2.putText(vis, f"depth: {median_depth:.2f}m", (30, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)

    vis_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:06d}_vis.jpg")
    cv2.imwrite(vis_path, vis)

    out = {
        "frame_id":     frame_id,
        "median_depth": median_depth,
        "bbox_px":      bbox_px,
        "img_w":        img.shape[1],
        "vis":          vis_path
    }
    out_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:06d}_perceive.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    print(f"[perceive] depth={median_depth:.2f}m → {out_path}")
    return out


def scan_frames(start, end):
    with open(cfg.MANIFEST_PATH) as f:
        manifest = json.load(f)

    yolo = YOLO(cfg.YOLO_MODEL)
    print(f"[perceive] scanning frames {start}–{end}...")

    for fid in range(start, end + 1):
        entry = next((r for r in manifest if r["frame_id"] == fid), None)
        if entry is None:
            continue
        img = cv2.imread(entry["camera_data"]["path"])
        if img is None:
            print(f"  frame {fid:06d}: image missing")
            continue

        boxes, _ = _detect(yolo, img, cfg.YOLO_CLASSES, cfg.YOLO_CONF)
        if len(boxes) == 0:
            boxes, _ = _detect(yolo, img, cfg.FALLBACK_CLASSES, cfg.FALLBACK_CONF)

        print(f"  frame {fid:06d}: {len(boxes)} det")

    print("[perceive] scan done")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", type=int, default=840)
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--scan-start", type=int, default=740)
    ap.add_argument("--scan-end",   type=int, default=760)
    args = ap.parse_args()

    if args.scan:
        scan_frames(args.scan_start, args.scan_end)
    else:
        run_frame(args.frame)

# import os
# import json
# import math
# import argparse
# import numpy as np
# import cv2
# from ultralytics import YOLO, SAM
# import cfg
# import lidar_pcap


# class FisheyeProjector:
#     def __init__(self):
#         self._K = np.array([
#             [cfg.FX,    0, cfg.CX],
#             [0,    cfg.FY, cfg.CY],
#             [0,        0,      1]
#         ], dtype=np.float64)

#     def project(self, pts, img_shape):
#         theta = math.radians(cfg.LIDAR_YAW_DEG)
#         cos_t, sin_t = math.cos(theta), math.sin(theta)

#         x_raw = pts[:, 0].astype(np.float64)
#         y_raw = pts[:, 1].astype(np.float64)
#         z_raw = pts[:, 2].astype(np.float64)

#         x_rot = x_raw * cos_t - y_raw * sin_t
#         y_rot = x_raw * sin_t + y_raw * cos_t
#         z_rot = z_raw

#         cam_z = y_rot
#         cam_x = x_rot
#         cam_y = -z_rot

#         cam_x += cfg.LIDAR_TO_CAM_X_OFFSET
#         cam_y += cfg.LIDAR_TO_CAM_Y_OFFSET
#         cam_z += cfg.LIDAR_TO_CAM_Z_OFFSET

#         front = cam_z > 0.5
#         cx, cy, cz = cam_x[front], cam_y[front], cam_z[front]

#         r_angle = np.arctan(np.sqrt(cx**2 + cy**2) / cz)

#         k1, k2, k3, k4 = cfg.FISHEYE_K1, cfg.FISHEYE_K2, cfg.FISHEYE_K3, cfg.FISHEYE_K4
#         r_d = r_angle * (1 + k1*r_angle**2 + k2*r_angle**4 + k3*r_angle**6 + k4*r_angle**8)

#         norm = np.sqrt(cx**2 + cy**2)
#         safe = norm > 1e-9
#         phi_x = np.where(safe, cx / norm, 0.0)
#         phi_y = np.where(safe, cy / norm, 0.0)

#         u = cfg.FX * r_d * phi_x + cfg.CX
#         v = cfg.FY * r_d * phi_y + cfg.CY
#         d = cz

#         h, w = img_shape[:2]
#         in_bounds = (u >= 0) & (u < w) & (v >= 0) & (v < h)
#         return u[in_bounds], v[in_bounds], d[in_bounds]


# def _detect(yolo, img, classes, conf):
#     yolo.set_classes(classes)
#     results = yolo(img, conf=conf, iou=cfg.YOLO_IOU, verbose=False)
#     boxes     = results[0].boxes.xyxy.cpu().numpy()
#     class_ids = results[0].boxes.cls.cpu().numpy()
#     return boxes, class_ids


# def _filter_boxes_by_side(boxes, class_ids, img_w, side):
#     if side == "right":
#         keep = [i for i, b in enumerate(boxes) if (b[0] + b[2]) / 2 > img_w * 0.5]
#     elif side == "left":
#         keep = [i for i, b in enumerate(boxes) if (b[0] + b[2]) / 2 < img_w * 0.5]
#     else:
#         keep = list(range(len(boxes)))
#     if not keep:
#         return boxes, class_ids
#     return boxes[keep], class_ids[keep]


# def run_frame(frame_id):
#     with open(cfg.MANIFEST_PATH) as f:
#         manifest = json.load(f)

#     entry = next((r for r in manifest if r["frame_id"] == frame_id), None)
#     if entry is None:
#         raise ValueError(f"Frame {frame_id} not in manifest")

#     img_path = entry["camera_data"]["path"]
#     print(f"[perceive] loading: {img_path}")

#     img = cv2.imread(img_path)
#     if img is None:
#         raise FileNotFoundError(f"Image not found: {img_path}")

#     raw_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:06d}_raw.jpg")
#     cv2.imwrite(raw_path, img)

#     yolo = YOLO(cfg.YOLO_MODEL)

#     print(f"[perceive] pass 1 @ conf={cfg.YOLO_CONF}")
#     boxes, class_ids = _detect(yolo, img, cfg.YOLO_CLASSES, cfg.YOLO_CONF)
#     if len(boxes) == 0:
#         print(f"[perceive] pass 2 @ conf={cfg.FALLBACK_CONF}")
#         boxes, class_ids = _detect(yolo, img, cfg.FALLBACK_CLASSES, cfg.FALLBACK_CONF)
#         active_classes = cfg.FALLBACK_CLASSES
#     else:
#         active_classes = cfg.YOLO_CLASSES

#     if len(boxes) == 0:
#         print(f"[perceive] no detections — check raw: {raw_path}")
#         return None

#     boxes, class_ids = _filter_boxes_by_side(boxes, class_ids, img.shape[1], cfg.IMAGE_BUILDING_SIDE)
#     print(f"[perceive] {len(boxes)} box(es) after '{cfg.IMAGE_BUILDING_SIDE}' filter → SAM")

#     if len(boxes) == 0:
#         print("[perceive] all boxes filtered — change IMAGE_BUILDING_SIDE in cfg.py to 'left' or 'any'")
#         return None

#     sam = SAM(cfg.SAM_MODEL)
#     sam_res = sam(img_path, bboxes=boxes, verbose=False)
#     masks = sam_res[0].masks.data.cpu().numpy()

#     master = np.any(masks, axis=0)
#     master = cv2.resize(master.astype(np.uint8), (img.shape[1], img.shape[0])) > 0

#     print(f"[perceive] loading PCAP...")
#     pts = lidar_pcap.load_both(entry["lidar_data"]["l1"], entry["lidar_data"]["l2"])
#     print(f"[perceive] {len(pts):,} raw LiDAR points")

#     proj = FisheyeProjector()
#     u, v, depths = proj.project(pts, img.shape)
#     print(f"[perceive] {len(u):,} projected into frame")

#     inside_depths = [depths[i] for i in range(len(u)) if master[int(v[i]), int(u[i])]]

#     if not inside_depths:
#         print(f"[perceive] 0 points inside mask (projected={len(u)}, mask_px={master.sum()})")
#         print("[perceive] try adjusting LIDAR_YAW_DEG in cfg.py (try 0, 90, -90, 180)")
#         return None

#     median_depth = float(np.median(inside_depths))

#     largest_box = boxes[int(np.argmax([(b[2]-b[0])*(b[3]-b[1]) for b in boxes]))]
#     bbox_px = [float(x) for x in largest_box]

#     vis = img.copy()
#     for i in range(0, len(u), 4):
#         cv2.circle(vis, (int(u[i]), int(v[i])), 1, (80, 80, 200), -1)

#     vis[master] = (vis[master] * 0.5 + np.array([0, 255, 0]) * 0.5).astype(np.uint8)

#     for i in range(len(u)):
#         if master[int(v[i]), int(u[i])]:
#             cv2.circle(vis, (int(u[i]), int(v[i])), 2, (0, 0, 255), -1)

#     for i, box in enumerate(boxes):
#         x1, y1, x2, y2 = map(int, box)
#         cid = int(class_ids[i])
#         label = active_classes[cid] if cid < len(active_classes) else "building"
#         cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 0, 0), 2)
#         cv2.putText(vis, label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)

#     cv2.putText(vis, f"depth: {median_depth:.2f}m", (30, 50),
#                 cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)

#     vis_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:06d}_vis.jpg")
#     cv2.imwrite(vis_path, vis)

#     out = {
#         "frame_id":     frame_id,
#         "median_depth": median_depth,
#         "bbox_px":      bbox_px,
#         "img_w":        img.shape[1],
#         "vis":          vis_path
#     }
#     out_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:06d}_perceive.json")
#     with open(out_path, "w") as f:
#         json.dump(out, f, indent=2)

#     print(f"[perceive] depth={median_depth:.2f}m → {out_path}")
#     return out


# def scan_frames(start, end):
#     with open(cfg.MANIFEST_PATH) as f:
#         manifest = json.load(f)
#     yolo = YOLO(cfg.YOLO_MODEL)
#     print(f"[perceive] scanning {start}–{end}...")
#     for fid in range(start, end + 1):
#         entry = next((r for r in manifest if r["frame_id"] == fid), None)
#         if entry is None:
#             continue
#         img = cv2.imread(entry["camera_data"]["path"])
#         if img is None:
#             print(f"  {fid:06d}: missing")
#             continue
#         boxes, cids = _detect(yolo, img, cfg.YOLO_CLASSES, cfg.YOLO_CONF)
#         if len(boxes) == 0:
#             boxes, cids = _detect(yolo, img, cfg.FALLBACK_CLASSES, cfg.FALLBACK_CONF)
#         rb, _ = _filter_boxes_by_side(boxes, cids, img.shape[1], "right")
#         lb, _ = _filter_boxes_by_side(boxes, cids, img.shape[1], "left")
#         print(f"  {fid:06d}: total={len(boxes)} right={len(rb)} left={len(lb)}")
#     print("[perceive] scan done")


# if __name__ == "__main__":
#     ap = argparse.ArgumentParser()
#     ap.add_argument("--frame", type=int, default=840)
#     ap.add_argument("--scan", action="store_true")
#     ap.add_argument("--scan-start", type=int, default=740)
#     ap.add_argument("--scan-end",   type=int, default=760)
#     args = ap.parse_args()
#     if args.scan:
#         scan_frames(args.scan_start, args.scan_end)
#     else:
#         run_frame(args.frame)