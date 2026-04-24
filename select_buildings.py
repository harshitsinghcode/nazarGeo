import os
import re
import json
import math
import argparse
from collections import defaultdict

import cfg

CURATED_FRAMES = [76, 151, 226, 276, 401, 626, 1826, 3351]


def _hav(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a  = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def _parse_polygon(geometry_wkt):
    if not geometry_wkt:
        return []
    m = re.search(r'POLYGON\s*\(\((.*?)\)\)', geometry_wkt, re.IGNORECASE | re.DOTALL)
    if not m:
        nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", geometry_wkt)
        if len(nums) < 4:
            return []
        pts = []
        for i in range(0, len(nums) - 1, 2):
            pts.append((float(nums[i]), float(nums[i + 1])))
        return pts
    pts = []
    for pair in m.group(1).split(','):
        parts = pair.strip().split()
        if len(parts) >= 2:
            pts.append((float(parts[0]), float(parts[1])))
    return pts


def _point_in_polygon(px, py, pts):
    inside = False
    n = len(pts)
    j = n - 1
    for i in range(n):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _pt_seg_dist_m(plat, plon, alat, alon, blat, blon):
    dx = blon - alon
    dy = blat - alat
    seg_sq = dx*dx + dy*dy
    if seg_sq == 0:
        return _hav(plat, plon, alat, alon)
    t = max(0.0, min(1.0, ((plon - alon)*dx + (plat - alat)*dy) / seg_sq))
    return _hav(plat, plon, alat + t*dy, alon + t*dx)


def error_to_polygon(target_lat, target_lon, geometry_wkt):
    pts = _parse_polygon(geometry_wkt)
    if len(pts) < 3:
        return None

    if _point_in_polygon(target_lon, target_lat, pts):
        return 0.0

    min_dist = float('inf')
    for i in range(len(pts) - 1):
        alon, alat = pts[i]
        blon, blat = pts[i+1]
        d = _pt_seg_dist_m(target_lat, target_lon, alat, alon, blat, blon)
        if d < min_dist:
            min_dist = d
    return round(min_dist, 2)


def polygon_centroid(geometry_wkt):
    pts = _parse_polygon(geometry_wkt)
    if not pts:
        return None, None
    lons = [p[0] for p in pts]
    lats = [p[1] for p in pts]
    return sum(lats)/len(lats), sum(lons)/len(lons)


def load_matches(match_dir, frame_ids):
    records = []
    for fid in frame_ids:
        path = os.path.join(match_dir, f"frame_{fid:06d}_match.json")
        if not os.path.exists(path):
            print(f"[select] WARNING: match_json missing for frame {fid}")
            continue
        with open(path) as f:
            data = json.load(f)
        best = data.get("best_match")
        if not best:
            continue

        proj_path = os.path.join(cfg.OUT_DIR, "project_json",
                                 f"frame_{fid:06d}_project.json")
        ego_lat = ego_lon = heading = target_lat = target_lon = None
        if os.path.exists(proj_path):
            with open(proj_path) as f:
                pd_ = json.load(f)
            ego_lat    = pd_.get("ego_lat")
            ego_lon    = pd_.get("ego_lon")
            heading    = pd_.get("heading_deg")
            target_lat = pd_.get("target_lat")
            target_lon = pd_.get("target_lon")

        records.append({
            "frame_id":       fid,
            "centroid_lat":   best["centroid_lat"],
            "centroid_lon":   best["centroid_lon"],
            "geometry":       best.get("geometry", ""),
            "score":          best["score"],
            "angle_off_deg":  best.get("angle_off_deg", 99),
            "dist_m":         best.get("dist_m", 999),
            "confidence":     best.get("confidence", 0),
            "footprint_w_m":  best.get("footprint_w_m"),
            "score_angle":    best.get("score_angle", 0),
            "score_prox":     best.get("score_prox", 0),
            "score_width":    best.get("score_width", 0),
            "score_depth":    best.get("score_depth", 0),
            "n_candidates":   len(data.get("all_candidates", [])),
            "ego_lat":        ego_lat,
            "ego_lon":        ego_lon,
            "heading_deg":    heading,
            "target_lat":     target_lat,
            "target_lon":     target_lon,
            "all_candidates": data.get("all_candidates", []),
        })
    return records


def cluster_by_building(records, radius_m=18.0):
    clusters = []
    for rec in records:
        lat, lon = rec["centroid_lat"], rec["centroid_lon"]
        assigned = False
        for cl in clusters:
            rep = cl[0]
            if _hav(lat, lon, rep["centroid_lat"], rep["centroid_lon"]) <= radius_m:
                cl.append(rec)
                assigned = True
                break
        if not assigned:
            clusters.append([rec])
    return clusters


WEIGHTS = dict(
    match_score   = 0.35,
    angle_quality = 0.25,
    dist_quality  = 0.18,
    confidence    = 0.12,
    n_candidates  = 0.06,
    cluster_size  = 0.04,
)

def quality_score(rec, cluster_size=1):
    ms  = min(rec["score"], 100) / 100.0
    aq  = max(0.0, 1.0 - (rec["angle_off_deg"] / 35.0) ** 1.6)
    dq  = math.exp(-((rec["dist_m"] - 25.0) ** 2) / (2 * 18.0 ** 2))
    cq  = float(rec["confidence"]) if rec["confidence"] else 0.5
    nq  = min(rec["n_candidates"], 20) / 20.0
    sq  = min(cluster_size, 6) / 6.0

    raw = (WEIGHTS["match_score"]   * ms +
           WEIGHTS["angle_quality"] * aq +
           WEIGHTS["dist_quality"]  * dq +
           WEIGHTS["confidence"]    * cq +
           WEIGHTS["n_candidates"]  * nq +
           WEIGHTS["cluster_size"]  * sq)
    return round(raw * 100.0, 2)


def smooth_cluster_gps(cluster):
    geom = cluster[0].get("geometry", "")
    p_lat, p_lon = polygon_centroid(geom)
    if p_lat is not None:
        return p_lat, p_lon, "polygon_centroid"

    weights = [max(r["score"], 1.0) for r in cluster]
    total_w = sum(weights)
    s_lat = sum(r["centroid_lat"] * w for r, w in zip(cluster, weights)) / total_w
    s_lon = sum(r["centroid_lon"] * w for r, w in zip(cluster, weights)) / total_w
    return s_lat, s_lon, "weighted_mean"


def _rationale(rec, q, cluster_size, error_m, smoothing_method):
    parts = []
    s = rec["score"]
    if   s >= 70: parts.append(f"high GOB match ({s:.1f}/100)")
    elif s >= 55: parts.append(f"good GOB match ({s:.1f}/100)")
    else:         parts.append(f"moderate GOB match ({s:.1f}/100)")

    if   rec["angle_off_deg"] <=  5: parts.append(f"near-perfect heading ({rec['angle_off_deg']:.1f}°)")
    elif rec["angle_off_deg"] <= 15: parts.append(f"good heading ({rec['angle_off_deg']:.1f}°)")
    else:                             parts.append(f"off-heading ({rec['angle_off_deg']:.1f}°)")

    if   15 <= rec["dist_m"] <= 40: parts.append(f"optimal range ({rec['dist_m']:.0f} m)")
    elif rec["dist_m"] < 15:         parts.append(f"very close ({rec['dist_m']:.0f} m)")
    else:                             parts.append(f"long range ({rec['dist_m']:.0f} m)")

    if rec["confidence"] and rec["confidence"] >= 0.80:
        parts.append(f"high GOB confidence ({rec['confidence']:.0%})")
    if cluster_size >= 3:
        parts.append(f"stable ({cluster_size}-frame cluster)")

    err_str = f"{error_m:.1f} m" if error_m is not None else "N/A"
    return ("; ".join(parts) +
            f". Quality={q:.1f}/100 · edge-error={err_str} · GPS={smoothing_method}.")


def select_best(clusters, top_n=None, min_quality=30.0):
    selected = []

    for cl in clusters:
        cs = len(cl)
        scored = sorted(cl, key=lambda r: quality_score(r, cs), reverse=True)
        best   = scored[0]
        q      = quality_score(best, cs)
        if q < min_quality:
            continue

        s_lat, s_lon, s_method = smooth_cluster_gps(cl)

        error_m = None
        tgt_lat = best.get("target_lat")
        tgt_lon = best.get("target_lon")
        if tgt_lat is not None and tgt_lon is not None:
            geom = best.get("geometry", "")
            if geom:
                error_m = error_to_polygon(tgt_lat, tgt_lon, geom)
                if error_m is None:
                    error_m = round(_hav(tgt_lat, tgt_lon,
                                         best["centroid_lat"], best["centroid_lon"]), 2)
                    print(f"[select] frame {best['frame_id']}: geometry parse failed, "
                          f"fell back to centroid error")
            else:
                error_m = round(_hav(tgt_lat, tgt_lon,
                                      best["centroid_lat"], best["centroid_lon"]), 2)
                print(f"[select] frame {best['frame_id']}: no geometry in match_json. "
                      f"Re-run match.py with the updated gob.py to get polygon-edge error.")

        fid = best["frame_id"]
        final_path = os.path.join(cfg.OUT_DIR, "final",
                                  f"frame_{fid:06d}_FINAL.jpg")
        vis_path   = os.path.join(cfg.OUT_DIR, "perceive_vis",
                                  f"frame_{fid:06d}_perceive_vis.jpg")

        selected.append({
            "frame_id":          fid,
            "centroid_lat":      s_lat,
            "centroid_lon":      s_lon,
            "smoothing_method":  s_method,
            "raw_centroid_lat":  best["centroid_lat"],
            "raw_centroid_lon":  best["centroid_lon"],
            "quality_score":     q,
            "match_score":       best["score"],
            "angle_off_deg":     best["angle_off_deg"],
            "dist_m":            best["dist_m"],
            "confidence":        best["confidence"],
            "footprint_w_m":     best["footprint_w_m"],
            "score_angle":       best["score_angle"],
            "score_prox":        best["score_prox"],
            "score_width":       best["score_width"],
            "score_depth":       best["score_depth"],
            "n_candidates":      best["n_candidates"],
            "ego_lat":           best["ego_lat"],
            "ego_lon":           best["ego_lon"],
            "heading_deg":       best["heading_deg"],
            "target_lat":        tgt_lat,
            "target_lon":        tgt_lon,
            "error_m":           error_m,
            "cluster_size":      cs,
            "img_path":          (final_path if os.path.exists(final_path) else
                                  vis_path   if os.path.exists(vis_path)   else None),
            "gmaps_building":    (f"https://www.google.com/maps/search/?api=1"
                                  f"&query={s_lat:.8f},{s_lon:.8f}"),
            "why_selected":      _rationale(best, q, cs, error_m, s_method),
        })

    selected.sort(key=lambda x: x["quality_score"], reverse=True)
    if top_n:
        selected = selected[:top_n]
    return selected


def write_report(selected, out_path):
    lines = [
        "=" * 72,
        "  NazarGeo — Automatic Building Selection Report",
        "=" * 72,
        "  Error metric  : polygon-edge distance (0 m if inside footprint)",
        "  GPS smoothing : polygon centroid > confidence-weighted mean",
        "  Angle scoring : quadratic falloff (steeper than linear)",
        f"  Buildings     : {len(selected)}",
        "=" * 72, "",
    ]
    for i, b in enumerate(selected, 1):
        err = f"{b['error_m']:.1f} m" if b['error_m'] is not None else "N/A"
        lines += [
            f"  -- #{i}  Frame {b['frame_id']} " + "-" * 36,
            f"  Quality score     : {b['quality_score']:.1f} / 100",
            f"  GOB match score   : {b['match_score']:.1f} / 100",
            f"    angle score     : {b['score_angle']:.1f}",
            f"    prox  score     : {b['score_prox']:.1f}",
            f"    width score     : {b['score_width']:.1f}",
            f"    depth bonus     : {b['score_depth']:.1f}",
            f"  Smoothed GPS      : {b['centroid_lat']:.7f}, {b['centroid_lon']:.7f}  ({b['smoothing_method']})",
            f"  Raw GOB centroid  : {b['raw_centroid_lat']:.7f}, {b['raw_centroid_lon']:.7f}",
            f"  Angle off heading : {b['angle_off_deg']:.2f} deg",
            f"  LiDAR distance    : {b['dist_m']:.1f} m",
            f"  GOB confidence    : {b['confidence']:.1%}" if b['confidence'] else
            f"  GOB confidence    : N/A",
            f"  Footprint width   : {b['footprint_w_m']:.1f} m" if b['footprint_w_m'] else
            f"  Footprint width   : N/A",
            f"  POLYGON-EDGE ERROR: {err}",
            f"  Cluster size      : {b['cluster_size']} frames",
            f"  Maps              : {b['gmaps_building']}",
            f"  Rationale         : {b['why_selected']}",
            "",
        ]
    lines += ["=" * 72, "  End of report", "=" * 72]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[report] → {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames",     type=str,   default=None)
    ap.add_argument("--start",      type=int,   default=None)
    ap.add_argument("--end",        type=int,   default=None)
    ap.add_argument("--top",        type=int,   default=None)
    ap.add_argument("--min-quality",type=float, default=30.0)
    ap.add_argument("--cluster-r",  type=float, default=18.0)
    args = ap.parse_args()

    match_dir = os.path.join(cfg.OUT_DIR, "match_json")

    if args.frames:
        frame_ids = [int(x.strip()) for x in args.frames.split(",")]
    elif args.start is not None and args.end is not None:
        frame_ids = []
        for fid in range(args.start, args.end + 1):
            if os.path.exists(os.path.join(match_dir, f"frame_{fid:06d}_match.json")):
                frame_ids.append(fid)
        print(f"[select] auto-scanned {len(frame_ids)} frames in [{args.start}, {args.end}]")
    else:
        frame_ids = CURATED_FRAMES
        print(f"[select] using curated frames: {frame_ids}")

    records  = load_matches(match_dir, frame_ids)
    print(f"[select] {len(records)} observations loaded")

    clusters = cluster_by_building(records, radius_m=args.cluster_r)
    print(f"[select] {len(clusters)} building clusters (r={args.cluster_r} m)")

    selected = select_best(clusters, top_n=args.top, min_quality=args.min_quality)
    print(f"[select] {len(selected)} buildings selected")

    json_out = os.path.join(cfg.OUT_DIR, "selected_buildings.json")
    with open(json_out, "w") as f:
        json.dump(selected, f, indent=2)
    print(f"[select] JSON → {json_out}")

    report_out = os.path.join(cfg.OUT_DIR, "selection_report.txt")
    write_report(selected, report_out)

    print(f"\n{'='*64}")
    print(f"  SELECTED {len(selected)} BUILDINGS")
    print(f"{'='*64}")
    for b in selected:
        err = f"err={b['error_m']:.1f}m" if b['error_m'] is not None else "err=N/A"
        gps = b['smoothing_method'][:4]
        print(f"  Frame {b['frame_id']:5d}  "
              f"quality={b['quality_score']:.1f}  "
              f"match={b['match_score']:.1f}  "
              f"angle={b['angle_off_deg']:.1f}°  "
              f"dist={b['dist_m']:.0f}m  "
              f"{err}  GPS:{gps}")
    print(f"{'='*64}\n")
    print("Next: streamlit run viewer.py")


if __name__ == "__main__":
    main()