import argparse
import os
import sys
import cv2
import json
import cfg
import sync
import perceive
import project
import match

def save_json(data, folder, filename):
    path = os.path.join(cfg.OUT_DIR, folder)
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, filename), "w") as f:
        json.dump(data, f, indent=4)

def main():
    ap = argparse.ArgumentParser(description="Falcons building geo-association pipeline")
    ap.add_argument("--frame",     type=int, default=840)
    ap.add_argument("--skip-sync", action="store_true")
    args = ap.parse_args()

    os.makedirs(cfg.OUT_DIR, exist_ok=True)

    if not args.skip_sync or not os.path.exists(cfg.MANIFEST_PATH):
        print("=== Phase 1: sync ===")
        sync.build_manifest()
    else:
        print("=== Phase 1: sync [skipped] ===")

    print(f"\n=== Phase 2: perceive (frame {args.frame}) ===")
    perc = perceive.run_frame(args.frame)
    if perc is None:
        print("[run] Phase 2 no output — abort")
        sys.exit(1)
    save_json(perc, "perceive_json", f"frame_{args.frame:06d}_perceive.json")

    print(f"\n=== Phase 3: project (frame {args.frame}) ===")
    proj = project.run_frame(args.frame)
    if proj is None:
        print("[run] Phase 3 no output — abort")
        sys.exit(1)
    save_json(proj, "project_json", f"frame_{args.frame:06d}_project.json")

    print(f"\n=== Phase 4: match (frame {args.frame}) ===")
    result = match.run_frame(args.frame)
    if result is None:
        print("[run] Phase 4 no match — abort")
        sys.exit(1)
    save_json(result, "match_json", f"frame_{args.frame:06d}_match.json")

    best = result["best_match"]

    summary_data = {
        "frame": args.frame,
        "depth": proj['depth_m'],
        "target_gps": [proj['target_lat'], proj['target_lon']],
        "match_gps": [best['centroid_lat'], best['centroid_lon']],
        "score": best['score'],
        "confidence": best['confidence']
    }
    save_json(summary_data, "summary", f"batch_summary_{args.frame:06d}.json")

    print(f"\n{'='*52}")
    print(f"RESULT  frame={args.frame}")
    print(f"  depth        {proj['depth_m']:.2f} m")
    print(f"  target GPS   {proj['target_lat']:.6f}, {proj['target_lon']:.6f}")
    print(f"  GOB match    {best['centroid_lat']:.6f}, {best['centroid_lon']:.6f}")
    print(f"  score        {best['score']:.1f}/100")
    print(f"  confidence   {best['confidence']}")
    print(f"{'='*52}")

    print("\n[run] Generating final presentation visual...")

    vis_path = perc.get("vis") or os.path.join(
        cfg.OUT_DIR, "perceive_vis", f"frame_{args.frame:06d}_perceive_vis.jpg"
    )
    img = cv2.imread(vis_path)

    if img is not None:
        h, w = img.shape[:2]
        car_pt  = (w // 2, h)
        box     = perc.get("bbox_px") or perc.get("bbox")
        bldg_pt = (int((box[0] + box[2]) / 2), int((box[1] + box[3]) / 2))

        cv2.line(img, car_pt, bldg_pt, (0, 255, 255), 4, cv2.LINE_AA)
        cv2.circle(img, bldg_pt, 8, (0, 165, 255), -1)

        text_x = bldg_pt[0] + 20
        if text_x > w - 440: text_x = bldg_pt[0] - 460
        text_y = max(bldg_pt[1] - 40, 50)

        overlay = img.copy()
        cv2.rectangle(overlay, (text_x - 10, text_y - 30), (text_x + 460, text_y + 100), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)

        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(img, f"Depth: {proj['depth_m']:.1f}m", (text_x, text_y), font, 0.8, (0, 255, 255), 2)
        cv2.putText(img, f"Est GPS: {proj['target_lat']:.5f}, {proj['target_lon']:.5f}", (text_x, text_y + 35), font, 0.6, (255, 255, 255), 1)
        cv2.putText(img, f"GOB Match: {best['centroid_lat']:.5f}, {best['centroid_lon']:.5f}", (text_x, text_y + 70), font, 0.7, (0, 255, 0), 2)

        final_dir = os.path.join(cfg.OUT_DIR, "final")
        os.makedirs(final_dir, exist_ok=True)
        final_path = os.path.join(final_dir, f"frame_{args.frame:06d}_FINAL.jpg")

        cv2.imwrite(final_path, img)
        print(f"[run] ✅ Final visual → {final_path}")
    else:
        print(f"[run] ⚠️  Could not load image — skipping final visual")

if __name__ == "__main__":
    main()