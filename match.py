# import os
# import json
# import math
# import argparse
# import warnings
# import osmnx as ox
# from geopy.distance import geodesic
# import cfg

# warnings.filterwarnings("ignore")


# def _bearing(lat1, lon1, lat2, lon2):
#     rlat1, rlon1 = math.radians(lat1), math.radians(lon1)
#     rlat2, rlon2 = math.radians(lat2), math.radians(lon2)
#     dlon = rlon2 - rlon1
#     y = math.sin(dlon) * math.cos(rlat2)
#     x = math.cos(rlat1) * math.sin(rlat2) - math.sin(rlat1) * math.cos(rlat2) * math.cos(dlon)
#     return (math.degrees(math.atan2(y, x)) + 360) % 360


# def _angle_diff(a, b):
#     return abs((a - b + 180) % 360 - 180)


# def _footprint_width_m(gdf_row):
#     try:
#         proj = gdf_row.geometry.minimum_rotated_rectangle
#         coords = list(proj.exterior.coords)
#         sides = [geodesic(
#             (coords[i][1], coords[i][0]),
#             (coords[i+1][1], coords[i+1][0])
#         ).meters for i in range(len(coords) - 1)]
#         return max(sides)
#     except Exception:
#         return None


# def _score(dist_m, angle_off, footprint_w_m, detected_img_frac):
#     angle_score = max(0.0, cfg.SCORE_ANGLE_MAX - angle_off * (cfg.SCORE_ANGLE_MAX / cfg.ANGLE_CONE_DEG))
#     prox_score  = cfg.SCORE_PROX_MAX * math.exp(-dist_m / cfg.PROX_DECAY_M)

#     if footprint_w_m is not None and footprint_w_m > 0 and dist_m > 0:
#         expected_frac = 2 * math.degrees(math.atan2(footprint_w_m / 2, dist_m)) / cfg.CAMERA_HFOV_DEG
#         ratio = min(detected_img_frac, expected_frac) / max(detected_img_frac, expected_frac)
#         width_score = cfg.SCORE_WIDTH_MAX * ratio
#     else:
#         width_score = 0.0

#     return angle_score + prox_score + width_score, angle_score, prox_score, width_score


# def run_frame(frame_id):
#     project_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:04d}_project.json")
#     perceive_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:04d}_perceive.json")

#     if not os.path.exists(project_path):
#         raise FileNotFoundError(f"Project output missing: {project_path}")
#     if not os.path.exists(perceive_path):
#         raise FileNotFoundError(f"Perceive output missing: {perceive_path}")

#     with open(project_path) as f:
#         proj = json.load(f)
#     with open(perceive_path) as f:
#         perc = json.load(f)

#     ego_lat  = proj["ego_lat"]
#     ego_lon  = proj["ego_lon"]
#     heading  = proj["heading_deg"]
#     depth    = proj["depth_m"]

#     bbox_px = perc["bbox_px"]
#     img_w   = perc["img_w"]
#     detected_img_frac = (bbox_px[2] - bbox_px[0]) / img_w if img_w > 0 else 0.0

#     print(f"[match] querying OSM within {cfg.OSM_RADIUS_M}m of ({ego_lat:.6f}, {ego_lon:.6f})...")
#     try:
#         gdf = ox.features_from_point((ego_lat, ego_lon), dist=cfg.OSM_RADIUS_M, tags={"building": True})
#     except Exception as e:
#         print(f"[match] OSM query failed: {e}")
#         return None

#     gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()
#     if gdf.empty:
#         print("[match] no building polygons returned")
#         return None

#     gdf["centroid_lat"] = gdf.geometry.centroid.y
#     gdf["centroid_lon"] = gdf.geometry.centroid.x

#     candidates = []
#     for i, (idx, row) in enumerate(gdf.iterrows()):
#         clat, clon = row["centroid_lat"], row["centroid_lon"]
#         dist      = geodesic((ego_lat, ego_lon), (clat, clon)).meters
#         bearing   = _bearing(ego_lat, ego_lon, clat, clon)
#         ang_off   = _angle_diff(bearing, heading)

#         if ang_off > cfg.ANGLE_CONE_DEG:
#             continue

#         fw = _footprint_width_m(row)
#         total, a_s, p_s, w_s = _score(dist, ang_off, fw, detected_img_frac)

#         candidates.append({
#             "osm_idx":       str(idx),
#             "centroid_lat":  clat,
#             "centroid_lon":  clon,
#             "dist_m":        round(dist, 2),
#             "angle_off_deg": round(ang_off, 2),
#             "footprint_w_m": round(fw, 2) if fw else None,
#             "score":         round(total, 2),
#             "score_angle":   round(a_s, 2),
#             "score_prox":    round(p_s, 2),
#             "score_width":   round(w_s, 2)
#         })

#     if not candidates:
#         print("[match] no candidates within angle cone")
#         return None

#     candidates.sort(key=lambda x: x["score"], reverse=True)
#     best = candidates[0]

#     print(f"[match] {len(candidates)} candidates — best score={best['score']:.1f} "
#           f"at ({best['centroid_lat']:.6f}, {best['centroid_lon']:.6f})")
#     for c in candidates:
#         flag = " ← best" if c is best else ""
#         print(f"  score={c['score']:.1f} "
#               f"(ang={c['score_angle']:.1f} prox={c['score_prox']:.1f} w={c['score_width']:.1f}) "
#               f"dist={c['dist_m']:.1f}m angle_off={c['angle_off_deg']:.1f}°{flag}")

#     out = {
#         "frame_id":   frame_id,
#         "best_match": best,
#         "all_candidates": candidates
#     }

#     out_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:04d}_match.json")
#     with open(out_path, "w") as f:
#         json.dump(out, f, indent=2)

#     print(f"[match] → {out_path}")
#     return out


# if __name__ == "__main__":
#     ap = argparse.ArgumentParser()
#     ap.add_argument("--frame", type=int, default=5)
#     args = ap.parse_args()
#     run_frame(args.frame)

#-------------------------------------------------------------

import os
import json
import math
import argparse
import cfg
import gob


def _bearing(lat1, lon1, lat2, lon2):
    rlat1, rlon1 = math.radians(lat1), math.radians(lon1)
    rlat2, rlon2 = math.radians(lat2), math.radians(lon2)
    dlon = rlon2 - rlon1
    y = math.sin(dlon) * math.cos(rlat2)
    x = math.cos(rlat1) * math.sin(rlat2) - math.sin(rlat1) * math.cos(rlat2) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def _angle_diff(a, b):
    return abs((a - b + 180) % 360 - 180)


def _score(dist_m, angle_off, footprint_w_m, detected_img_frac):
    angle_score = max(0.0, cfg.SCORE_ANGLE_MAX - angle_off * (cfg.SCORE_ANGLE_MAX / cfg.ANGLE_CONE_DEG))
    prox_score  = cfg.SCORE_PROX_MAX * math.exp(-dist_m / cfg.PROX_DECAY_M)

    if footprint_w_m and footprint_w_m > 0 and dist_m > 0:
        expected_frac = 2 * math.degrees(math.atan2(footprint_w_m / 2, dist_m)) / cfg.HFOV_DEG
        ratio = min(detected_img_frac, expected_frac) / max(detected_img_frac, expected_frac)
        width_score = cfg.SCORE_WIDTH_MAX * ratio
    else:
        width_score = 0.0

    return angle_score + prox_score + width_score, angle_score, prox_score, width_score


def run_frame(frame_id):
    project_path  = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:06d}_project.json")
    perceive_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:06d}_perceive.json")

    if not os.path.exists(project_path):
        raise FileNotFoundError(f"Project output missing: {project_path}")
    if not os.path.exists(perceive_path):
        raise FileNotFoundError(f"Perceive output missing: {perceive_path}")

    with open(project_path) as f:
        proj = json.load(f)
    with open(perceive_path) as f:
        perc = json.load(f)

    ego_lat = proj["ego_lat"]
    ego_lon = proj["ego_lon"]
    heading = proj["heading_deg"]

    bbox_px = perc["bbox_px"]
    img_w   = perc["img_w"]
    detected_img_frac = (bbox_px[2] - bbox_px[0]) / img_w if img_w > 0 else 0.0

    print(f"[match] querying GOB within {cfg.GOB_RADIUS_M}m of ({ego_lat:.6f}, {ego_lon:.6f})...")
    buildings = gob.load_gob(cfg.GOB_CSV_PATH, ego_lat, ego_lon, cfg.GOB_RADIUS_M, cfg.GOB_CONF_MIN)

    if not buildings:
        print("[match] no GOB buildings found in radius")
        return None

    print(f"[match] {len(buildings)} buildings in radius — filtering by cone...")

    candidates = []
    for b in buildings:
        clat, clon = b["centroid_lat"], b["centroid_lon"]
        dist_m    = b["dist_m"]
        bearing   = _bearing(ego_lat, ego_lon, clat, clon)
        ang_off   = _angle_diff(bearing, heading)

        if ang_off > cfg.ANGLE_CONE_DEG:
            continue

        fw = b.get("footprint_w_m")
        total, a_s, p_s, w_s = _score(dist_m, ang_off, fw, detected_img_frac)

        candidates.append({
            "centroid_lat":  clat,
            "centroid_lon":  clon,
            "dist_m":        round(dist_m, 2),
            "angle_off_deg": round(ang_off, 2),
            "confidence":    b.get("confidence"),
            "footprint_w_m": round(fw, 2) if fw else None,
            "score":         round(total, 2),
            "score_angle":   round(a_s, 2),
            "score_prox":    round(p_s, 2),
            "score_width":   round(w_s, 2)
        })

    if not candidates:
        print("[match] no candidates within angle cone")
        return None

    candidates.sort(key=lambda x: x["score"], reverse=True)
    best = candidates[0]

    print(f"[match] {len(candidates)} candidates — best score={best['score']:.1f} "
          f"at ({best['centroid_lat']:.6f}, {best['centroid_lon']:.6f})")
    for c in candidates:
        flag = " ← best" if c is best else ""
        print(f"  score={c['score']:.1f} "
              f"(ang={c['score_angle']:.1f} prox={c['score_prox']:.1f} w={c['score_width']:.1f}) "
              f"dist={c['dist_m']:.1f}m angle_off={c['angle_off_deg']:.1f}°{flag}")

    out = {
        "frame_id":       frame_id,
        "best_match":     best,
        "all_candidates": candidates
    }

    out_path = os.path.join(cfg.OUT_DIR, f"frame_{frame_id:06d}_match.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    print(f"[match] → {out_path}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", type=int, default=840)
    args = ap.parse_args()
    run_frame(args.frame)