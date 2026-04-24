import os
import sys
import json
import math
import argparse
import re

try:
    import cfg
except ImportError:
    print("[FATAL] Cannot import cfg.py — run from the NazarGeo project directory")
    sys.exit(1)

try:
    import sync
    import perceive
    import project
    import match
    import gob
except ImportError as e:
    print(f"[FATAL] Missing module: {e}")
    sys.exit(1)


GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):    print(f"  {GREEN}✓{RESET} {msg}")
def warn(msg):  print(f"  {YELLOW}⚠{RESET} {msg}")
def fail(msg):  print(f"  {RED}✗{RESET} {msg}")
def info(msg):  print(f"  {CYAN}→{RESET} {msg}")
def header(msg):print(f"\n{BOLD}{CYAN}{'─'*60}{RESET}\n{BOLD}  {msg}{RESET}\n{'─'*60}")


def hav(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin(math.radians(lat2-lat1)/2)**2
         + math.cos(p1)*math.cos(p2)*math.sin(math.radians(lon2-lon1)/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def parse_polygon(wkt):
    if not wkt: return []
    m = re.search(r'POLYGON\s*\(\((.*?)\)\)', wkt, re.IGNORECASE | re.DOTALL)
    if not m: return []
    pts = []
    for pair in m.group(1).split(','):
        p = pair.strip().split()
        if len(p) >= 2:
            pts.append((float(p[1]), float(p[0])))  # (lat, lon)
    return pts


def pip(lat, lon, pts):
    inside = False
    n, j = len(pts), len(pts)-1
    for i in range(n):
        yi, xi = pts[i]; yj, xj = pts[j]
        if ((xi > lon) != (xj > lon)) and (lat < (yj-yi)*(lon-xi)/(xj-xi)+yi):
            inside = not inside
        j = i
    return inside


def poly_error(tlat, tlon, wkt):
    pts = parse_polygon(wkt)
    if len(pts) < 3: return None
    if pip(tlat, tlon, pts): return 0.0
    def seg(plat, plon, alat, alon, blat, blon):
        dx = blon-alon; dy = blat-alat; sq = dx*dx+dy*dy
        if sq == 0: return hav(plat, plon, alat, alon)
        t = max(0.0, min(1.0, ((plon-alon)*dx+(plat-alat)*dy)/sq))
        return hav(plat, plon, alat+t*dy, alon+t*dx)
    return round(min(seg(tlat,tlon,pts[i][0],pts[i][1],pts[i+1][0],pts[i+1][1])
                     for i in range(len(pts)-1)), 2)


def stage_sync():
    header("STAGE 1 — SYNC  (manifest generation)")

    # Check IMU CSV
    if not os.path.exists(cfg.IMU_CSV_PATH):
        fail(f"IMU CSV not found: {cfg.IMU_CSV_PATH}")
        return False
    ok(f"IMU CSV found: {cfg.IMU_CSV_PATH}")

    try:
        sync.build_manifest()
        ok(f"Manifest written: {cfg.MANIFEST_PATH}")
    except Exception as e:
        fail(f"sync.build_manifest() raised: {e}")
        return False

    with open(cfg.MANIFEST_PATH) as f:
        manifest = json.load(f)
    info(f"Total frames in manifest: {len(manifest)}")

    for fid in [1, len(manifest)//2, len(manifest)]:
        entry = next((r for r in manifest if r["frame_id"] == fid), None)
        if entry is None:
            warn(f"Frame {fid} missing from manifest")
            continue
        pose = entry["ego_pose"]
        lat, lon, hdg = pose["latitude"], pose["longitude"], pose["heading_deg"]
        # Rough sanity: should be near Chennai (12.9°N, 80.2°E)
        if not (12.0 < lat < 14.0 and 79.5 < lon < 81.0):
            warn(f"Frame {fid}: lat={lat:.4f}, lon={lon:.4f} — outside expected area!")
        else:
            ok(f"Frame {fid}: lat={lat:.6f}, lon={lon:.6f}, hdg={hdg:.1f}°")

    return True


def stage_perceive(frame_id):
    header(f"STAGE 2 — PERCEIVE  (frame {frame_id})")

    img_path = os.path.join(cfg.LENS1_DIR, f"frame_{frame_id:06d}.jpg")
    if not os.path.exists(img_path):
        fail(f"Image not found: {img_path}")
        return False
    ok(f"Image exists: {img_path}")

    # Check for existing output (skip if already done)
    out_path = os.path.join(cfg.OUT_DIR, f"perceive_json/frame_{frame_id:06d}_perceive.json")
    if os.path.exists(out_path):
        with open(out_path) as f:
            perc = json.load(f)
        info(f"Using cached perceive output: {out_path}")
    else:
        info("Running perceive.run_frame() — this takes ~30s ...")
        try:
            perc = perceive.run_frame(frame_id)
        except Exception as e:
            fail(f"perceive.run_frame() raised: {e}")
            return False

    if perc is None:
        fail("perceive returned None — no building detected")
        return False

    depth = perc["median_depth"]
    bbox  = perc.get("bbox_px") or perc.get("bbox")
    conf  = perc.get("det_conf", 0)

    info(f"bbox={bbox}")
    info(f"det_conf={conf:.3f}")

    if depth < 2.0:
        warn(f"depth={depth:.2f}m  — very shallow, likely road/ground hit")
    elif depth > 60.0:
        warn(f"depth={depth:.2f}m  — very deep, may be sky/noise")
    else:
        ok(f"depth={depth:.2f}m  — plausible facade depth")

    if conf < 0.10:
        warn(f"Low detection confidence ({conf:.2f}) — may be noisy")
    else:
        ok(f"Detection confidence: {conf:.2f}")

    vis_path = perc.get("vis", "")
    if vis_path and os.path.exists(vis_path):
        ok(f"Vis image: {vis_path}")
    else:
        warn("Vis image missing — check perceive.run_frame()")

    return True


def stage_project(frame_id):
    header(f"STAGE 3 — PROJECT  (frame {frame_id})")

    out_path = os.path.join(cfg.OUT_DIR, f"project_json/frame_{frame_id:06d}_project.json")
    if os.path.exists(out_path):
        info(f"Using cached project output: {out_path}")
        with open(out_path) as f:
            proj = json.load(f)
    else:
        try:
            proj = project.run_frame(frame_id)
        except Exception as e:
            fail(f"project.run_frame() raised: {e}")
            return False

    if proj is None:
        fail("project returned None")
        return False

    ego_lat   = proj["ego_lat"]
    ego_lon   = proj["ego_lon"]
    raw_lat   = proj.get("raw_target_lat", proj["target_lat"] - cfg.PROJECTION_LAT_OFFSET)
    raw_lon   = proj.get("raw_target_lon", proj["target_lon"] - cfg.PROJECTION_LON_OFFSET)
    tgt_lat   = proj["target_lat"]
    tgt_lon   = proj["target_lon"]
    depth_m   = proj["depth_m"]
    dist_m    = proj.get("adjusted_dist_m", depth_m)
    bearing   = proj.get("projection_bearing", proj.get("heading_deg", 0))
    mode      = proj.get("projection_mode", "heading_only")

    ok(f"Ego pose:        ({ego_lat:.6f}, {ego_lon:.6f})")
    ok(f"Depth:           {depth_m:.2f} m")
    ok(f"Projection dist: {dist_m:.2f} m  bearing={bearing:.1f}°  mode={mode}")
    ok(f"Raw target:      ({raw_lat:.6f}, {raw_lon:.6f})")
    ok(f"Corrected GPS:   ({tgt_lat:.6f}, {tgt_lon:.6f})")
    info(f"Applied offset:  dlat={cfg.PROJECTION_LAT_OFFSET:+.6f}  "
         f"dlon={cfg.PROJECTION_LON_OFFSET:+.6f}")
    info(f"Google Maps:     {proj.get('gmaps', 'N/A')}")

    # Sanity: corrected should be near ego
    dist_to_ego = hav(ego_lat, ego_lon, tgt_lat, tgt_lon)
    if dist_to_ego > 200:
        warn(f"Corrected GPS is {dist_to_ego:.0f}m from ego — unusually far")
    else:
        ok(f"Corrected GPS is {dist_to_ego:.0f}m from ego — reasonable")

    return True


def stage_match(frame_id, show_ranking=True):
    header(f"STAGE 4 — MATCH + RANKING  (frame {frame_id})")

    match_path = os.path.join(cfg.OUT_DIR, f"match_json/frame_{frame_id:06d}_match.json")
    if os.path.exists(match_path):
        info(f"Using cached match output: {match_path}")
        with open(match_path) as f:
            result = json.load(f)
    else:
        try:
            result = match.run_frame(frame_id)
        except Exception as e:
            fail(f"match.run_frame() raised: {e}")
            return False

    if result is None:
        fail("match returned None — no GOB candidates found")
        return False

    best      = result["best_match"]
    all_cands = result.get("all_candidates", [])

    ok(f"GOB candidates evaluated: {len(all_cands)}")
    info(f"Best match:")
    info(f"  GOB centroid: ({best['centroid_lat']:.6f}, {best['centroid_lon']:.6f})")
    info(f"  Score:        {best['score']:.1f}/100")
    info(f"  Components:   angle={best.get('score_angle',0):.1f}  "
         f"prox={best.get('score_prox',0):.1f}  "
         f"width={best.get('score_width',0):.1f}  "
         f"depth={best.get('score_depth',0):.1f}")
    info(f"  Angle off:    {best.get('angle_off_deg',0):.2f}°")
    info(f"  Distance:     {best.get('dist_m',0):.1f} m")
    info(f"  Confidence:   {best.get('confidence',0):.1%}")

    if show_ranking and all_cands:
        print(f"\n  {'Rank':>4}  {'Score':>6}  {'Angle':>6}  {'Dist':>6}  "
              f"{'Width':>6}  {'Depth':>6}  {'Conf':>5}  GOB GPS")
        print("  " + "─" * 80)
        for rank, c in enumerate(all_cands[:10], 1):
            flag = " ◄ BEST" if rank == 1 else ""
            print(f"  {rank:>4}  {c['score']:>6.1f}  "
                  f"{c.get('score_angle',0):>6.1f}  "
                  f"{c.get('score_prox',0):>6.1f}  "
                  f"{c.get('score_width',0):>6.1f}  "
                  f"{c.get('score_depth',0):>6.1f}  "
                  f"{c.get('confidence',0):>5.2f}  "
                  f"({c['centroid_lat']:.5f}, {c['centroid_lon']:.5f}){flag}")
        if len(all_cands) > 10:
            print(f"  ... and {len(all_cands)-10} more candidates not shown")

    return True


def stage_error(frame_id):
    header(f"STAGE 5 — ERROR COMPUTATION  (frame {frame_id})")

    proj_path  = os.path.join(cfg.OUT_DIR, f"project_json/frame_{frame_id:06d}_project.json")
    match_path = os.path.join(cfg.OUT_DIR, f"match_json/frame_{frame_id:06d}_match.json")

    if not os.path.exists(proj_path):
        fail(f"project_json missing for frame {frame_id} — run project first")
        return False
    if not os.path.exists(match_path):
        fail(f"match_json missing for frame {frame_id} — run match first")
        return False

    with open(proj_path) as f: proj = json.load(f)
    with open(match_path) as f: result = json.load(f)

    best    = result["best_match"]
    tgt_lat = proj["target_lat"]
    tgt_lon = proj["target_lon"]
    raw_lat = proj.get("raw_target_lat", tgt_lat - cfg.PROJECTION_LAT_OFFSET)
    raw_lon = proj.get("raw_target_lon", tgt_lon - cfg.PROJECTION_LON_OFFSET)
    gob_lat = best["centroid_lat"]
    gob_lon = best["centroid_lon"]
    geom    = best.get("geometry", "")

    raw_centroid_err  = hav(raw_lat,  raw_lon,  gob_lat, gob_lon)
    corr_centroid_err = hav(tgt_lat, tgt_lon,   gob_lat, gob_lon)

    raw_poly_err  = poly_error(raw_lat,  raw_lon,  geom)
    corr_poly_err = poly_error(tgt_lat, tgt_lon,   geom)

    info(f"Estimated GPS (raw):       ({raw_lat:.6f}, {raw_lon:.6f})")
    info(f"Estimated GPS (corrected): ({tgt_lat:.6f}, {tgt_lon:.6f})")
    info(f"GOB centroid:              ({gob_lat:.6f}, {gob_lon:.6f})")
    print()

    def chip(err):
        if err is None: return "N/A"
        if err == 0.0:  return f"{GREEN}INSIDE FOOTPRINT{RESET}"
        if err < 5:     return f"{GREEN}{err:.2f} m (excellent){RESET}"
        if err < 10:    return f"{CYAN}{err:.2f} m (good){RESET}"
        if err < 20:    return f"{YELLOW}{err:.2f} m (fair){RESET}"
        return f"{RED}{err:.2f} m (poor){RESET}"

    print(f"  Centroid error  raw:       {chip(raw_centroid_err)}")
    print(f"  Centroid error  corrected: {chip(corr_centroid_err)}")
    print()
    if geom:
        print(f"  Polygon-edge error raw:       {chip(raw_poly_err)}")
        print(f"  Polygon-edge error corrected: {chip(corr_poly_err)}")
        impr = (raw_poly_err or 0) - (corr_poly_err or 0)
        if impr > 0:
            ok(f"Offset improved error by {impr:.2f} m")
        elif impr < 0:
            warn(f"Offset worsened error by {abs(impr):.2f} m — retune offset!")
    else:
        warn("No geometry in match_json — cannot compute polygon-edge error")
        info("Rerun: match.py with updated gob.py to get WKT geometry")

    return True


def stage_multi_summary(frame_ids):
    header(f"MULTI-FRAME ERROR SUMMARY  ({len(frame_ids)} frames)")

    rows = []
    for fid in frame_ids:
        proj_path  = os.path.join(cfg.OUT_DIR, f"project_json/frame_{fid:06d}_project.json")
        match_path = os.path.join(cfg.OUT_DIR, f"match_json/frame_{fid:06d}_match.json")
        if not (os.path.exists(proj_path) and os.path.exists(match_path)):
            warn(f"Frame {fid}: missing output files — skipping")
            continue
        with open(proj_path) as f: proj = json.load(f)
        with open(match_path) as f: result = json.load(f)
        best    = result.get("best_match")
        if best is None: continue
        tgt_lat = proj["target_lat"]
        tgt_lon = proj["target_lon"]
        raw_lat = proj.get("raw_target_lat", tgt_lat - cfg.PROJECTION_LAT_OFFSET)
        raw_lon = proj.get("raw_target_lon", tgt_lon - cfg.PROJECTION_LON_OFFSET)
        gob_lat = best["centroid_lat"]
        gob_lon = best["centroid_lon"]
        geom    = best.get("geometry", "")
        raw_e   = poly_error(raw_lat,  raw_lon,  geom)
        corr_e  = poly_error(tgt_lat, tgt_lon,   geom)
        if raw_e is None:  raw_e  = round(hav(raw_lat,  raw_lon,  gob_lat, gob_lon), 2)
        if corr_e is None: corr_e = round(hav(tgt_lat, tgt_lon,   gob_lat, gob_lon), 2)
        rows.append((fid, best["score"], raw_e, corr_e))

    if not rows:
        warn("No frames with complete output found")
        return

    print(f"\n  {'Frame':>6}  {'Score':>6}  {'RawErr':>8}  {'CorrErr':>9}  {'Impr':>7}")
    print("  " + "─" * 50)
    raw_errs, corr_errs = [], []
    for fid, score, re, ce in rows:
        impr = (re - ce) if (re is not None and ce is not None) else 0
        flag = GREEN+"✓"+RESET if impr >= 0 else RED+"✗"+RESET
        label_r = "INSIDE" if re == 0 else f"{re:.1f}m"
        label_c = "INSIDE" if ce == 0 else f"{ce:.1f}m"
        print(f"  {fid:>6}  {score:>6.1f}  {label_r:>8}  {label_c:>9}  "
              f"{impr:>+6.1f}m  {flag}")
        if re is not None: raw_errs.append(re)
        if ce is not None: corr_errs.append(ce)

    print("  " + "─" * 50)
    if raw_errs:
        print(f"  Average raw error:       {sum(raw_errs)/len(raw_errs):.2f} m")
    if corr_errs:
        avg_c = sum(corr_errs)/len(corr_errs)
        print(f"  Average corrected error: {avg_c:.2f} m")
        inside = sum(1 for e in corr_errs if e == 0)
        lt5    = sum(1 for e in corr_errs if 0 < e < 5)
        lt10   = sum(1 for e in corr_errs if 5 <= e < 10)
        print(f"\n  INSIDE footprint: {inside}  |  <5m: {lt5}  |  <10m: {lt10}")
    print()

    # Suggest new offset
    dlats, dlons = [], []
    for fid, score, re, ce in rows:
        proj_path  = os.path.join(cfg.OUT_DIR, f"project_json/frame_{fid:06d}_project.json")
        match_path = os.path.join(cfg.OUT_DIR, f"match_json/frame_{fid:06d}_match.json")
        with open(proj_path) as f: proj = json.load(f)
        with open(match_path) as f: result = json.load(f)
        best = result.get("best_match")
        if best is None: continue
        raw_lat = proj.get("raw_target_lat", proj["target_lat"] - cfg.PROJECTION_LAT_OFFSET)
        raw_lon = proj.get("raw_target_lon", proj["target_lon"] - cfg.PROJECTION_LON_OFFSET)
        dlats.append(best["centroid_lat"] - raw_lat)
        dlons.append(best["centroid_lon"] - raw_lon)

    if dlats:
        avg_dlat = sum(dlats) / len(dlats)
        avg_dlon = sum(dlons) / len(dlons)
        print(f"  Suggested new offset from these {len(dlats)} frames:")
        print(f"    {BOLD}PROJECTION_LAT_OFFSET = {avg_dlat:.6f}{RESET}")
        print(f"    {BOLD}PROJECTION_LON_OFFSET = {avg_dlon:.6f}{RESET}")
        print(f"  (currently: dlat={cfg.PROJECTION_LAT_OFFSET:.6f}  "
              f"dlon={cfg.PROJECTION_LON_OFFSET:.6f})")


def main():
    ap = argparse.ArgumentParser(
        description="NazarGeo step-by-step diagnostic tool",
        formatter_class=argparse.RawTextHelpFormatter
    )
    ap.add_argument("--frame",   type=int, default=840,
                    help="Single frame to test (default: 840)")
    ap.add_argument("--frames",  type=str, default=None,
                    help="Comma-separated frame list for multi-frame summary\n"
                         "e.g.  76,151,226,276,401,626,1826,3351")
    ap.add_argument("--stage",   type=str, default="all",
                    choices=["sync", "perceive", "project", "match", "error",
                             "ranking", "summary", "all"],
                    help="Which stage to test (default: all)")
    ap.add_argument("--no-ranking", action="store_true",
                    help="Skip the 10-candidate ranking table in match stage")
    args = ap.parse_args()

    frame_id = args.frame
    frame_ids = ([int(x.strip()) for x in args.frames.split(",")]
                 if args.frames else [frame_id])

    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  NazarGeo Diagnostic  |  frame={frame_id}{RESET}")
    print(f"  cfg.OUT_DIR = {cfg.OUT_DIR}")
    print(f"  Offsets: dlat={cfg.PROJECTION_LAT_OFFSET:+.6f}  "
          f"dlon={cfg.PROJECTION_LON_OFFSET:+.6f}")
    print(f"  Penetration offset: {cfg.BUILDING_PENETRATION_OFFSET_M} m")
    print(f"{'='*60}\n")

    results = {}

    run_all = args.stage == "all"

    if run_all or args.stage == "sync":
        results["sync"] = stage_sync()

    if run_all or args.stage in ("perceive",):
        results["perceive"] = stage_perceive(frame_id)

    if run_all or args.stage in ("project",):
        results["project"] = stage_project(frame_id)

    if run_all or args.stage in ("match", "ranking"):
        results["match"] = stage_match(frame_id,
                                       show_ranking=not args.no_ranking)

    if run_all or args.stage == "error":
        results["error"] = stage_error(frame_id)

    if args.frames or args.stage == "summary":
        stage_multi_summary(frame_ids)

    header("VERDICT")
    all_ok = True
    for stage, passed in results.items():
        if passed:
            ok(f"{stage}")
        else:
            fail(f"{stage}")
            all_ok = False

    if all_ok and results:
        print(f"\n  {GREEN}{BOLD}All stages passed!{RESET}")
        print(f"  Next steps:")
        print(f"    python presniff.py --start 1 --end 3599 --step 43")
        print(f"    python select_buildings.py --start 1 --end 3599")
        print(f"    python tim.py   # recalibrate offset")
        print(f"    python verify.py --frames 76,151,226,276,401,626,1826,3351  --stage summary")
        print(f"    streamlit run viewer.py")
    else:
        print(f"\n  {YELLOW}Some stages need attention — fix issues above before proceeding.{RESET}")
    print()


if __name__ == "__main__":
    main()