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
            (z < 80.0)          &
            (np.abs(x) < 50.0)  &
            (y > -1.5)          &
            (y < 12.0)
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
        if cx < img_w * 0.35 and cy > img_h * 0.50:
            continue

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

    # Pass 4 — centre strip
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


def _depth_fallback(u, v, depths, x1, y1, x2, y2):
    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    sw = (x2 - x1) * 0.10
    sh = (y2 - y1) * 0.30
    in_strip = (
        (u >= cx - sw) & (u <= cx + sw) &
        (v >= cy - sh) & (v <= cy + sh) &
        (depths > 2.0) & (depths < 80.0)
    )
    d = depths[in_strip]
    if len(d) > 3:
        return float(np.percentile(d, 35)), len(d)
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
        mask[:int(y1), :] = 0
        mask[:int(img_h * 0.15), :] = 0
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