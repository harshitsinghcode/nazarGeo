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
    y    = math.sin(dlon) * math.cos(rlat2)
    x    = math.cos(rlat1)*math.sin(rlat2) - math.sin(rlat1)*math.cos(rlat2)*math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def _angle_diff(a, b):
    return abs((a - b + 180) % 360 - 180)


def _score(dist_m, angle_off, footprint_w_m, detected_img_frac, depth_m):
    norm_angle = angle_off / cfg.ANGLE_CONE_DEG      
    angle_score = max(0.0,
        cfg.SCORE_ANGLE_MAX * (1.0 - norm_angle ** 1.6))  # steeper falloff

    prox_score  = cfg.SCORE_PROX_MAX * math.exp(-dist_m / cfg.PROX_DECAY_M)

    if footprint_w_m and footprint_w_m > 0 and dist_m > 0:
        expected_frac = 2 * math.degrees(math.atan2(footprint_w_m / 2, dist_m)) / cfg.HFOV_DEG
        if expected_frac > 0:
            ratio       = min(detected_img_frac, expected_frac) / max(detected_img_frac, expected_frac)
            width_score = cfg.SCORE_WIDTH_MAX * ratio
        else:
            width_score = 0.0
    else:
        width_score = 0.0

    depth_bonus = 0.0
    if depth_m and depth_m > 0:
        depth_diff   = abs(dist_m - depth_m)
        depth_bonus  = 10.0 * math.exp(-depth_diff / 15.0)

    total = angle_score + prox_score + width_score + depth_bonus
    return total, angle_score, prox_score, width_score, depth_bonus


def run_frame(frame_id):
    project_path  = os.path.join(cfg.OUT_DIR, f"project_json/frame_{frame_id:06d}_project.json")
    perceive_path = os.path.join(cfg.OUT_DIR, f"perceive_json/frame_{frame_id:06d}_perceive.json")

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
    depth_m = proj["depth_m"]

    bbox_px = perc.get("bbox_px") or perc.get("bbox")
    img_w   = perc["img_w"]
    detected_img_frac = (bbox_px[2] - bbox_px[0]) / img_w if img_w > 0 else 0.0

    print(f"[match] querying GOB within {cfg.GOB_RADIUS_M}m of ({ego_lat:.6f}, {ego_lon:.6f})...")
    buildings = gob.load_gob(cfg.GOB_CSV_PATH, ego_lat, ego_lon, cfg.GOB_RADIUS_M, cfg.GOB_CONF_MIN)

    if not buildings:
        print("[match] no GOB buildings found in radius")
        return None

    print(f"[match] {len(buildings)} buildings — filtering cone {cfg.ANGLE_CONE_DEG}°...")

    candidates = []
    for b in buildings:
        clat, clon = b["centroid_lat"], b["centroid_lon"]
        dist_m_b   = b["dist_m"]
        bearing    = _bearing(ego_lat, ego_lon, clat, clon)
        ang_off    = _angle_diff(bearing, heading)

        if ang_off > cfg.ANGLE_CONE_DEG:
            continue

        fw = b.get("footprint_w_m")
        total, a_s, p_s, w_s, d_b = _score(dist_m_b, ang_off, fw, detected_img_frac, depth_m)

        candidates.append({
            "centroid_lat":  clat,
            "centroid_lon":  clon,
            "dist_m":        round(dist_m_b, 2),
            "angle_off_deg": round(ang_off, 2),
            "confidence":    b.get("confidence"),
            "footprint_w_m": round(fw, 2) if fw else None,
            "score":         round(total, 2),
            "score_angle":   round(a_s, 2),
            "score_prox":    round(p_s, 2),
            "score_width":   round(w_s, 2),
            "score_depth":   round(d_b, 2),
            "geometry":      b.get("geometry", ""),
        })

    if not candidates:
        print("[match] no candidates in cone")
        return None

    candidates.sort(key=lambda x: x["score"], reverse=True)
    best = candidates[0]

    print(f"[match] {len(candidates)} candidates — best={best['score']:.1f} "
          f"at ({best['centroid_lat']:.6f}, {best['centroid_lon']:.6f})")
    for c in candidates[:8]:
        flag = " ← best" if c is best else ""
        print(f"  {c['score']:.1f} "
              f"(ang={c['score_angle']:.1f} prox={c['score_prox']:.1f} "
              f"w={c['score_width']:.1f} dep={c['score_depth']:.1f}) "
              f"dist={c['dist_m']:.1f}m off={c['angle_off_deg']:.1f}°{flag}")

    out = {
        "frame_id":       frame_id,
        "best_match":     best,
        "all_candidates": candidates,
    }
    out_path = os.path.join(cfg.OUT_DIR, f"match_json/frame_{frame_id:06d}_match.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)

    print(f"[match] → {out_path}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", type=int, default=840)
    args = ap.parse_args()
    run_frame(args.frame)