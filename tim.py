import os
import json
import math
import argparse
import re
from collections import defaultdict

import cfg


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin(math.radians(lat2-lat1)/2)**2
         + math.cos(p1)*math.cos(p2)*math.sin(math.radians(lon2-lon1)/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def parse_polygon(wkt):
    if not wkt: return []
    m = re.search(r"POLYGON\s*\(\((.*?)\)\)", wkt, re.IGNORECASE | re.DOTALL)
    if not m:
        nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", wkt)
        if len(nums) < 4: return []
        return [(float(nums[i]), float(nums[i+1])) for i in range(0, len(nums)-1, 2)]
    pts = []
    for pair in m.group(1).split(","):
        parts = pair.strip().split()
        if len(parts) >= 2:
            pts.append((float(parts[0]), float(parts[1])))
    return pts


def point_in_polygon(px, py, pts):
    inside = False; n = len(pts); j = n-1
    for i in range(n):
        xi, yi = pts[i]; xj, yj = pts[j]
        if ((yi > py) != (yj > py)) and (px < (xj-xi)*(py-yi)/(yj-yi)+xi):
            inside = not inside
        j = i
    return inside


def polygon_edge_error(tlat, tlon, wkt):
    pts = parse_polygon(wkt)
    if len(pts) < 3: return None
    if point_in_polygon(tlon, tlat, pts): return 0.0
    min_d = float("inf")
    for i in range(len(pts)-1):
        alon, alat = pts[i]; blon, blat = pts[i+1]
        dx = blon-alon; dy = blat-alat; sq = dx*dx+dy*dy
        if sq == 0:
            d = haversine_m(tlat, tlon, alat, alon)
        else:
            t = max(0.0, min(1.0, ((tlon-alon)*dx+(tlat-alat)*dy)/sq))
            d = haversine_m(tlat, tlon, alat+t*dy, alon+t*dx)
        if d < min_d: min_d = d
    return round(min_d, 2)


def accuracy_label(err_m):
    if err_m is None:  return "unknown"
    if err_m == 0.0:   return "INSIDE"
    if err_m < 3.0:    return "sub-3m"
    if err_m < 5.0:    return "excellent"
    if err_m < 10.0:   return "good"
    if err_m < 20.0:   return "fair"
    return "poor"


def gob_key(lat, lon):
    return f"{lat:.5f}_{lon:.5f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-score",    type=float, default=40.0)
    ap.add_argument("--per-building", action="store_true",
                    help="Deduplicate: use only the best-scoring frame per GOB building")
    ap.add_argument("--selected-only", action="store_true",
                    help="Only use frames in selected_buildings.json")
    args = ap.parse_args()

    match_dir   = os.path.join(cfg.OUT_DIR, "match_json")
    project_dir = os.path.join(cfg.OUT_DIR, "project_json")

    print()
    print("=" * 72)
    print("  NazarGeo — Offset Calibration & Error Evaluation")
    print("=" * 72)

    print()
    print("  Step 1 — scanning match_json files ...")
    if args.selected_only:
        sel_path = os.path.join(cfg.OUT_DIR, "selected_buildings.json")
        with open(sel_path) as f:
            sel = json.load(f)
        frame_ids = [b["frame_id"] for b in sel]
        print(f"  Using {len(frame_ids)} selected frames only")
    else:
        frame_ids = []
        for fname in sorted(os.listdir(match_dir)):
            if fname.endswith("_match.json"):
                try:
                    fid = int(fname.replace("frame_", "").replace("_match.json", ""))
                    frame_ids.append(fid)
                except: pass
        print(f"  Found {len(frame_ids)} match_json files")

    print(f"  Step 2 — loading (min_score >= {args.min_score}) ...")
    all_records = []

    for fid in frame_ids:
        mpath = os.path.join(match_dir,   f"frame_{fid:06d}_match.json")
        ppath = os.path.join(project_dir, f"frame_{fid:06d}_project.json")
        if not (os.path.exists(mpath) and os.path.exists(ppath)): continue

        with open(mpath) as f: md = json.load(f)
        with open(ppath) as f: pd = json.load(f)

        best = md.get("best_match")
        if best is None: continue
        score = best.get("score", 0)
        if score < args.min_score: continue

        raw_lat = pd.get("raw_target_lat") or (pd["target_lat"] - cfg.PROJECTION_LAT_OFFSET)
        raw_lon = pd.get("raw_target_lon") or (pd["target_lon"] - cfg.PROJECTION_LON_OFFSET)
        gob_lat = best["centroid_lat"]
        gob_lon = best["centroid_lon"]

        all_records.append({
            "frame_id":   fid,
            "raw_lat":    raw_lat,
            "raw_lon":    raw_lon,
            "gob_lat":    gob_lat,
            "gob_lon":    gob_lon,
            "dlat":       gob_lat - raw_lat,
            "dlon":       gob_lon - raw_lon,
            "score":      score,
            "geometry":   best.get("geometry", ""),
            "dist_m":     best.get("dist_m", 0),
            "angle_off":  best.get("angle_off_deg", 0),
            "gob_key":    gob_key(gob_lat, gob_lon),
        })

    n_raw = len(all_records)
    print(f"  Valid frames: {n_raw}")

    if n_raw == 0:
        print("  ERROR: no valid frames. Run presniff.py first or lower --min-score")
        return

    if args.per_building:
        by_building = defaultdict(list)
        for rec in all_records:
            by_building[rec["gob_key"]].append(rec)
        # Keep only best-scoring frame per building for offset computation
        calib_records = [max(recs, key=lambda r: r["score"]) for recs in by_building.values()]
        print(f"  Deduplicated to {len(calib_records)} unique buildings "
              f"(from {n_raw} frames)")
    else:
        calib_records = all_records

    print()
    print("  Step 3 — computing calibrated offset ...")
    dlats = [r["dlat"] for r in calib_records]
    dlons = [r["dlon"] for r in calib_records]
    n = len(dlats)

    avg_dlat = sum(dlats) / n
    avg_dlon = sum(dlons) / n
    std_dlat = math.sqrt(sum((d - avg_dlat)**2 for d in dlats) / max(n-1, 1))
    std_dlon = math.sqrt(sum((d - avg_dlon)**2 for d in dlons) / max(n-1, 1))

    lat_m = avg_dlat * 111320.0
    lon_m = avg_dlon * 111320.0 * math.cos(math.radians(12.945))

    print(f"    n_samples = {n}")
    print(f"    avg_dlat  = {avg_dlat:+.6f} deg  ({lat_m:+.2f} m)  ± {std_dlat:.6f}")
    print(f"    avg_dlon  = {avg_dlon:+.6f} deg  ({lon_m:+.2f} m)  ± {std_dlon:.6f}")
    print()
    print("  ── Copy to cfg.py: ──────────────────────────────────────────────")
    print(f"    PROJECTION_LAT_OFFSET = {avg_dlat:.6f}")
    print(f"    PROJECTION_LON_OFFSET = {avg_dlon:.6f}")
    print("  ─────────────────────────────────────────────────────────────────")

    print()
    print("  Step 4 — applying offset and computing errors ...")
    print()
    print(f"  {'Frame':>6}  {'Score':>6}  {'Dist':>5}  {'Ang':>5}  "
          f"{'RawErr':>8}  {'CorrErr':>8}  {'Impr':>7}  Label")
    print("  " + "─" * 76)

    raw_errors, corr_errors = [], []
    results = []

    for rec in sorted(all_records, key=lambda r: r["score"], reverse=True):
        fid      = rec["frame_id"]
        raw_lat  = rec["raw_lat"]
        raw_lon  = rec["raw_lon"]
        gob_lat  = rec["gob_lat"]
        gob_lon  = rec["gob_lon"]
        geom     = rec["geometry"]
        corr_lat = raw_lat + avg_dlat
        corr_lon = raw_lon + avg_dlon

        if geom:
            raw_err  = polygon_edge_error(raw_lat,  raw_lon,  geom)
            corr_err = polygon_edge_error(corr_lat, corr_lon, geom)
        else:
            raw_err  = round(haversine_m(raw_lat,  raw_lon,  gob_lat, gob_lon), 2)
            corr_err = round(haversine_m(corr_lat, corr_lon, gob_lat, gob_lon), 2)

        raw_err  = raw_err  if raw_err  is not None else 999.0
        corr_err = corr_err if corr_err is not None else 999.0
        impr     = raw_err - corr_err
        label    = accuracy_label(corr_err)
        flag     = "✓" if corr_err < raw_err else "✗"

        print(f"  {fid:>6}  {rec['score']:>6.1f}  "
              f"{rec['dist_m']:>4.0f}m  {rec['angle_off']:>4.1f}°  "
              f"{raw_err:>7.1f}m  {corr_err:>7.1f}m  "
              f"{impr:>+6.1f}m  [{label}] {flag}")

        raw_errors.append(raw_err)
        corr_errors.append(corr_err)
        results.append({
            "frame_id":          fid,
            "match_score":       rec["score"],
            "raw_error_m":       raw_err,
            "corrected_error_m": corr_err,
            "improvement_m":     round(impr, 2),
            "corrected_lat":     corr_lat,
            "corrected_lon":     corr_lon,
            "gob_lat":           gob_lat,
            "gob_lon":           gob_lon,
            "accuracy_label":    label,
            "gmaps": f"https://maps.google.com/?q={corr_lat:.8f},{corr_lon:.8f}",
        })

    print("  " + "─" * 76)
    avg_raw  = sum(raw_errors)  / len(raw_errors)
    avg_corr = sum(corr_errors) / len(corr_errors)
    pct      = 100 * (avg_raw - avg_corr) / avg_raw if avg_raw > 0 else 0

    by_bld = defaultdict(list)
    for r in results:
        mpath = os.path.join(match_dir, f"frame_{r['frame_id']:06d}_match.json")
        with open(mpath) as f: md = json.load(f)
        best = md["best_match"]
        by_bld[gob_key(best["centroid_lat"], best["centroid_lon"])].append(r["corrected_error_m"])
    bld_avg_errors = [sum(v)/len(v) for v in by_bld.values()]
    avg_per_building = sum(bld_avg_errors) / len(bld_avg_errors) if bld_avg_errors else 0

    print()
    print(f"  Frames evaluated            : {len(results)}")
    print(f"  Unique GOB buildings        : {len(by_bld)}")
    print(f"  Raw avg error               : {avg_raw:.2f} m")
    print(f"  Corrected avg error         : {avg_corr:.2f} m")
    print(f"  Per-building avg error      : {avg_per_building:.2f} m  ← best metric")
    print(f"  Improvement                 : {avg_raw-avg_corr:.2f} m  ({pct:.1f}% reduction)")
    print()
    inside    = sum(1 for e in corr_errors if e == 0)
    sub3      = sum(1 for e in corr_errors if 0 < e < 3)
    excellent = sum(1 for e in corr_errors if 3 <= e < 5)
    good      = sum(1 for e in corr_errors if 5 <= e < 10)
    fair      = sum(1 for e in corr_errors if 10 <= e < 20)
    poor      = sum(1 for e in corr_errors if e >= 20)
    print(f"  INSIDE footprint  (0m)  : {inside}")
    print(f"  sub-3m            (<3m) : {sub3}")
    print(f"  Excellent         (<5m) : {excellent}")
    print(f"  Good              (<10m): {good}")
    print(f"  Fair              (<20m): {fair}")
    print(f"  Poor              (≥20m): {poor}")
    print()

    print("  ── Path to sub-2m error ──────────────────────────────────────────")
    print(f"  Current per-building avg: {avg_per_building:.2f} m")
    if avg_per_building <= 2.0:
        print(f"  ✓ Already at sub-2m! Great accuracy.")
    elif avg_per_building <= 5.0:
        print(f"  → Run more frames (e.g. --step 25) for denser coverage")
        print(f"  → Run tim.py --per-building to reduce per-building bias")
        print(f"  → Update BUILDING_PENETRATION_OFFSET_M in cfg.py")
    else:
        print(f"  → Check perceive.py depth extraction quality")
        print(f"  → Try lowering PROX_DECAY_M in cfg.py")
        print(f"  → Increase data density: presniff.py --step 15")
    print()

    out = {
        "calibration": {
            "n_frames_used":       n,
            "n_buildings_covered": len(by_bld),
            "min_score_gate":      args.min_score,
            "per_building_dedup":  args.per_building,
            "avg_dlat":            avg_dlat,
            "avg_dlon":            avg_dlon,
            "std_dlat":            std_dlat,
            "std_dlon":            std_dlon,
            "offset_m_lat":        lat_m,
            "offset_m_lon":        lon_m,
            "cfg_lines": [
                f"PROJECTION_LAT_OFFSET = {avg_dlat:.6f}",
                f"PROJECTION_LON_OFFSET = {avg_dlon:.6f}",
            ],
        },
        "summary": {
            "total_frames":             len(results),
            "unique_buildings":         len(by_bld),
            "raw_avg_error_m":          round(avg_raw, 2),
            "corrected_avg_error_m":    round(avg_corr, 2),
            "per_building_avg_error_m": round(avg_per_building, 2),
            "improvement_m":            round(avg_raw - avg_corr, 2),
            "improvement_pct":          round(pct, 1),
            "inside":                   inside,
            "sub_3m":                   sub3,
            "excellent_lt5m":           excellent,
            "good_lt10m":               good,
        },
        "buildings": results,
    }

    out_path = os.path.join(cfg.OUT_DIR, "calibrated_results.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"  Saved → {out_path}")
    print("=" * 72)
    print()
    print("  Next — update cfg.py:")
    print(f"    PROJECTION_LAT_OFFSET = {avg_dlat:.6f}")
    print(f"    PROJECTION_LON_OFFSET = {avg_dlon:.6f}")
    print()


if __name__ == "__main__":
    main()