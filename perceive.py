import os
import re
import json
import argparse
import numpy as np
import cv2
from ultralytics import YOLO, SAM
import cfg

FALLBACK_CLASSES = [
    "building", "house", "commercial building", "brick wall", "facade",
    "wall", "structure", "apartment", "office building", "storefront",
    "architecture", "construction"
]
FALLBACK_CONF = 0.05


def _read_calib(path):
    data = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or ":" not in line:
                continue
            key, val = line.split(":", 1)
            key, val = key.strip(), val.strip()
            if val and val[0].isalpha():
                continue
            nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", val)
            if nums:
                data[key] = np.array([float(x) for x in nums])
    return data


def _get_mat(d, keys, shape):
    for k in keys:
        if k in d and d[k].size == np.prod(shape):
            return d[k].reshape(shape)
    raise KeyError(f"None of {keys} found in calibration. Available: {list(d.keys())}")


class Projector:
    def __init__(self, calib_dir):
        cam = _read_calib(os.path.join(calib_dir, "calib_cam_to_cam.txt"))
        vel = _read_calib(os.path.join(calib_dir, "calib_velo_to_cam.txt"))

        P2 = _get_mat(cam, ["P_rect_02", "P_rect_2", "P2"], (3, 4))
        R0 = _get_mat(cam, ["R_rect_00", "R_rect_0", "R0_rect"], (3, 3))
        R  = _get_mat(vel, ["R"], (3, 3))
        T  = _get_mat(vel, ["T"], (3, 1))

        Tr = np.eye(4)
        Tr[:3, :] = np.hstack((R, T))

        R0_4 = np.eye(4)
        R0_4[:3, :3] = R0

        self._full = P2 @ R0_4 @ Tr

    def project(self, pts, img_shape):
        xyz1 = np.hstack((pts[:, :3], np.ones((len(pts), 1))))
        proj = (self._full @ xyz1.T).T
        d = proj[:, 2]
        u = proj[:, 0] / d
        v = proj[:, 1] / d
        h, w = img_shape[:2]
        mask = (d > 0) & (u >= 0) & (u < w) & (v >= 0) & (v < h)
        return u[mask], v[mask], d[mask]


def _detect(yolo, img, classes, conf):
    yolo.set_classes(classes)
    results = yolo(img, conf=conf, iou=cfg.YOLO_IOU, verbose=False)
    boxes     = results[0].boxes.xyxy.cpu().numpy()
    class_ids = results[0].boxes.cls.cpu().numpy()
    return boxes, class_ids


def _process_detections(frame_id, entry, img, boxes, class_ids, active_classes):
    img_path   = entry["camera_data"]["path"]
    lidar_path = entry["lidar_data"]["path"]

    sam = SAM(cfg.SAM_MODEL)
    sam_res = sam(img_path, bboxes=boxes, verbose=False)
    masks = sam_res[0].masks.data.cpu().numpy()

    master = np.any(masks, axis=0)
    master = cv2.resize(master.astype(np.uint8), (img.shape[1], img.shape[0])) > 0

    proj = Projector(cfg.KITTI_CALIB_DIR)
    pts  = np.fromfile(lidar_path, dtype=np.float32).reshape(-1, 4)
    u, v, depths = proj.project(pts, img.shape)

    inside_depths = [depths[i] for i in range(len(u)) if master[int(v[i]), int(u[i])]]

    if not inside_depths:
        print(f"[perceive] frame {frame_id}: detections found but no LiDAR points inside mask")
        return None

    median_depth = float(np.median(inside_depths))

    largest_box = boxes[int(np.argmax(
        [(b[2]-b[0]) * (b[3]-b[1]) for b in boxes]
    ))]
    bbox_px = [float(x) for x in largest_box]
    img_w   = img.shape[1]

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

    cv2.putText(vis, f"depth: {median_depth:.2f}m", (30, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

    vis_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:04d}_vis.jpg")
    cv2.imwrite(vis_path, vis)

    out = {
        "frame_id":     frame_id,
        "median_depth": median_depth,
        "bbox_px":      bbox_px,
        "img_w":        img_w,
        "vis":          vis_path
    }
    out_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:04d}_perceive.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    print(f"[perceive] frame {frame_id}: depth={median_depth:.2f}m  detections={len(boxes)} → {out_path}")
    return out


def run_frame(frame_id):
    with open(cfg.MANIFEST_PATH) as f:
        manifest = json.load(f)

    entry = next((r for r in manifest if r["frame_id"] == frame_id), None)
    if entry is None:
        raise ValueError(f"Frame {frame_id} not in manifest")

    img_path = entry["camera_data"]["path"]
    print(f"[perceive] loading image: {img_path}")

    img = cv2.imread(img_path)
    if img is None:
        raise FileNotFoundError(f"Image not found: {img_path}")

    raw_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:04d}_raw.jpg")
    cv2.imwrite(raw_path, img)
    print(f"[perceive] raw frame saved → {raw_path}")

    yolo = YOLO(cfg.YOLO_MODEL)

    print(f"[perceive] pass 1 — primary classes @ conf={cfg.YOLO_CONF}")
    boxes, class_ids = _detect(yolo, img, cfg.YOLO_CLASSES, cfg.YOLO_CONF)

    if len(boxes) == 0:
        print(f"[perceive] pass 1 found nothing — pass 2: fallback classes @ conf={FALLBACK_CONF}")
        boxes, class_ids = _detect(yolo, img, FALLBACK_CLASSES, FALLBACK_CONF)
        active_classes = FALLBACK_CLASSES
    else:
        active_classes = cfg.YOLO_CLASSES

    if len(boxes) == 0:
        print(f"[perceive] frame {frame_id}: both passes found no detections")
        print(f"[perceive] check raw frame at: {raw_path}")
        return None

    print(f"[perceive] {len(boxes)} detection(s) — passing to SAM")
    return _process_detections(frame_id, entry, img, boxes, class_ids, active_classes)


def scan_for_detections(start=0, end=20):
    with open(cfg.MANIFEST_PATH) as f:
        manifest = json.load(f)

    yolo = YOLO(cfg.YOLO_MODEL)

    print(f"[perceive] scanning frames {start}–{end} for first usable detection...")
    for fid in range(start, end + 1):
        entry = next((r for r in manifest if r["frame_id"] == fid), None)
        if entry is None:
            continue
        img = cv2.imread(entry["camera_data"]["path"])
        if img is None:
            continue

        boxes, _ = _detect(yolo, img, cfg.YOLO_CLASSES, cfg.YOLO_CONF)
        if len(boxes) == 0:
            boxes, _ = _detect(yolo, img, FALLBACK_CLASSES, FALLBACK_CONF)

        status = f"{len(boxes)} det" if len(boxes) > 0 else "none"
        print(f"  frame {fid:03d}: {status}")

    print("[perceive] scan complete — re-run with the best frame using --frame N")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", type=int, default=5)
    ap.add_argument("--scan", action="store_true", help="Scan frames 0-20 and report detection counts")
    ap.add_argument("--scan-end", type=int, default=20)
    args = ap.parse_args()

    if args.scan:
        scan_for_detections(0, args.scan_end)
    else:
        run_frame(args.frame)