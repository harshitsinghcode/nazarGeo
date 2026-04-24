import os
import json
import math
import datetime
import numpy as np
import re
import cfg

MATCH_DIR   = os.path.join(cfg.OUT_DIR, "match_json")
PROJECT_DIR = os.path.join(cfg.OUT_DIR, "project_json")
RESULTS_JSON = os.path.join(cfg.OUT_DIR, "calibration_results.json")

CURATED_FRAMES = [76, 151, 226, 276, 401, 626, 1826, 3351]

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a  = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def heading_unit_vector(hdg_deg):
    h = math.radians(hdg_deg)
    return math.cos(h), math.sin(h)

def m_to_deg(north_m, east_m, ref_lat=12.945):
    dlat = north_m / 111320.0
    dlon = east_m  / (111320.0 * math.cos(math.radians(ref_lat)))
    return dlat, dlon

def apply_correction(ego_lat, ego_lon, hdg_deg, raw_depth, along_off, cross_off):
    corrected_depth = max(1.0, raw_depth + along_off)
    lat_angle = math.degrees(math.atan2(cross_off, corrected_depth))
    new_hdg   = (hdg_deg + lat_angle) % 360.0
    rn, re    = heading_unit_vector(new_hdg)
    dlat, dlon = m_to_deg(corrected_depth * rn, corrected_depth * re)
    return ego_lat + dlat, ego_lon + dlon

def _parse_poly(wkt):
    if not wkt: return []
    m = re.search(r"POLYGON\s*\(\((.*?)\)\)", wkt, re.IGNORECASE | re.DOTALL)
    if not m: return []
    pts = []
    for pair in m.group(1).split(","):
        p = pair.strip().split()
        if len(p) >= 2:
            pts.append((float(p[0]), float(p[1])))
    return pts

def _point_in_poly(px, py, pts):
    inside = False
    n, j = len(pts), len(pts) - 1
    for i in range(n):
        xi, yi = pts[i]; xj, yj = pts[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi)*(py - yi)/(yj - yi) + xi):
            inside = not inside
        j = i
    return inside

def polygon_error(tlat, tlon, wkt, gob_lat, gob_lon):
    pts = _parse_poly(wkt)
    if len(pts) < 3:
        return haversine_m(tlat, tlon, gob_lat, gob_lon)
    if _point_in_poly(tlon, tlat, pts):
        return 0.0
    min_d = float("inf")
    for i in range(len(pts) - 1):
        alon, alat = pts[i]; blon, blat = pts[i+1]
        dx, dy = blon - alon, blat - alat
        sq = dx*dx + dy*dy
        if sq == 0:
            d = haversine_m(tlat, tlon, alat, alon)
        else:
            t = max(0.0, min(1.0, ((tlon-alon)*dx + (tlat-alat)*dy) / sq))
            d = haversine_m(tlat, tlon, alat + t*dy, alon + t*dx)
        if d < min_d: min_d = d
    return min_d

def load_curated_frames():
    records = []
    for fid in CURATED_FRAMES:
        mpath = os.path.join(MATCH_DIR,   f"frame_{fid:06d}_match.json")
        ppath = os.path.join(PROJECT_DIR, f"frame_{fid:06d}_project.json")
        if not os.path.exists(mpath) or not os.path.exists(ppath):
            continue
        with open(mpath) as f: md  = json.load(f)
        with open(ppath) as f: pd_ = json.load(f)
        best = md.get("best_match")
        if not best:
            continue
        records.append({
            "fid":       fid,
            "ego_lat":   pd_["ego_lat"],
            "ego_lon":   pd_["ego_lon"],
            "heading":   pd_["heading_deg"],
            "raw_depth": pd_.get("raw_depth_m", pd_["depth_m"]),
            "gob_lat":   best["centroid_lat"],
            "gob_lon":   best["centroid_lon"],
            "geometry":  best.get("geometry", ""),
        })
    return records

FLOOR_M       = 4.5
OUTLIER_SCALE = 2.0

def _threshold(arr):
    med = float(np.median(arr))
    return max(OUTLIER_SCALE * med, FLOOR_M), med

def evaluate_offset(records, along, cross):
    errors = [polygon_error(
        *apply_correction(r["ego_lat"], r["ego_lon"], r["heading"], r["raw_depth"], along, cross),
        r["geometry"], r["gob_lat"], r["gob_lon"]
    ) for r in records]

    arr = np.array(sorted(errors))
    thr, _ = _threshold(arr)
    inliers = arr[arr <= thr]
    if len(inliers) == 0:
        inliers = arr

    return (float(np.mean(inliers)),
            float(np.median(inliers)),
            int(np.sum(inliers == 0.0)))

def frame_breakdown(records, along, cross):
    rows = []
    raw_errors = []
    for r in records:
        clat, clon = apply_correction(
            r["ego_lat"], r["ego_lon"], r["heading"], r["raw_depth"], along, cross)
        err = polygon_error(clat, clon, r["geometry"], r["gob_lat"], r["gob_lon"])
        raw_errors.append(err)
        rows.append({"fid": r["fid"], "err": err})

    arr = np.array(raw_errors)
    thr, med = _threshold(arr)

    result = []
    for row in rows:
        is_inlier = row["err"] <= thr
        result.append({
            "frame_id":          row["fid"],
            "calibrated_error_m": round(row["err"], 3),
            "is_inlier":         is_inlier,
            "is_polygon_hit":    row["err"] == 0.0,
        })
    return result, round(thr, 2), round(med, 3)

def print_frame_table(breakdown, thr):
    print(f"\n{'Frame':>8}  {'Error (m)':>10}  Status")
    print("-" * 46)
    for r in sorted(breakdown, key=lambda x: x["calibrated_error_m"]):
        err = r["calibrated_error_m"]
        if r["is_polygon_hit"]:
            tag = "OK  inside polygon"
        elif r["is_inlier"]:
            tag = f"OK  inlier  (<= {thr}m)"
        else:
            tag = f"BAD outlier (> {thr}m) -- wrong GOB match?"
        print(f"{r['frame_id']:>8}  {err:>10.2f}  {tag}")

def save_results(along, cross, mean_e, med_e, hits, frames, thr, group_med, target_achieved):
    payload = {
        "timestamp":          datetime.datetime.now().isoformat(timespec="seconds"),
        "along_offset_m":     round(along, 2),
        "cross_offset_m":     round(cross, 2),
        "inlier_mean_m":      round(mean_e, 3),
        "inlier_median_m":    round(med_e,  3),
        "inlier_threshold_m": thr,
        "group_median_m":     group_med,
        "sub3m_hits":         hits,
        "total_frames":       len(frames),
        "inlier_count":       sum(1 for f in frames if f["is_inlier"]),
        "target_achieved":    target_achieved,
        "frames":             frames,
    }
    os.makedirs(os.path.dirname(RESULTS_JSON), exist_ok=True)
    with open(RESULTS_JSON, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"\nCalibration results saved -> {RESULTS_JSON}")

def main():
    print("Loading data...")
    records = load_curated_frames()
    print(f"Loaded {len(records)} valid frames.")
    if not records:
        print("No records found. Run presniff.py for the curated frames first.")
        return

    best_mean  = float("inf")
    best_med   = float("inf")
    best_along = 0.0
    best_cross = 0.0
    best_hits  = 0
    combo_n    = 0

    along_range = np.arange(25.0, 55.0, 0.5)
    cross_range = np.arange(-6.0,  6.0, 0.2)
    total       = len(along_range) * len(cross_range)

    print(f"\nStarting Aggressive Sub-3m Search ({total} combinations)...")

    target_achieved = False
    for along in along_range:
        for cross in cross_range:
            combo_n += 1
            mean_e, med_e, hits = evaluate_offset(records, along, cross)

            if mean_e < best_mean:
                best_mean  = mean_e
                best_med   = med_e
                best_along = along
                best_cross = cross
                best_hits  = hits
                print(
                    f"[{combo_n}/{total}] New Best! "
                    f"Along: {along:+.1f}m, Cross: {cross:+.1f}m -> "
                    f"Inlier Mean: {mean_e:.2f}m  (Med: {med_e:.2f}m, Hits: {hits})"
                )

            if best_mean < 3.0 and best_med < 3.0:
                target_achieved = True
                break
        if target_achieved:
            print("\nTARGET ACHIEVED: BOTH MEAN & MEDIAN UNDER 3.0 m!")
            break

    print("\n" + "="*52)
    print("OPTIMIZATION COMPLETE")
    print("="*52)
    print(f"Best Along Offset  : {best_along:+.2f} m")
    print(f"Best Cross Offset  : {best_cross:+.2f} m")
    print(f"Final Inlier Mean  : {best_mean:.2f} m")
    print(f"Final Median Error : {best_med:.2f} m")
    print(f"Sub-3m Hits        : {best_hits} inliers with 0 m error")

    if not target_achieved:
        print("\nWARNING: Sub-3m mean not reached. Check frame breakdown for bad GOB matches.")

    breakdown, thr, group_med = frame_breakdown(records, best_along, best_cross)
    print_frame_table(breakdown, thr)
    print(f"\n  Group median: {group_med}m  =>  inlier threshold: {thr}m")

    save_results(best_along, best_cross, best_mean, best_med,
                 best_hits, breakdown, thr, group_med, target_achieved)

    print("\nPaste these directly into cfg.py:")
    print(f"ALONG_RAY_OFFSET_M = {best_along:.2f}")
    print(f"CROSS_RAY_OFFSET_M = {best_cross:.2f}")

if __name__ == "__main__":
    main()