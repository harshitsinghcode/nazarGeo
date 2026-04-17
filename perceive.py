# import os
# import json
# import argparse
# import numpy as np
# import cv2
# import math
# from ultralytics import YOLO, SAM
# import cfg
# import lidar_pcap


# class CalibratedProjector:
#     def __init__(self):
#         # Camera Intrinsics
#         self._K = np.array([
#             [cfg.FX,     0,  cfg.CX],
#             [0,      cfg.FY,  cfg.CY],
#             [0,          0,       1]
#         ], dtype=np.float64)

#         # =========================================================
#         # PERFECT CALIBRATION: LiDAR to Camera Extrinsic Matrix
#         # Automatically rotates and translates the point cloud!
#         # =========================================================
#         self._Tr = np.array([
#             [ 0.2092700, -0.9776630, -0.0195126,  2.054160 ],
#             [ 0.0386136,  0.0282009, -0.9988560,  0.401883 ],
#             [ 0.9770950,  0.2082770,  0.0436527, -0.035744 ],
#             [ 0.0000000,  0.0000000,  0.0000000,  1.000000 ]
#         ], dtype=np.float64)

#     def project(self, pts, img_shape):
#         # 1. Grab raw LiDAR X, Y, Z
#         xyz = pts[:, :3].astype(np.float64)
        
#         # 2. Add '1' to make them 4D homogeneous coordinates [X, Y, Z, 1]
#         ones = np.ones((len(xyz), 1), dtype=np.float64)
#         xyz1 = np.hstack([xyz, ones])
        
#         # 3. Apply the True Calibration Matrix!
#         cam_xyz = (self._Tr @ xyz1.T).T
        
#         x, y, z = cam_xyz[:, 0], cam_xyz[:, 1], cam_xyz[:, 2]

#         # 4. Cull points BEHIND the camera
#         mask_front = z > 0.5
#         x, y, z = x[mask_front], y[mask_front], z[mask_front]

#         # 5. Apply Intrinsic Camera Lens Projection
#         u = (cfg.FX * x / z + cfg.CX)
#         v = (cfg.FY * y / z + cfg.CY)
#         d = z

#         h, w = img_shape[:2]
#         mask_bounds = (u >= 0) & (u < w) & (v >= 0) & (v < h)
#         return u[mask_bounds], v[mask_bounds], d[mask_bounds]


# def _detect(yolo, img, classes, conf):
#     yolo.set_classes(classes)
#     results = yolo(img, conf=conf, iou=cfg.YOLO_IOU, verbose=False)
#     boxes     = results[0].boxes.xyxy.cpu().numpy()
#     class_ids = results[0].boxes.cls.cpu().numpy()
#     return boxes, class_ids


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
#     print(f"[perceive] raw saved → {raw_path}")

#     yolo = YOLO(cfg.YOLO_MODEL)

#     print(f"[perceive] pass 1 — primary @ conf={cfg.YOLO_CONF}")
#     boxes, class_ids = _detect(yolo, img, cfg.YOLO_CLASSES, cfg.YOLO_CONF)

#     if len(boxes) == 0:
#         # NOW USING CFG.PY DYNAMICALLY!
#         print(f"[perceive] pass 2 — fallback @ conf={cfg.FALLBACK_CONF}")
#         boxes, class_ids = _detect(yolo, img, cfg.FALLBACK_CLASSES, cfg.FALLBACK_CONF)
#         active_classes = cfg.FALLBACK_CLASSES
#     else:
#         active_classes = cfg.YOLO_CLASSES

#     if len(boxes) == 0:
#         print(f"[perceive] no detections — check raw: {raw_path}")
#         return None

#     # --- THE SAM FIX: ONLY SEGMENT THE LARGEST BUILDING ---
#     largest_idx = int(np.argmax([(b[2]-b[0]) * (b[3]-b[1]) for b in boxes]))
#     target_box = boxes[largest_idx:largest_idx+1]  
#     target_class = class_ids[largest_idx]
    
#     print(f"[perceive] {len(boxes)} detections found. Locking SAM onto the primary target...")

#     sam = SAM(cfg.SAM_MODEL)
#     sam_res = sam(img_path, bboxes=target_box, verbose=False)
#     masks = sam_res[0].masks.data.cpu().numpy()

#     master = np.any(masks, axis=0)
#     master = cv2.resize(master.astype(np.uint8), (img.shape[1], img.shape[0])) > 0

#     print(f"[perceive] loading PCAP...")
#     pts = lidar_pcap.load_both(entry["lidar_data"]["l1"], entry["lidar_data"]["l2"])
#     print(f"[perceive] {len(pts):,} LiDAR points loaded")

#     proj = CalibratedProjector()
#     u, v, depths = proj.project(pts, img.shape)
#     print(f"[perceive] {len(u):,} points projected into frame")

#     inside_depths = [depths[i] for i in range(len(u)) if master[int(v[i]), int(u[i])]]

#     if not inside_depths:
#         print("[perceive] no LiDAR points inside mask")
#         return None

#     median_depth = float(np.median(inside_depths))
#     bbox_px = [float(x) for x in target_box[0]]

#     # --- DRAW VISUALIZATION ---
#     vis = img.copy()
    
#     for i, box in enumerate(boxes):
#         x1, y1, x2, y2 = map(int, box)
#         cid = int(class_ids[i])
#         label = active_classes[cid] if cid < len(active_classes) else "building"
        
#         if i == largest_idx:
#             cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 255), 3) 
#             cv2.putText(vis, f"TARGET: {label}", (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
#         else:
#             cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 0, 0), 1) 

#     vis[master] = (vis[master] * 0.5 + np.array([0, 255, 0]) * 0.5).astype(np.uint8)

#     for i in range(len(u)):
#         if master[int(v[i]), int(u[i])]:
#             cv2.circle(vis, (int(u[i]), int(v[i])), 2, (0, 0, 255), -1)

#     cv2.putText(vis, f"Target Depth: {median_depth:.2f}m", (30, 50),
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
#     print(f"[perceive] scanning frames {start}–{end}...")

#     for fid in range(start, end + 1):
#         entry = next((r for r in manifest if r["frame_id"] == fid), None)
#         if entry is None:
#             continue
#         img = cv2.imread(entry["camera_data"]["path"])
#         if img is None:
#             print(f"  frame {fid:06d}: image missing")
#             continue

#         boxes, _ = _detect(yolo, img, cfg.YOLO_CLASSES, cfg.YOLO_CONF)
#         if len(boxes) == 0:
#             boxes, _ = _detect(yolo, img, cfg.FALLBACK_CLASSES, cfg.FALLBACK_CONF)

#         print(f"  frame {fid:06d}: {len(boxes)} det")
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



# #-----------------------------------------------------------------------------------------
# # import os
# # import re
# # import json
# # import argparse
# # import numpy as np
# # import cv2
# # from ultralytics import YOLO, SAM
# # import cfg

# # FALLBACK_CLASSES = [
# #     "building", "house", "commercial building", "brick wall", "facade",
# #     "wall", "structure", "apartment", "office building", "storefront",
# #     "architecture", "construction"
# # ]
# # FALLBACK_CONF = 0.05


# # def _read_calib(path):
# #     data = {}
# #     with open(path) as f:
# #         for line in f:
# #             line = line.strip()
# #             if not line or ":" not in line:
# #                 continue
# #             key, val = line.split(":", 1)
# #             key, val = key.strip(), val.strip()
# #             if val and val[0].isalpha():
# #                 continue
# #             nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", val)
# #             if nums:
# #                 data[key] = np.array([float(x) for x in nums])
# #     return data


# # def _get_mat(d, keys, shape):
# #     for k in keys:
# #         if k in d and d[k].size == np.prod(shape):
# #             return d[k].reshape(shape)
# #     raise KeyError(f"None of {keys} found in calibration. Available: {list(d.keys())}")


# # class Projector:
# #     def __init__(self, calib_dir):
# #         cam = _read_calib(os.path.join(calib_dir, "calib_cam_to_cam.txt"))
# #         vel = _read_calib(os.path.join(calib_dir, "calib_velo_to_cam.txt"))

# #         P2 = _get_mat(cam, ["P_rect_02", "P_rect_2", "P2"], (3, 4))
# #         R0 = _get_mat(cam, ["R_rect_00", "R_rect_0", "R0_rect"], (3, 3))
# #         R  = _get_mat(vel, ["R"], (3, 3))
# #         T  = _get_mat(vel, ["T"], (3, 1))

# #         Tr = np.eye(4)
# #         Tr[:3, :] = np.hstack((R, T))

# #         R0_4 = np.eye(4)
# #         R0_4[:3, :3] = R0

# #         self._full = P2 @ R0_4 @ Tr

# #     def project(self, pts, img_shape):
# #         xyz1 = np.hstack((pts[:, :3], np.ones((len(pts), 1))))
# #         proj = (self._full @ xyz1.T).T
# #         d = proj[:, 2]
# #         u = proj[:, 0] / d
# #         v = proj[:, 1] / d
# #         h, w = img_shape[:2]
# #         mask = (d > 0) & (u >= 0) & (u < w) & (v >= 0) & (v < h)
# #         return u[mask], v[mask], d[mask]


# # def _detect(yolo, img, classes, conf):
# #     yolo.set_classes(classes)
# #     results = yolo(img, conf=conf, iou=cfg.YOLO_IOU, verbose=False)
# #     boxes     = results[0].boxes.xyxy.cpu().numpy()
# #     class_ids = results[0].boxes.cls.cpu().numpy()
# #     return boxes, class_ids


# # def _process_detections(frame_id, entry, img, boxes, class_ids, active_classes):
# #     img_path   = entry["camera_data"]["path"]
# #     lidar_path = entry["lidar_data"]["path"]

# #     sam = SAM(cfg.SAM_MODEL)
# #     sam_res = sam(img_path, bboxes=boxes, verbose=False)
# #     masks = sam_res[0].masks.data.cpu().numpy()

# #     master = np.any(masks, axis=0)
# #     master = cv2.resize(master.astype(np.uint8), (img.shape[1], img.shape[0])) > 0

# #     proj = Projector(cfg.KITTI_CALIB_DIR)
# #     pts  = np.fromfile(lidar_path, dtype=np.float32).reshape(-1, 4)
# #     u, v, depths = proj.project(pts, img.shape)

# #     inside_depths = [depths[i] for i in range(len(u)) if master[int(v[i]), int(u[i])]]

# #     if not inside_depths:
# #         print(f"[perceive] frame {frame_id}: detections found but no LiDAR points inside mask")
# #         return None

# #     median_depth = float(np.median(inside_depths))

# #     largest_box = boxes[int(np.argmax(
# #         [(b[2]-b[0]) * (b[3]-b[1]) for b in boxes]
# #     ))]
# #     bbox_px = [float(x) for x in largest_box]
# #     img_w   = img.shape[1]

# #     vis = img.copy()
# #     for i, box in enumerate(boxes):
# #         x1, y1, x2, y2 = map(int, box)
# #         cid = int(class_ids[i])
# #         label = active_classes[cid] if cid < len(active_classes) else "building"
# #         cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 0, 0), 2)
# #         cv2.putText(vis, label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)

# #     vis[master] = (vis[master] * 0.5 + np.array([0, 255, 0]) * 0.5).astype(np.uint8)

# #     for i in range(len(u)):
# #         if master[int(v[i]), int(u[i])]:
# #             cv2.circle(vis, (int(u[i]), int(v[i])), 2, (0, 0, 255), -1)

# #     cv2.putText(vis, f"depth: {median_depth:.2f}m", (30, 40),
# #                 cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

# #     vis_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:04d}_vis.jpg")
# #     cv2.imwrite(vis_path, vis)

# #     out = {
# #         "frame_id":     frame_id,
# #         "median_depth": median_depth,
# #         "bbox_px":      bbox_px,
# #         "img_w":        img_w,
# #         "vis":          vis_path
# #     }
# #     out_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:04d}_perceive.json")
# #     with open(out_path, "w") as f:
# #         json.dump(out, f, indent=2)

# #     print(f"[perceive] frame {frame_id}: depth={median_depth:.2f}m  detections={len(boxes)} → {out_path}")
# #     return out


# # def run_frame(frame_id):
# #     with open(cfg.MANIFEST_PATH) as f:
# #         manifest = json.load(f)

# #     entry = next((r for r in manifest if r["frame_id"] == frame_id), None)
# #     if entry is None:
# #         raise ValueError(f"Frame {frame_id} not in manifest")

# #     img_path = entry["camera_data"]["path"]
# #     print(f"[perceive] loading image: {img_path}")

# #     img = cv2.imread(img_path)
# #     if img is None:
# #         raise FileNotFoundError(f"Image not found: {img_path}")

# #     raw_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:04d}_raw.jpg")
# #     cv2.imwrite(raw_path, img)
# #     print(f"[perceive] raw frame saved → {raw_path}")

# #     yolo = YOLO(cfg.YOLO_MODEL)

# #     print(f"[perceive] pass 1 — primary classes @ conf={cfg.YOLO_CONF}")
# #     boxes, class_ids = _detect(yolo, img, cfg.YOLO_CLASSES, cfg.YOLO_CONF)

# #     if len(boxes) == 0:
# #         print(f"[perceive] pass 1 found nothing — pass 2: fallback classes @ conf={FALLBACK_CONF}")
# #         boxes, class_ids = _detect(yolo, img, FALLBACK_CLASSES, FALLBACK_CONF)
# #         active_classes = FALLBACK_CLASSES
# #     else:
# #         active_classes = cfg.YOLO_CLASSES

# #     if len(boxes) == 0:
# #         print(f"[perceive] frame {frame_id}: both passes found no detections")
# #         print(f"[perceive] check raw frame at: {raw_path}")
# #         return None

# #     print(f"[perceive] {len(boxes)} detection(s) — passing to SAM")
# #     return _process_detections(frame_id, entry, img, boxes, class_ids, active_classes)


# # def scan_for_detections(start=0, end=20):
# #     with open(cfg.MANIFEST_PATH) as f:
# #         manifest = json.load(f)

# #     yolo = YOLO(cfg.YOLO_MODEL)

# #     print(f"[perceive] scanning frames {start}–{end} for first usable detection...")
# #     for fid in range(start, end + 1):
# #         entry = next((r for r in manifest if r["frame_id"] == fid), None)
# #         if entry is None:
# #             continue
# #         img = cv2.imread(entry["camera_data"]["path"])
# #         if img is None:
# #             continue

# #         boxes, _ = _detect(yolo, img, cfg.YOLO_CLASSES, cfg.YOLO_CONF)
# #         if len(boxes) == 0:
# #             boxes, _ = _detect(yolo, img, FALLBACK_CLASSES, FALLBACK_CONF)

# #         status = f"{len(boxes)} det" if len(boxes) > 0 else "none"
# #         print(f"  frame {fid:03d}: {status}")

# #     print("[perceive] scan complete — re-run with the best frame using --frame N")


# # if __name__ == "__main__":
# #     ap = argparse.ArgumentParser()
# #     ap.add_argument("--frame", type=int, default=5)
# #     ap.add_argument("--scan", action="store_true", help="Scan frames 0-20 and report detection counts")
# #     ap.add_argument("--scan-end", type=int, default=20)
# #     args = ap.parse_args()

# #     if args.scan:
# #         scan_for_detections(0, args.scan_end)
# #     else:
# #         run_frame(args.frame)

# #---------------------------------------------

# # import os
# # import json
# # import argparse
# # import numpy as np
# # import cv2
# # from ultralytics import YOLO, SAM
# # import cfg
# # import lidar_pcap


# # class ApproxProjector:
# #     def __init__(self):
# #         # ---------------------------------------------------------
# #         # SENSOR ALIGNMENT DIAL (TUNE THIS!)
# #         # ---------------------------------------------------------
# #         # Twist the LiDAR point cloud horizontally to align with the camera lens.
# #         # Common mounting angles are 0.0, 90.0, -90.0, or 180.0
# #         self.YAW_ADJUST_DEG = 90.0 
# #         # ---------------------------------------------------------
        
# #         self._K = np.array([
# #             [cfg.FX,     0,  cfg.CX],
# #             [0,      cfg.FY,  cfg.CY],
# #             [0,          0,       1]
# #         ], dtype=np.float64)

# #     def project(self, pts, img_shape):
# #         # 1. Read Raw LiDAR (X=Right, Y=Forward, Z=Up)
# #         x_lidar = pts[:, 0].astype(np.float64)
# #         y_lidar = pts[:, 1].astype(np.float64)
# #         z_lidar = pts[:, 2].astype(np.float64)

# #         # 2. Spin the cloud to match physical mounting
# #         import math
# #         theta = math.radians(self.YAW_ADJUST_DEG)
# #         cos_t, sin_t = math.cos(theta), math.sin(theta)
        
# #         x_spun = x_lidar * cos_t - y_lidar * sin_t
# #         y_spun = x_lidar * sin_t + y_lidar * cos_t
# #         z_spun = z_lidar

# #         # 3. Convert to OpenCV Camera System
# #         cam_z = y_spun   # LiDAR Forward -> Camera Depth
# #         cam_x = x_spun   # LiDAR Right -> Camera Right
# #         cam_y = -z_spun  # LiDAR Up -> Camera Down (Negative)

# #         cam_x += cfg.LIDAR_TO_CAM_X_OFFSET
# #         cam_y += cfg.LIDAR_TO_CAM_Y_OFFSET
# #         cam_z += cfg.LIDAR_TO_CAM_Z_OFFSET

# #         # 4. Cull points BEHIND the camera
# #         mask_front = cam_z > 0.5
# #         x, y, z = cam_x[mask_front], cam_y[mask_front], cam_z[mask_front]

# #         # 5. Project onto 2D image
# #         u = (cfg.FX * x / z + cfg.CX)
# #         v = (cfg.FY * y / z + cfg.CY)
# #         d = z

# #         h, w = img_shape[:2]
# #         mask_bounds = (u >= 0) & (u < w) & (v >= 0) & (v < h)
# #         return u[mask_bounds], v[mask_bounds], d[mask_bounds]

# # def _detect(yolo, img, classes, conf):
# #     yolo.set_classes(classes)
# #     results = yolo(img, conf=conf, iou=cfg.YOLO_IOU, verbose=False)
# #     boxes     = results[0].boxes.xyxy.cpu().numpy()
# #     class_ids = results[0].boxes.cls.cpu().numpy()
# #     return boxes, class_ids


# # def run_frame(frame_id):
# #     with open(cfg.MANIFEST_PATH) as f:
# #         manifest = json.load(f)

# #     entry = next((r for r in manifest if r["frame_id"] == frame_id), None)
# #     if entry is None:
# #         raise ValueError(f"Frame {frame_id} not in manifest")

# #     img_path = entry["camera_data"]["path"]
# #     print(f"[perceive] loading: {img_path}")

# #     img = cv2.imread(img_path)
# #     if img is None:
# #         raise FileNotFoundError(f"Image not found: {img_path}")

# #     raw_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:06d}_raw.jpg")
# #     cv2.imwrite(raw_path, img)
# #     print(f"[perceive] raw saved → {raw_path}")

# #     yolo = YOLO(cfg.YOLO_MODEL)

# #     print(f"[perceive] pass 1 — primary @ conf={cfg.YOLO_CONF}")
# #     boxes, class_ids = _detect(yolo, img, cfg.YOLO_CLASSES, cfg.YOLO_CONF)

# #     if len(boxes) == 0:
# #         print(f"[perceive] pass 2 — fallback @ conf={cfg.FALLBACK_CONF}")
# #         boxes, class_ids = _detect(yolo, img, cfg.FALLBACK_CLASSES, cfg.FALLBACK_CONF)
# #         active_classes = cfg.FALLBACK_CLASSES
# #     else:
# #         active_classes = cfg.YOLO_CLASSES

# #     if len(boxes) == 0:
# #         print(f"[perceive] no detections — check raw: {raw_path}")
# #         return None

# #     print(f"[perceive] {len(boxes)} detection(s) → SAM")

# #     sam = SAM(cfg.SAM_MODEL)
# #     sam_res = sam(img_path, bboxes=boxes, verbose=False)
# #     masks = sam_res[0].masks.data.cpu().numpy()

# #     master = np.any(masks, axis=0)
# #     master = cv2.resize(master.astype(np.uint8), (img.shape[1], img.shape[0])) > 0

# #     print(f"[perceive] loading PCAP...")
# #     pts = lidar_pcap.load_both(entry["lidar_data"]["l1"], entry["lidar_data"]["l2"])
# #     print(f"[perceive] {len(pts):,} LiDAR points loaded")

# #     proj = ApproxProjector()
# #     u, v, depths = proj.project(pts, img.shape)
# #     print(f"[perceive] {len(u):,} points projected into frame")

# #     inside_depths = [depths[i] for i in range(len(u)) if master[int(v[i]), int(u[i])]]

# #     if not inside_depths:
# #         print("[perceive] no LiDAR points inside mask")
# #         return None

# #     median_depth = float(np.median(inside_depths))

# #     largest_box = boxes[int(np.argmax(
# #         [(b[2]-b[0]) * (b[3]-b[1]) for b in boxes]
# #     ))]
# #     bbox_px = [float(x) for x in largest_box]

# #     vis = img.copy()
# #     for i, box in enumerate(boxes):
# #         x1, y1, x2, y2 = map(int, box)
# #         cid = int(class_ids[i])
# #         label = active_classes[cid] if cid < len(active_classes) else "building"
# #         cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 0, 0), 2)
# #         cv2.putText(vis, label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)

# #     vis[master] = (vis[master] * 0.5 + np.array([0, 255, 0]) * 0.5).astype(np.uint8)

# #     for i in range(len(u)):
# #         if master[int(v[i]), int(u[i])]:
# #             cv2.circle(vis, (int(u[i]), int(v[i])), 2, (0, 0, 255), -1)

# #     cv2.putText(vis, f"depth: {median_depth:.2f}m", (30, 50),
# #                 cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)

# #     vis_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:06d}_vis.jpg")
# #     cv2.imwrite(vis_path, vis)

# #     out = {
# #         "frame_id":     frame_id,
# #         "median_depth": median_depth,
# #         "bbox_px":      bbox_px,
# #         "img_w":        img.shape[1],
# #         "vis":          vis_path
# #     }
# #     out_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:06d}_perceive.json")
# #     with open(out_path, "w") as f:
# #         json.dump(out, f, indent=2)

# #     print(f"[perceive] depth={median_depth:.2f}m → {out_path}")
# #     return out


# # def scan_frames(start, end):
# #     with open(cfg.MANIFEST_PATH) as f:
# #         manifest = json.load(f)

# #     yolo = YOLO(cfg.YOLO_MODEL)
# #     print(f"[perceive] scanning frames {start}–{end}...")

# #     for fid in range(start, end + 1):
# #         entry = next((r for r in manifest if r["frame_id"] == fid), None)
# #         if entry is None:
# #             continue
# #         img = cv2.imread(entry["camera_data"]["path"])
# #         if img is None:
# #             print(f"  frame {fid:06d}: image missing")
# #             continue

# #         boxes, _ = _detect(yolo, img, cfg.YOLO_CLASSES, cfg.YOLO_CONF)
# #         if len(boxes) == 0:
# #             boxes, _ = _detect(yolo, img, cfg.FALLBACK_CLASSES, cfg.FALLBACK_CONF)

# #         print(f"  frame {fid:06d}: {len(boxes)} det")

# #     print("[perceive] scan done")


# # if __name__ == "__main__":
# #     ap = argparse.ArgumentParser()
# #     ap.add_argument("--frame", type=int, default=840)
# #     ap.add_argument("--scan", action="store_true")
# #     ap.add_argument("--scan-start", type=int, default=740)
# #     ap.add_argument("--scan-end",   type=int, default=760)
# #     args = ap.parse_args()

# #     if args.scan:
# #         scan_frames(args.scan_start, args.scan_end)
# #     else:
# #         run_frame(args.frame)

# # import os
# # import json
# # import math
# # import argparse
# # import numpy as np
# # import cv2
# # from ultralytics import YOLO, SAM
# # import cfg
# # import lidar_pcap


# # class FisheyeProjector:
# #     def __init__(self):
# #         self._K = np.array([
# #             [cfg.FX,    0, cfg.CX],
# #             [0,    cfg.FY, cfg.CY],
# #             [0,        0,      1]
# #         ], dtype=np.float64)

# #     def project(self, pts, img_shape):
# #         theta = math.radians(cfg.LIDAR_YAW_DEG)
# #         cos_t, sin_t = math.cos(theta), math.sin(theta)

# #         x_raw = pts[:, 0].astype(np.float64)
# #         y_raw = pts[:, 1].astype(np.float64)
# #         z_raw = pts[:, 2].astype(np.float64)

# #         x_rot = x_raw * cos_t - y_raw * sin_t
# #         y_rot = x_raw * sin_t + y_raw * cos_t
# #         z_rot = z_raw

# #         cam_z = y_rot
# #         cam_x = x_rot
# #         cam_y = -z_rot

# #         cam_x += cfg.LIDAR_TO_CAM_X_OFFSET
# #         cam_y += cfg.LIDAR_TO_CAM_Y_OFFSET
# #         cam_z += cfg.LIDAR_TO_CAM_Z_OFFSET

# #         front = cam_z > 0.5
# #         cx, cy, cz = cam_x[front], cam_y[front], cam_z[front]

# #         r_angle = np.arctan(np.sqrt(cx**2 + cy**2) / cz)

# #         k1, k2, k3, k4 = cfg.FISHEYE_K1, cfg.FISHEYE_K2, cfg.FISHEYE_K3, cfg.FISHEYE_K4
# #         r_d = r_angle * (1 + k1*r_angle**2 + k2*r_angle**4 + k3*r_angle**6 + k4*r_angle**8)

# #         norm = np.sqrt(cx**2 + cy**2)
# #         safe = norm > 1e-9
# #         phi_x = np.where(safe, cx / norm, 0.0)
# #         phi_y = np.where(safe, cy / norm, 0.0)

# #         u = cfg.FX * r_d * phi_x + cfg.CX
# #         v = cfg.FY * r_d * phi_y + cfg.CY
# #         d = cz

# #         h, w = img_shape[:2]
# #         in_bounds = (u >= 0) & (u < w) & (v >= 0) & (v < h)
# #         return u[in_bounds], v[in_bounds], d[in_bounds]


# # def _detect(yolo, img, classes, conf):
# #     yolo.set_classes(classes)
# #     results = yolo(img, conf=conf, iou=cfg.YOLO_IOU, verbose=False)
# #     boxes     = results[0].boxes.xyxy.cpu().numpy()
# #     class_ids = results[0].boxes.cls.cpu().numpy()
# #     return boxes, class_ids


# # def _filter_boxes_by_side(boxes, class_ids, img_w, side):
# #     if side == "right":
# #         keep = [i for i, b in enumerate(boxes) if (b[0] + b[2]) / 2 > img_w * 0.5]
# #     elif side == "left":
# #         keep = [i for i, b in enumerate(boxes) if (b[0] + b[2]) / 2 < img_w * 0.5]
# #     else:
# #         keep = list(range(len(boxes)))
# #     if not keep:
# #         return boxes, class_ids
# #     return boxes[keep], class_ids[keep]


# # def run_frame(frame_id):
# #     with open(cfg.MANIFEST_PATH) as f:
# #         manifest = json.load(f)

# #     entry = next((r for r in manifest if r["frame_id"] == frame_id), None)
# #     if entry is None:
# #         raise ValueError(f"Frame {frame_id} not in manifest")

# #     img_path = entry["camera_data"]["path"]
# #     print(f"[perceive] loading: {img_path}")

# #     img = cv2.imread(img_path)
# #     if img is None:
# #         raise FileNotFoundError(f"Image not found: {img_path}")

# #     raw_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:06d}_raw.jpg")
# #     cv2.imwrite(raw_path, img)

# #     yolo = YOLO(cfg.YOLO_MODEL)

# #     print(f"[perceive] pass 1 @ conf={cfg.YOLO_CONF}")
# #     boxes, class_ids = _detect(yolo, img, cfg.YOLO_CLASSES, cfg.YOLO_CONF)
# #     if len(boxes) == 0:
# #         print(f"[perceive] pass 2 @ conf={cfg.FALLBACK_CONF}")
# #         boxes, class_ids = _detect(yolo, img, cfg.FALLBACK_CLASSES, cfg.FALLBACK_CONF)
# #         active_classes = cfg.FALLBACK_CLASSES
# #     else:
# #         active_classes = cfg.YOLO_CLASSES

# #     if len(boxes) == 0:
# #         print(f"[perceive] no detections — check raw: {raw_path}")
# #         return None

# #     boxes, class_ids = _filter_boxes_by_side(boxes, class_ids, img.shape[1], cfg.IMAGE_BUILDING_SIDE)
# #     print(f"[perceive] {len(boxes)} box(es) after '{cfg.IMAGE_BUILDING_SIDE}' filter → SAM")

# #     if len(boxes) == 0:
# #         print("[perceive] all boxes filtered — change IMAGE_BUILDING_SIDE in cfg.py to 'left' or 'any'")
# #         return None

# #     sam = SAM(cfg.SAM_MODEL)
# #     sam_res = sam(img_path, bboxes=boxes, verbose=False)
# #     masks = sam_res[0].masks.data.cpu().numpy()

# #     master = np.any(masks, axis=0)
# #     master = cv2.resize(master.astype(np.uint8), (img.shape[1], img.shape[0])) > 0

# #     print(f"[perceive] loading PCAP...")
# #     pts = lidar_pcap.load_both(entry["lidar_data"]["l1"], entry["lidar_data"]["l2"])
# #     print(f"[perceive] {len(pts):,} raw LiDAR points")

# #     proj = FisheyeProjector()
# #     u, v, depths = proj.project(pts, img.shape)
# #     print(f"[perceive] {len(u):,} projected into frame")

# #     inside_depths = [depths[i] for i in range(len(u)) if master[int(v[i]), int(u[i])]]

# #     if not inside_depths:
# #         print(f"[perceive] 0 points inside mask (projected={len(u)}, mask_px={master.sum()})")
# #         print("[perceive] try adjusting LIDAR_YAW_DEG in cfg.py (try 0, 90, -90, 180)")
# #         return None

# #     median_depth = float(np.median(inside_depths))

# #     largest_box = boxes[int(np.argmax([(b[2]-b[0])*(b[3]-b[1]) for b in boxes]))]
# #     bbox_px = [float(x) for x in largest_box]

# #     vis = img.copy()
# #     for i in range(0, len(u), 4):
# #         cv2.circle(vis, (int(u[i]), int(v[i])), 1, (80, 80, 200), -1)

# #     vis[master] = (vis[master] * 0.5 + np.array([0, 255, 0]) * 0.5).astype(np.uint8)

# #     for i in range(len(u)):
# #         if master[int(v[i]), int(u[i])]:
# #             cv2.circle(vis, (int(u[i]), int(v[i])), 2, (0, 0, 255), -1)

# #     for i, box in enumerate(boxes):
# #         x1, y1, x2, y2 = map(int, box)
# #         cid = int(class_ids[i])
# #         label = active_classes[cid] if cid < len(active_classes) else "building"
# #         cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 0, 0), 2)
# #         cv2.putText(vis, label, (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)

# #     cv2.putText(vis, f"depth: {median_depth:.2f}m", (30, 50),
# #                 cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)

# #     vis_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:06d}_vis.jpg")
# #     cv2.imwrite(vis_path, vis)

# #     out = {
# #         "frame_id":     frame_id,
# #         "median_depth": median_depth,
# #         "bbox_px":      bbox_px,
# #         "img_w":        img.shape[1],
# #         "vis":          vis_path
# #     }
# #     out_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:06d}_perceive.json")
# #     with open(out_path, "w") as f:
# #         json.dump(out, f, indent=2)

# #     print(f"[perceive] depth={median_depth:.2f}m → {out_path}")
# #     return out


# # def scan_frames(start, end):
# #     with open(cfg.MANIFEST_PATH) as f:
# #         manifest = json.load(f)
# #     yolo = YOLO(cfg.YOLO_MODEL)
# #     print(f"[perceive] scanning {start}–{end}...")
# #     for fid in range(start, end + 1):
# #         entry = next((r for r in manifest if r["frame_id"] == fid), None)
# #         if entry is None:
# #             continue
# #         img = cv2.imread(entry["camera_data"]["path"])
# #         if img is None:
# #             print(f"  {fid:06d}: missing")
# #             continue
# #         boxes, cids = _detect(yolo, img, cfg.YOLO_CLASSES, cfg.YOLO_CONF)
# #         if len(boxes) == 0:
# #             boxes, cids = _detect(yolo, img, cfg.FALLBACK_CLASSES, cfg.FALLBACK_CONF)
# #         rb, _ = _filter_boxes_by_side(boxes, cids, img.shape[1], "right")
# #         lb, _ = _filter_boxes_by_side(boxes, cids, img.shape[1], "left")
# #         print(f"  {fid:06d}: total={len(boxes)} right={len(rb)} left={len(lb)}")
# #     print("[perceive] scan done")


# # if __name__ == "__main__":
# #     ap = argparse.ArgumentParser()
# #     ap.add_argument("--frame", type=int, default=840)
# #     ap.add_argument("--scan", action="store_true")
# #     ap.add_argument("--scan-start", type=int, default=740)
# #     ap.add_argument("--scan-end",   type=int, default=760)
# #     args = ap.parse_args()
# #     if args.scan:
# #         scan_frames(args.scan_start, args.scan_end)
# #     else:
# #         run_frame(args.frame)

# #---------------------------------------------------------------------

# # import os
# # import json
# # import argparse
# # import numpy as np
# # import cv2
# # import math
# # from ultralytics import YOLO, SAM
# # import cfg
# # import lidar_pcap

# # # =========================================================
# # # HARDCODED FALLBACKS (Prevents cfg.py errors)
# # # =========================================================
# # FALLBACK_CLASSES = [
# #     "building", "house", "commercial building", "brick wall", "facade",
# #     "wall", "structure", "apartment", "office building", "storefront",
# #     "architecture", "construction"
# # ]
# # FALLBACK_CONF = 0.25 
# # # =========================================================


# # class CalibratedProjector:
# #     def __init__(self):
# #         # Camera Intrinsics
# #         self._K = np.array([
# #             [cfg.FX,     0,  cfg.CX],
# #             [0,      cfg.FY,  cfg.CY],
# #             [0,          0,       1]
# #         ], dtype=np.float64)

# #         # =========================================================
# #         # PERFECT CALIBRATION: LiDAR to Camera Extrinsic Matrix
# #         # Automatically rotates and translates the point cloud!
# #         # =========================================================
# #         self._Tr = np.array([
# #             [ 0.2092700, -0.9776630, -0.0195126,  2.054160 ],
# #             [ 0.0386136,  0.0282009, -0.9988560,  0.401883 ],
# #             [ 0.9770950,  0.2082770,  0.0436527, -0.035744 ],
# #             [ 0.0000000,  0.0000000,  0.0000000,  1.000000 ]
# #         ], dtype=np.float64)

# #     def project(self, pts, img_shape):
# #         # 1. Grab raw LiDAR X, Y, Z
# #         xyz = pts[:, :3].astype(np.float64)
        
# #         # 2. Add '1' to make them 4D homogeneous coordinates [X, Y, Z, 1]
# #         ones = np.ones((len(xyz), 1), dtype=np.float64)
# #         xyz1 = np.hstack([xyz, ones])
        
# #         # 3. Apply the True Calibration Matrix!
# #         cam_xyz = (self._Tr @ xyz1.T).T
        
# #         x, y, z = cam_xyz[:, 0], cam_xyz[:, 1], cam_xyz[:, 2]

# #         # 4. Cull points BEHIND the camera
# #         mask_front = z > 0.5
# #         x, y, z = x[mask_front], y[mask_front], z[mask_front]

# #         # 5. Apply Intrinsic Camera Lens Projection
# #         u = (cfg.FX * x / z + cfg.CX)
# #         v = (cfg.FY * y / z + cfg.CY)
# #         d = z

# #         h, w = img_shape[:2]
# #         mask_bounds = (u >= 0) & (u < w) & (v >= 0) & (v < h)
# #         return u[mask_bounds], v[mask_bounds], d[mask_bounds]


# # def _detect(yolo, img, classes, conf):
# #     yolo.set_classes(classes)
# #     results = yolo(img, conf=conf, iou=cfg.YOLO_IOU, verbose=False)
# #     boxes     = results[0].boxes.xyxy.cpu().numpy()
# #     class_ids = results[0].boxes.cls.cpu().numpy()
# #     return boxes, class_ids


# # def run_frame(frame_id):
# #     with open(cfg.MANIFEST_PATH) as f:
# #         manifest = json.load(f)

# #     entry = next((r for r in manifest if r["frame_id"] == frame_id), None)
# #     if entry is None:
# #         raise ValueError(f"Frame {frame_id} not in manifest")

# #     img_path = entry["camera_data"]["path"]
# #     print(f"[perceive] loading: {img_path}")

# #     img = cv2.imread(img_path)
# #     if img is None:
# #         raise FileNotFoundError(f"Image not found: {img_path}")

# #     raw_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:06d}_raw.jpg")
# #     cv2.imwrite(raw_path, img)
# #     print(f"[perceive] raw saved → {raw_path}")

# #     yolo = YOLO(cfg.YOLO_MODEL)

# #     print(f"[perceive] pass 1 — primary @ conf={cfg.YOLO_CONF}")
# #     boxes, class_ids = _detect(yolo, img, cfg.YOLO_CLASSES, cfg.YOLO_CONF)

# #     if len(boxes) == 0:
# #         print(f"[perceive] pass 2 — fallback @ conf={FALLBACK_CONF}")
# #         boxes, class_ids = _detect(yolo, img, FALLBACK_CLASSES, FALLBACK_CONF)
# #         active_classes = FALLBACK_CLASSES
# #     else:
# #         active_classes = cfg.YOLO_CLASSES

# #     if len(boxes) == 0:
# #         print(f"[perceive] no detections — check raw: {raw_path}")
# #         return None

# #     # --- THE SAM FIX: ONLY SEGMENT THE LARGEST BUILDING ---
# #     largest_idx = int(np.argmax([(b[2]-b[0]) * (b[3]-b[1]) for b in boxes]))
# #     target_box = boxes[largest_idx:largest_idx+1]  
# #     target_class = class_ids[largest_idx]
    
# #     print(f"[perceive] {len(boxes)} detections found. Locking SAM onto the primary target...")

# #     sam = SAM(cfg.SAM_MODEL)
# #     sam_res = sam(img_path, bboxes=target_box, verbose=False)
# #     masks = sam_res[0].masks.data.cpu().numpy()

# #     master = np.any(masks, axis=0)
# #     master = cv2.resize(master.astype(np.uint8), (img.shape[1], img.shape[0])) > 0

# #     print(f"[perceive] loading PCAP...")
# #     pts = lidar_pcap.load_both(entry["lidar_data"]["l1"], entry["lidar_data"]["l2"])
# #     print(f"[perceive] {len(pts):,} LiDAR points loaded")

# #     proj = CalibratedProjector()
# #     u, v, depths = proj.project(pts, img.shape)
# #     print(f"[perceive] {len(u):,} points projected into frame")

# #     inside_depths = [depths[i] for i in range(len(u)) if master[int(v[i]), int(u[i])]]

# #     if not inside_depths:
# #         print("[perceive] no LiDAR points inside mask")
# #         return None

# #     median_depth = float(np.median(inside_depths))
# #     bbox_px = [float(x) for x in target_box[0]]

# #     # --- DRAW VISUALIZATION ---
# #     vis = img.copy()
    
# #     for i, box in enumerate(boxes):
# #         x1, y1, x2, y2 = map(int, box)
# #         cid = int(class_ids[i])
# #         label = active_classes[cid] if cid < len(active_classes) else "building"
        
# #         if i == largest_idx:
# #             cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 255), 3) 
# #             cv2.putText(vis, f"TARGET: {label}", (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
# #         else:
# #             cv2.rectangle(vis, (x1, y1), (x2, y2), (255, 0, 0), 1) 

# #     vis[master] = (vis[master] * 0.5 + np.array([0, 255, 0]) * 0.5).astype(np.uint8)

# #     for i in range(len(u)):
# #         if master[int(v[i]), int(u[i])]:
# #             cv2.circle(vis, (int(u[i]), int(v[i])), 2, (0, 0, 255), -1)

# #     cv2.putText(vis, f"Target Depth: {median_depth:.2f}m", (30, 50),
# #                 cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)

# #     vis_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:06d}_vis.jpg")
# #     cv2.imwrite(vis_path, vis)

# #     out = {
# #         "frame_id":     frame_id,
# #         "median_depth": median_depth,
# #         "bbox_px":      bbox_px,
# #         "img_w":        img.shape[1],
# #         "vis":          vis_path
# #     }
# #     out_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:06d}_perceive.json")
# #     with open(out_path, "w") as f:
# #         json.dump(out, f, indent=2)

# #     print(f"[perceive] depth={median_depth:.2f}m → {out_path}")
# #     return out


# # def scan_frames(start, end):
# #     with open(cfg.MANIFEST_PATH) as f:
# #         manifest = json.load(f)

# #     yolo = YOLO(cfg.YOLO_MODEL)
# #     print(f"[perceive] scanning frames {start}–{end}...")

# #     for fid in range(start, end + 1):
# #         entry = next((r for r in manifest if r["frame_id"] == fid), None)
# #         if entry is None:
# #             continue
# #         img = cv2.imread(entry["camera_data"]["path"])
# #         if img is None:
# #             print(f"  frame {fid:06d}: image missing")
# #             continue

# #         boxes, _ = _detect(yolo, img, cfg.YOLO_CLASSES, cfg.YOLO_CONF)
# #         if len(boxes) == 0:
# #             boxes, _ = _detect(yolo, img, FALLBACK_CLASSES, FALLBACK_CONF)

# #         print(f"  frame {fid:06d}: {len(boxes)} det")
# #     print("[perceive] scan done")


# # if __name__ == "__main__":
# #     ap = argparse.ArgumentParser()
# #     ap.add_argument("--frame", type=int, default=840)
# #     ap.add_argument("--scan", action="store_true")
# #     ap.add_argument("--scan-start", type=int, default=740)
# #     ap.add_argument("--scan-end",   type=int, default=760)
# #     args = ap.parse_args()

# #     if args.scan:
# #         scan_frames(args.scan_start, args.scan_end)
# #     else:
# #         run_frame(args.frame)

# perceive_robust.py
# Full rewrite to fix: vehicle interior points, mask bleeding, wrong detection region

# import os, json, math
# import cv2
# import numpy as np
# from ultralytics import YOLO, SAM
# import cfg
# import lidar_pcap

# # ─── CALIBRATED PROJECTOR (uses your FAST-Calib matrix) ──────────────────────
# class CalibratedProjector:
#     def __init__(self):
#         # From your FAST-Calib output
#         self.K = np.array([
#             [1106.46,    0.0,  1080.0],
#             [   0.0, 1077.77, 1920.0],
#             [   0.0,    0.0,     1.0]
#         ], dtype=np.float64)

#         # Full 4x4 LiDAR→Camera extrinsic
#         self.T = np.array([
#             [ 0.20927,  -0.977663, -0.0195126,  2.05416],
#             [ 0.0386136, 0.0282009, -0.998856,  0.401883],
#             [ 0.977095,  0.208277,   0.0436527,-0.035744],
#             [ 0.0,       0.0,        0.0,        1.0    ]
#         ], dtype=np.float64)

#     def project(self, pts_xyz, img_h, img_w):
#         """
#         pts_xyz : (N,3) float32  LiDAR points
#         returns  : u(M,), v(M,), depth(M,)  — only valid in-frame points
#         """
#         N = len(pts_xyz)
#         ones = np.ones((N, 1), dtype=np.float64)
#         pts_h = np.hstack([pts_xyz.astype(np.float64), ones])   # (N,4)

#         # Transform to camera frame
#         cam = (self.T @ pts_h.T).T          # (N,4)
#         x, y, z = cam[:,0], cam[:,1], cam[:,2]

#         # ── EGO-VEHICLE FILTER ──────────────────────────────────────────────
#         # Remove points that are BEHIND or TOO CLOSE (vehicle body / interior)
#         valid = (
#             (z > 1.5)      &   # must be in front of camera, at least 1.5 m
#             (z < 120.0)    &   # ignore absurdly far noise
#             (np.abs(x) < 60.0) &
#             (np.abs(y) < 30.0)
#         )
#         x, y, z = x[valid], y[valid], z[valid]

#         # Project
#         u = self.K[0,0] * x / z + self.K[0,2]
#         v = self.K[1,1] * y / z + self.K[1,2]

#         # Keep only points that land inside the image
#         in_frame = (u >= 0) & (u < img_w) & (v >= 0) & (v < img_h)
#         return u[in_frame], v[in_frame], z[in_frame]


# # ─── YOLO DETECTION WITH REGION AWARENESS ────────────────────────────────────
# def detect_buildings(img, img_w, img_h):
#     """
#     Multi-pass YOLO with:
#       - primary pass full image
#       - if nothing on right 60% of frame, bias search there
#       - returns list of (x1,y1,x2,y2,conf) sorted by conf desc
#     """
#     yolo = YOLO(cfg.YOLO_MODEL)

#     PRIMARY_CLASSES = [
#         "building", "house", "commercial building",
#         "brick wall", "facade", "concrete building",
#         "flat roof building", "multi-storey building"
#     ]
#     FALLBACK_CLASSES = [
#         "building", "house", "wall", "structure",
#         "apartment", "office building", "storefront",
#         "architecture", "concrete structure", "terrace building"
#     ]

#     def run(classes, conf, region_crop=None):
#         src = img
#         offset_x, offset_y = 0, 0
#         if region_crop is not None:
#             x1c, y1c, x2c, y2c = region_crop
#             src = img[y1c:y2c, x1c:x2c]
#             offset_x, offset_y = x1c, y1c
#         yolo.set_classes(classes)
#         res = yolo(src, conf=conf, iou=0.45, verbose=False)
#         boxes = res[0].boxes.xyxy.cpu().numpy()
#         confs = res[0].boxes.conf.cpu().numpy()
#         # Shift back if cropped
#         if region_crop is not None and len(boxes):
#             boxes[:, [0,2]] += offset_x
#             boxes[:, [1,3]] += offset_y
#         return boxes, confs

#     # Pass 1 — full image, primary classes
#     boxes, confs = run(PRIMARY_CLASSES, conf=0.28)

#     # Pass 2 — fallback classes, full image
#     if len(boxes) == 0:
#         print("[detect] pass 2 — fallback classes")
#         boxes, confs = run(FALLBACK_CLASSES, conf=0.12)

#     # Pass 3 — right 65% crop (your camera has building on right side)
#     if len(boxes) == 0:
#         print("[detect] pass 3 — right-side crop")
#         crop = (int(img_w * 0.35), 0, img_w, img_h)
#         boxes, confs = run(FALLBACK_CLASSES, conf=0.08, region_crop=crop)

#     if len(boxes) == 0:
#         return []

#     # Filter: remove boxes that are mostly in the LEFT 35% (vehicle interior zone)
#     # and boxes that are too small or too much in the sky (top 20%)
#     filtered = []
#     for i, (box, c) in enumerate(zip(boxes, confs)):
#         x1, y1, x2, y2 = box
#         box_cx = (x1 + x2) / 2
#         box_cy = (y1 + y2) / 2
#         box_w = x2 - x1
#         box_h = y2 - y1
#         area_frac = (box_w * box_h) / (img_w * img_h)

#         # Skip tiny boxes
#         if area_frac < 0.005:
#             continue
#         # Skip boxes that are mostly in the vehicle interior (left 40%)
#         if box_cx < img_w * 0.40 and box_cy > img_h * 0.40:
#             continue
#         # Skip boxes that are entirely sky (top 25% of image)
#         if y2 < img_h * 0.25:
#             continue

#         filtered.append((x1, y1, x2, y2, float(c)))

#     # Sort by confidence desc
#     filtered.sort(key=lambda b: b[4], reverse=True)
#     return filtered


# # ─── DEPTH FROM LIDAR WITHIN MASK ────────────────────────────────────────────
# def extract_depth_in_mask(u, v, depths, mask, img_h, img_w, percentile=40):
#     """
#     Use a lower percentile (not median) — median gets skewed by
#     foreground clutter (trees, poles). 40th percentile gives the
#     dominant surface depth more reliably.
#     """
#     u_i = np.clip(u.astype(int), 0, img_w - 1)
#     v_i = np.clip(v.astype(int), 0, img_h - 1)

#     inside = mask[v_i, u_i] > 0
#     inside_depths = depths[inside]

#     if len(inside_depths) < 5:
#         return None, 0

#     # Remove outliers: keep middle 80%
#     lo, hi = np.percentile(inside_depths, 10), np.percentile(inside_depths, 90)
#     clean = inside_depths[(inside_depths >= lo) & (inside_depths <= hi)]

#     if len(clean) < 3:
#         return None, 0

#     return float(np.percentile(clean, percentile)), len(clean)


# # ─── MAIN PERCEIVE FUNCTION ───────────────────────────────────────────────────
# def run_frame(frame_id):
#     import lidar_pcap

#     img_path = os.path.join(cfg.LENS1_DIR, f"frame_{frame_id:06d}.jpg")
#     out_dir  = cfg.OUT_DIR
#     os.makedirs(out_dir, exist_ok=True)

#     print(f"[perceive] loading: {img_path}")
#     img = cv2.imread(img_path)
#     if img is None:
#         raise FileNotFoundError(f"Image not found: {img_path}")

#     img_h, img_w = img.shape[:2]

#     # Save raw copy
#     cv2.imwrite(os.path.join(out_dir, f"frame_{frame_id:06d}_raw.jpg"), img)

#     # ── DETECTION ──────────────────────────────────────────────────────────
#     detections = detect_buildings(img, img_w, img_h)

#     if not detections:
#         print("[perceive] ❌ No buildings detected")
#         return None

#     best = detections[0]
#     x1, y1, x2, y2, det_conf = best
#     bbox = [int(x1), int(y1), int(x2), int(y2)]
#     print(f"[perceive] best detection: conf={det_conf:.2f} bbox={bbox}")

#     # ── SAM SEGMENTATION ───────────────────────────────────────────────────
#     print("[perceive] running SAM...")
#     sam = SAM(cfg.SAM_MODEL)
#     target_box = np.array([[x1, y1, x2, y2]])
#     sam_res = sam(img_path, bboxes=target_box, verbose=False)

#     mask = None
#     if sam_res[0].masks is not None:
#         raw_mask = sam_res[0].masks.data[0].cpu().numpy().astype(np.float32)
#         mask = cv2.resize(raw_mask, (img_w, img_h), interpolation=cv2.INTER_NEAREST)
#         mask = (mask > 0.5).astype(np.uint8)

#         # ── MASK CLEANUP: remove the vehicle interior zone ─────────────────
#         # Left 38% of image is mostly vehicle body — zero it out
#         vehicle_interior_x = int(img_w * 0.38)
#         mask[:, :vehicle_interior_x] = 0

#         # Also remove ground plane (bottom 15%)
#         ground_start = int(img_h * 0.85)
#         mask[ground_start:, :] = 0

#         # Morphological cleanup
#         kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
#         mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
#         mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
#     else:
#         print("[perceive] SAM returned no mask, using bbox region")
#         mask = np.zeros((img_h, img_w), dtype=np.uint8)
#         mask[int(y1):int(y2), int(x1):int(x2)] = 1

#     # ── LIDAR LOADING + PROJECTION ─────────────────────────────────────────
#     print("[perceive] loading PCAP...")
#     pts = lidar_pcap.load_both(cfg.L1_PCAP_PATH, cfg.L2_PCAP_PATH)
#     if pts is None or len(pts) == 0:
#         print("[perceive] ❌ No LiDAR points loaded")
#         return None

#     print(f"[perceive] {len(pts):,} LiDAR points loaded")

#     proj = CalibratedProjector()
#     u, v, depths = proj.project(pts, img_h, img_w)
#     print(f"[perceive] {len(u):,} points projected into frame")

#     # ── DEPTH EXTRACTION ───────────────────────────────────────────────────
#     depth_m, n_pts = extract_depth_in_mask(u, v, depths, mask, img_h, img_w)

#     if depth_m is None or n_pts < 3:
#         # Fallback: use bbox center column depth
#         print("[perceive] ⚠️  sparse mask depth, falling back to bbox-strip depth")
#         cx = int((x1 + x2) / 2)
#         strip_w = int((x2 - x1) * 0.3)
#         in_strip = (
#             (u >= cx - strip_w) & (u <= cx + strip_w) &
#             (v >= y1) & (v <= y2) &
#             (depths > 1.5)
#         )
#         strip_depths = depths[in_strip]
#         if len(strip_depths) > 2:
#             depth_m = float(np.percentile(strip_depths, 40))
#             n_pts = len(strip_depths)
#         else:
#             depth_m = float(np.mean(depths[(depths > 2) & (depths < 80)])) if len(depths) > 0 else 25.0
#             n_pts = 0

#     print(f"[perceive] depth={depth_m:.2f}m ({n_pts} pts)")

#     # ── VISUALIZATION ──────────────────────────────────────────────────────
#     vis = img.copy()

#     # Draw ONLY the in-frame, in-front LiDAR points (colored by depth)
#     max_d = 60.0
#     for pu, pv, pd in zip(u.astype(int), v.astype(int), depths):
#         if 0 <= pu < img_w and 0 <= pv < img_h:
#             t = min(pd / max_d, 1.0)
#             # Blue=near → Red=far
#             color = (int(255*(1-t)), 50, int(255*t))
#             cv2.circle(vis, (pu, pv), 2, color, -1)

#     # Draw SAM mask overlay (only on right side, green tint)
#     if mask is not None:
#         overlay = vis.copy()
#         overlay[mask > 0] = (overlay[mask > 0] * 0.5 + np.array([0, 200, 0]) * 0.5).astype(np.uint8)
#         vis = overlay

#     # Draw bbox
#     cv2.rectangle(vis, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 255), 3)

#     # Info panel
#     info_lines = [
#         f"Depth: {depth_m:.1f}m",
#         f"Det conf: {det_conf:.2f}",
#         f"LiDAR pts in mask: {n_pts}",
#         f"Frame: {frame_id}"
#     ]
#     for i, line in enumerate(info_lines):
#         cv2.putText(vis, line, (20, 40 + i*35),
#                     cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,0,0), 4)
#         cv2.putText(vis, line, (20, 40 + i*35),
#                     cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255,255,255), 2)

#     vis_path = os.path.join(out_dir, f"frame_{frame_id:06d}_perceive_vis.jpg")
#     cv2.imwrite(vis_path, vis)

#     # ── OUTPUT JSON ────────────────────────────────────────────────────────
#     out = {
#         "frame_id":      frame_id,
#         "bbox":          bbox,
#         "det_conf":      det_conf,
#         "median_depth":  depth_m,
#         "depth_pts":     n_pts,
#         "img_w":         img_w,
#         "img_h":         img_h,
#     }
#     out_path = os.path.join(out_dir, f"frame_{frame_id:06d}_perceive.json")
#     with open(out_path, "w") as f:
#         json.dump(out, f, indent=2)

#     print(f"[perceive] depth={depth_m:.2f}m → {out_path}")
#     return out


# if __name__ == "__main__":
#     import argparse
#     ap = argparse.ArgumentParser()
#     ap.add_argument("--frame", type=int, default=840)
#     args = ap.parse_args()
#     run_frame(args.frame)


#-------------------------------------------------------------------------

# import os
# import json
# import cv2
# import numpy as np
# from ultralytics import YOLO, SAM
# import cfg
# import lidar_pcap


# # ─── CALIBRATED PROJECTOR ────────────────────────────────────────────────────
# class CalibratedProjector:
#     def __init__(self):
#         # FIXED: CX=1920 (half of 3840), CY=1080 (half of 2160)
#         self.K = np.array([
#             [cfg.FX,   0.0,  cfg.CX],
#             [  0.0,  cfg.FY, cfg.CY],
#             [  0.0,    0.0,    1.0 ]
#         ], dtype=np.float64)

#         # Full 4x4 LiDAR→Camera extrinsic from FAST-Calib
#         self.T = np.array([
#             [ 0.20927,  -0.977663, -0.0195126,  2.05416 ],
#             [ 0.0386136, 0.0282009, -0.998856,  0.401883],
#             [ 0.977095,  0.208277,   0.0436527, -0.035744],
#             [ 0.0,       0.0,        0.0,        1.0    ]
#         ], dtype=np.float64)

#     def project(self, pts_xyz, img_h, img_w):
#         N    = len(pts_xyz)
#         ones = np.ones((N, 1), dtype=np.float64)
#         pts_h = np.hstack([pts_xyz.astype(np.float64), ones])  # (N,4)

#         cam      = (self.T @ pts_h.T).T         # (N,4)
#         x, y, z  = cam[:, 0], cam[:, 1], cam[:, 2]

#         # ── EGO-VEHICLE + GROUND FILTER ─────────────────────────────────────
#         valid = (
#             (z > 1.5)           &   # in front of camera, clears vehicle nose
#             (z < 120.0)         &   # ignore noise far away
#             (np.abs(x) < 60.0)  &
#             (y > -2.5)          &   # remove extreme downward beams (ground stripe)
#             (y < 15.0)              # remove extreme upward beams (sky noise)
#         )
#         x, y, z = x[valid], y[valid], z[valid]

#         u = self.K[0, 0] * x / z + self.K[0, 2]
#         v = self.K[1, 1] * y / z + self.K[1, 2]

#         in_frame = (u >= 0) & (u < img_w) & (v >= 0) & (v < img_h)
#         return u[in_frame], v[in_frame], z[in_frame]


# # ─── BUILDING DETECTION ───────────────────────────────────────────────────────
# def detect_buildings(img, img_w, img_h):
#     yolo = YOLO(cfg.YOLO_MODEL)

#     PRIMARY_CLASSES = [
#         "building", "house", "commercial building",
#         "brick wall", "facade", "concrete building",
#         "flat roof building", "multi-storey building"
#     ]
#     FALLBACK_CLASSES = [
#         "building", "house", "wall", "structure",
#         "apartment", "office building", "storefront",
#         "architecture", "concrete structure", "terrace building"
#     ]

#     def run(classes, conf, region_crop=None):
#         src = img
#         offset_x, offset_y = 0, 0
#         if region_crop is not None:
#             x1c, y1c, x2c, y2c = region_crop
#             src = img[y1c:y2c, x1c:x2c]
#             offset_x, offset_y = x1c, y1c
#         yolo.set_classes(classes)
#         res   = yolo(src, conf=conf, iou=0.45, verbose=False)
#         boxes = res[0].boxes.xyxy.cpu().numpy()
#         confs = res[0].boxes.conf.cpu().numpy()
#         if region_crop is not None and len(boxes):
#             boxes[:, [0, 2]] += offset_x
#             boxes[:, [1, 3]] += offset_y
#         return boxes, confs

#     # Pass 1 — full image, primary classes
#     boxes, confs = run(PRIMARY_CLASSES, conf=0.28)

#     # Pass 2 — fallback classes, full image
#     if len(boxes) == 0:
#         print("[detect] pass 2 — fallback classes")
#         boxes, confs = run(FALLBACK_CLASSES, conf=0.12)

#     # Pass 3 — right 65% crop (building is on right side for this camera mount)
#     if len(boxes) == 0:
#         print("[detect] pass 3 — right-side crop")
#         crop  = (int(img_w * 0.35), 0, img_w, img_h)
#         boxes, confs = run(FALLBACK_CLASSES, conf=0.08, region_crop=crop)

#     if len(boxes) == 0:
#         return []

#     filtered = []
#     for box, c in zip(boxes, confs):
#         x1, y1, x2, y2 = box
#         box_cx   = (x1 + x2) / 2
#         box_cy   = (y1 + y2) / 2
#         area_frac = ((x2 - x1) * (y2 - y1)) / (img_w * img_h)

#         if area_frac < 0.005:
#             continue
#         # Skip boxes centred in the vehicle-interior zone (left 40%, lower half)
#         if box_cx < img_w * 0.40 and box_cy > img_h * 0.40:
#             continue
#         # Skip boxes entirely in the sky (top 25%)
#         if y2 < img_h * 0.25:
#             continue

#         filtered.append((x1, y1, x2, y2, float(c)))

#     filtered.sort(key=lambda b: b[4], reverse=True)
#     return filtered


# # ─── DEPTH EXTRACTION FROM LIDAR MASK ────────────────────────────────────────
# def extract_depth_in_mask(u, v, depths, mask, img_h, img_w, percentile=40):
#     u_i = np.clip(u.astype(int), 0, img_w - 1)
#     v_i = np.clip(v.astype(int), 0, img_h - 1)

#     inside        = mask[v_i, u_i] > 0
#     inside_depths = depths[inside]

#     if len(inside_depths) < 5:
#         return None, 0

#     lo, hi = np.percentile(inside_depths, 10), np.percentile(inside_depths, 90)
#     clean  = inside_depths[(inside_depths >= lo) & (inside_depths <= hi)]

#     if len(clean) < 3:
#         return None, 0

#     return float(np.percentile(clean, percentile)), len(clean)


# # ─── MAIN ────────────────────────────────────────────────────────────────────
# def run_frame(frame_id):
#     img_path = os.path.join(cfg.LENS1_DIR, f"frame_{frame_id:06d}.jpg")
#     out_dir  = cfg.OUT_DIR
#     os.makedirs(out_dir, exist_ok=True)

#     print(f"[perceive] loading: {img_path}")
#     img = cv2.imread(img_path)
#     if img is None:
#         raise FileNotFoundError(f"Image not found: {img_path}")

#     img_h, img_w = img.shape[:2]

#     # ── DETECTION ─────────────────────────────────────────────────────────
#     detections = detect_buildings(img, img_w, img_h)
#     if not detections:
#         print("[perceive] ❌ No buildings detected")
#         return None

#     x1, y1, x2, y2, det_conf = detections[0]
#     bbox = [int(x1), int(y1), int(x2), int(y2)]
#     print(f"[perceive] best detection: conf={det_conf:.2f} bbox={bbox}")

#     # ── SAM SEGMENTATION ──────────────────────────────────────────────────
#     print("[perceive] running SAM...")
#     sam        = SAM(cfg.SAM_MODEL)
#     target_box = np.array([[x1, y1, x2, y2]])
#     sam_res    = sam(img_path, bboxes=target_box, verbose=False)

#     if sam_res[0].masks is not None:
#         raw_mask = sam_res[0].masks.data[0].cpu().numpy().astype(np.float32)
#         mask     = cv2.resize(raw_mask, (img_w, img_h), interpolation=cv2.INTER_NEAREST)
#         mask     = (mask > 0.5).astype(np.uint8)

#         # Remove vehicle interior (left 38%) and ground plane (bottom 15%)
#         mask[:, :int(img_w * 0.38)]  = 0
#         mask[int(img_h * 0.85):, :]  = 0

#         # Morphological cleanup
#         kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
#         mask   = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
#         mask   = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  kernel)
#     else:
#         print("[perceive] SAM returned no mask — using bbox region")
#         mask = np.zeros((img_h, img_w), dtype=np.uint8)
#         mask[int(y1):int(y2), int(x1):int(x2)] = 1

#     # ── LIDAR LOADING + PROJECTION ────────────────────────────────────────
#     print("[perceive] loading PCAP...")
#     pts = lidar_pcap.load_both(cfg.L1_PCAP_PATH, cfg.L2_PCAP_PATH)
#     if pts is None or len(pts) == 0:
#         print("[perceive] ❌ No LiDAR points loaded")
#         return None

#     print(f"[perceive] {len(pts):,} LiDAR points loaded")

#     proj         = CalibratedProjector()
#     u, v, depths = proj.project(pts, img_h, img_w)
#     print(f"[perceive] {len(u):,} points projected into frame")

#     # DEBUG: confirm points land near the bbox
#     in_bbox = (u >= x1) & (u <= x2) & (v >= y1) & (v <= y2)
#     print(f"[perceive] pts in bbox region: {in_bbox.sum()},  mask sum: {mask.sum()}")

#     # ── DEPTH EXTRACTION ──────────────────────────────────────────────────
#     depth_m, n_pts = extract_depth_in_mask(u, v, depths, mask, img_h, img_w)

#     if depth_m is None or n_pts < 3:
#         print("[perceive] ⚠️  sparse mask depth — falling back to bbox-strip depth")
#         cx       = int((x1 + x2) / 2)
#         strip_w  = int((x2 - x1) * 0.3)
#         in_strip = (
#             (u >= cx - strip_w) & (u <= cx + strip_w) &
#             (v >= y1) & (v <= y2) &
#             (depths > 1.5)
#         )
#         strip_depths = depths[in_strip]
#         if len(strip_depths) > 2:
#             depth_m = float(np.percentile(strip_depths, 40))
#             n_pts   = len(strip_depths)
#         else:
#             depth_m = float(np.mean(depths[(depths > 2) & (depths < 80)])) if len(depths) > 0 else 25.0
#             n_pts   = 0

#     print(f"[perceive] depth={depth_m:.2f}m ({n_pts} pts)")

#     # ── VISUALIZATION ─────────────────────────────────────────────────────
#     vis   = img.copy()
#     max_d = 60.0

#     for pu, pv, pd in zip(u.astype(int), v.astype(int), depths):
#         if 0 <= pu < img_w and 0 <= pv < img_h:
#             t     = min(pd / max_d, 1.0)
#             color = (int(255 * (1 - t)), 50, int(255 * t))
#             cv2.circle(vis, (pu, pv), 2, color, -1)

#     overlay = vis.copy()
#     overlay[mask > 0] = (
#         overlay[mask > 0] * 0.5 + np.array([0, 200, 0]) * 0.5
#     ).astype(np.uint8)
#     vis = overlay

#     cv2.rectangle(vis, (bbox[0], bbox[1]), (bbox[2], bbox[3]), (0, 255, 255), 3)

#     info_lines = [
#         f"Depth: {depth_m:.1f}m",
#         f"Det conf: {det_conf:.2f}",
#         f"LiDAR pts in mask: {n_pts}",
#         f"Frame: {frame_id}"
#     ]
#     for i, line in enumerate(info_lines):
#         cv2.putText(vis, line, (20, 40 + i * 35),
#                     cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 4)
#         cv2.putText(vis, line, (20, 40 + i * 35),
#                     cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

#     vis_path = os.path.join(out_dir, f"frame_{frame_id:06d}_perceive_vis.jpg")
#     cv2.imwrite(vis_path, vis)

#     # ── OUTPUT JSON ───────────────────────────────────────────────────────
#     out = {
#         "frame_id":    frame_id,
#         "bbox":        bbox,
#         "bbox_px":     bbox,       # alias so match.py works with either key
#         "det_conf":    det_conf,
#         "median_depth": depth_m,
#         "depth_pts":   n_pts,
#         "img_w":       img_w,
#         "img_h":       img_h,
#         "vis":         vis_path,   # run.py reads this for the final visual
#     }
#     out_path = os.path.join(out_dir, f"frame_{frame_id:06d}_perceive.json")
#     with open(out_path, "w") as f:
#         json.dump(out, f, indent=2)

#     print(f"[perceive] depth={depth_m:.2f}m → {out_path}")
#     return out


# if __name__ == "__main__":
#     import argparse
#     ap = argparse.ArgumentParser()
#     ap.add_argument("--frame", type=int, default=840)
#     args = ap.parse_args()
#     run_frame(args.frame)


import os
import json
import argparse
import numpy as np
import cv2
from ultralytics import YOLO, SAM
import cfg
import lidar_pcap


class CalibratedProjector:
    def __init__(self):
        self._K = np.array([
            [cfg.FX,   0.0, cfg.CX],
            [  0.0, cfg.FY, cfg.CY],
            [  0.0,   0.0,    1.0 ]
        ], dtype=np.float64)

        self._T = np.array(cfg.T_LIDAR_TO_CAM, dtype=np.float64)

    def project(self, pts_xyz, img_h, img_w):
        N    = len(pts_xyz)
        ones = np.ones((N, 1), dtype=np.float64)
        pts_h = np.hstack([pts_xyz.astype(np.float64), ones])

        cam     = (self._T @ pts_h.T).T
        x, y, z = cam[:, 0], cam[:, 1], cam[:, 2]

        valid = (
        (z > 1.5)           &
        (z < 80.0)          &   # was 150, tighter
        (np.abs(x) < 50.0)  &   # was 80
        (y > -1.5)          &   # was -3.0, removes more ground
        (y < 12.0)              # was 20.0, removes sky/flyover beams
    )
        x, y, z = x[valid], y[valid], z[valid]

        u = self._K[0, 0] * x / z + self._K[0, 2]
        v = self._K[1, 1] * y / z + self._K[1, 2]

        in_frame = (u >= 0) & (u < img_w) & (v >= 0) & (v < img_h)
        return u[in_frame], v[in_frame], z[in_frame]


def _detect(yolo, img, classes, conf, crop=None):
    src = img
    ox, oy = 0, 0
    if crop is not None:
        x1c, y1c, x2c, y2c = crop
        src = img[y1c:y2c, x1c:x2c]
        ox, oy = x1c, y1c
    yolo.set_classes(classes)
    res   = yolo(src, conf=conf, iou=cfg.YOLO_IOU, verbose=False)
    boxes = res[0].boxes.xyxy.cpu().numpy()
    confs = res[0].boxes.conf.cpu().numpy()
    if crop is not None and len(boxes):
        boxes[:, [0, 2]] += ox
        boxes[:, [1, 3]] += oy
    return boxes, confs


def _best_building_box(boxes, confs, img_w, img_h):
    scored = []
    for box, c in zip(boxes, confs):
        x1, y1, x2, y2 = box
        cx   = (x1 + x2) / 2
        cy   = (y1 + y2) / 2
        area = (x2 - x1) * (y2 - y1) / (img_w * img_h)

        if area < 0.003:
            continue
        if y2 < img_h * 0.20:
            continue
        # skip car interior zone — left 35% lower 50%
        if cx < img_w * 0.35 and cy > img_h * 0.50:
            continue

        # prefer boxes on right half (building side for this rig)
        side_bonus = 0.15 if cx > img_w * 0.50 else 0.0
        score = float(c) + area * 2.0 + side_bonus
        scored.append((score, box, float(c)))

    if not scored:
        return None, None
    scored.sort(reverse=True)
    return scored[0][1], scored[0][2]


def detect_building(img, img_w, img_h):
    yolo = YOLO(cfg.YOLO_MODEL)

    # Pass 1 — full image, primary classes
    boxes, confs = _detect(yolo, img, cfg.YOLO_CLASSES, cfg.YOLO_CONF)
    box, c = _best_building_box(boxes, confs, img_w, img_h)
    if box is not None:
        print(f"[detect] pass 1 hit  conf={c:.2f}")
        return box, c

    # Pass 2 — full image, fallback classes
    print("[detect] pass 2 — fallback")
    boxes, confs = _detect(yolo, img, cfg.FALLBACK_CLASSES, cfg.FALLBACK_CONF)
    box, c = _best_building_box(boxes, confs, img_w, img_h)
    if box is not None:
        print(f"[detect] pass 2 hit  conf={c:.2f}")
        return box, c

    # Pass 3 — right 60% crop
    print("[detect] pass 3 — right crop")
    crop = (int(img_w * 0.40), 0, img_w, img_h)
    boxes, confs = _detect(yolo, img, cfg.FALLBACK_CLASSES, cfg.FALLBACK_CONF * 0.7, crop)
    box, c = _best_building_box(boxes, confs, img_w, img_h)
    if box is not None:
        print(f"[detect] pass 3 hit  conf={c:.2f}")
        return box, c

    # Pass 4 — centre strip (catches buildings directly ahead)
    print("[detect] pass 4 — centre strip")
    crop = (int(img_w * 0.25), 0, int(img_w * 0.75), img_h)
    boxes, confs = _detect(yolo, img, cfg.FALLBACK_CLASSES, cfg.FALLBACK_CONF * 0.6, crop)
    box, c = _best_building_box(boxes, confs, img_w, img_h)
    if box is not None:
        print(f"[detect] pass 4 hit  conf={c:.2f}")
        return box, c

    return None, None


def _depth_from_mask(u, v, depths, mask, img_h, img_w):
    u_i = np.clip(u.astype(int), 0, img_w - 1)
    v_i = np.clip(v.astype(int), 0, img_h - 1)
    inside = mask[v_i, u_i] > 0
    d = depths[inside]
    if len(d) < 5:
        return None, 0
    lo, hi = np.percentile(d, 5), np.percentile(d, 95)
    d = d[(d >= lo) & (d <= hi)]
    if len(d) < 3:
        return None, 0
    return float(np.percentile(d, 35)), len(d)


# def _depth_fallback(u, v, depths, x1, y1, x2, y2):
#     cx      = (x1 + x2) / 2
#     sw      = (x2 - x1) * 0.25
#     in_strip = (
#         (u >= cx - sw) & (u <= cx + sw) &
#         (v >= y1) & (v <= y2) &
#         (depths > 1.5) & (depths < 120.0)
#     )
#     d = depths[in_strip]
#     if len(d) > 3:
#         return float(np.percentile(d, 35)), len(d)
#     valid = depths[(depths > 2.0) & (depths < 80.0)]
#     if len(valid) > 0:
#         return float(np.percentile(valid, 40)), 0
#     return 25.0, 0
def _depth_fallback(u, v, depths, x1, y1, x2, y2):
    # Use only the middle 20% width, middle 60% height of bbox
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    sw = (x2 - x1) * 0.10   # tighter strip
    sh = (y2 - y1) * 0.30
    in_strip = (
        (u >= cx - sw) & (u <= cx + sw) &
        (v >= cy - sh) & (v <= cy + sh) &
        (depths > 2.0) & (depths < 80.0)
    )
    d = depths[in_strip]
    if len(d) > 3:
        return float(np.percentile(d, 35)), len(d)
    # wider fallback
    in_bbox = (
        (u >= x1) & (u <= x2) &
        (v >= y1) & (v <= y2) &
        (depths > 2.0) & (depths < 80.0)
    )
    d2 = depths[in_bbox]
    if len(d2) > 3:
        return float(np.percentile(d2, 35)), len(d2)
    valid = depths[(depths > 2.0) & (depths < 80.0)]
    return (float(np.percentile(valid, 40)), 0) if len(valid) > 0 else (25.0, 0)


def run_frame(frame_id):
    os.makedirs(cfg.OUT_DIR, exist_ok=True)

    img_path = os.path.join(cfg.LENS1_DIR, f"frame_{frame_id:06d}.jpg")
    print(f"[perceive] loading: {img_path}")
    img = cv2.imread(img_path)
    if img is None:
        raise FileNotFoundError(f"Image not found: {img_path}")

    img_h, img_w = img.shape[:2]

    raw_path = os.path.join(cfg.OUT_DIR, f"raw/frame_{frame_id:06d}_raw.jpg")
    cv2.imwrite(raw_path, img)

    box, det_conf = detect_building(img, img_w, img_h)
    if box is None:
        print("[perceive] no building detected")
        return None

    x1, y1, x2, y2 = [int(v) for v in box]
    bbox = [x1, y1, x2, y2]
    print(f"[perceive] bbox={bbox}  conf={det_conf:.2f}")

    print("[perceive] running SAM...")
    sam     = SAM(cfg.SAM_MODEL)
    sam_res = sam(img_path, bboxes=np.array([[x1, y1, x2, y2]]), verbose=False)

    if sam_res[0].masks is not None:
        raw_mask = sam_res[0].masks.data[0].cpu().numpy().astype(np.float32)
        mask     = cv2.resize(raw_mask, (img_w, img_h), interpolation=cv2.INTER_NEAREST)
        mask     = (mask > 0.5).astype(np.uint8)
        # mask[:, :int(img_w * 0.35)] = 0
        # mask[int(img_h * 0.88):, :] = 0
        # After SAM mask generation, before morphological ops:
        mask[:int(y1), :] = 0          # nothing above detection box
        mask[:int(img_h * 0.15), :] = 0  # hard sky cutoff
        k    = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  k)
    else:
        mask = np.zeros((img_h, img_w), dtype=np.uint8)
        mask[y1:y2, x1:x2] = 1

    print("[perceive] loading PCAP...")
    pts = lidar_pcap.load_both(cfg.L1_PCAP_PATH, cfg.L2_PCAP_PATH)
    if pts is None or len(pts) == 0:
        print("[perceive] no LiDAR points")
        return None
    print(f"[perceive] {len(pts):,} LiDAR points")

    proj         = CalibratedProjector()
    u, v, depths = proj.project(pts, img_h, img_w)
    print(f"[perceive] {len(u):,} projected  mask_px={mask.sum()}")

    depth_m, n_pts = _depth_from_mask(u, v, depths, mask, img_h, img_w)
    if depth_m is None:
        print("[perceive] sparse mask — bbox strip fallback")
        depth_m, n_pts = _depth_fallback(u, v, depths, x1, y1, x2, y2)

    print(f"[perceive] depth={depth_m:.2f}m  pts={n_pts}")

    vis = img.copy()

    step = max(1, len(u) // 40000)
    us, vs, ds = u[::step], v[::step], depths[::step]
    for pu, pv, pd in zip(us.astype(int), vs.astype(int), ds):
        if 0 <= pu < img_w and 0 <= pv < img_h:
            t     = min(pd / 80.0, 1.0)
            color = (int(255*(1-t)), 80, int(255*t))
            cv2.circle(vis, (pu, pv), 1, color, -1)

    overlay = vis.copy()
    overlay[mask > 0] = (overlay[mask > 0] * 0.45 + np.array([0, 210, 0]) * 0.55).astype(np.uint8)
    vis = overlay

    for pu, pv in zip(u.astype(int)[::step], v.astype(int)[::step]):
        if 0 <= pu < img_w and 0 <= pv < img_h and mask[pv, pu]:
            cv2.circle(vis, (pu, pv), 2, (0, 0, 255), -1)

    cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 255), 3)

    for i, line in enumerate([
        f"Depth: {depth_m:.1f}m",
        f"Det conf: {det_conf:.2f}",
        f"LiDAR pts: {n_pts}",
        f"Frame: {frame_id}"
    ]):
        cv2.putText(vis, line, (22, 44 + i*36), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0,0,0), 4)
        cv2.putText(vis, line, (22, 44 + i*36), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255,255,255), 2)

    vis_path = os.path.join(cfg.OUT_DIR, f"perceive_vis/frame_{frame_id:06d}_perceive_vis.jpg")
    cv2.imwrite(vis_path, vis)

    out = {
        "frame_id":     frame_id,
        "bbox":         bbox,
        "bbox_px":      bbox,
        "det_conf":     det_conf,
        "median_depth": depth_m,
        "depth_pts":    n_pts,
        "img_w":        img_w,
        "img_h":        img_h,
        "vis":          vis_path
    }
    out_path = os.path.join(cfg.OUT_DIR, f"perceive_json/frame_{frame_id:06d}_perceive.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    print(f"[perceive] → {out_path}")
    return out


def scan_frames(start, end):
    yolo = YOLO(cfg.YOLO_MODEL)
    print(f"[perceive] scanning {start}–{end}...")
    for fid in range(start, end + 1):
        img_path = os.path.join(cfg.LENS1_DIR, f"frame_{fid:06d}.jpg")
        img = cv2.imread(img_path)
        if img is None:
            print(f"  {fid:06d}: missing")
            continue
        img_h, img_w = img.shape[:2]
        box, c = detect_building(img, img_w, img_h)
        status = f"conf={c:.2f} bbox={[int(v) for v in box]}" if box is not None else "none"
        print(f"  {fid:06d}: {status}")
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