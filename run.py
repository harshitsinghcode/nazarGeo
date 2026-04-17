# import argparse
# import os
# import sys
# import cfg
# import sync
# import perceive
# import project
# import match


# def main():
#     ap = argparse.ArgumentParser(description="Building geo-association pipeline")
#     ap.add_argument("--frame", type=int, default=5, help="Frame index to process")
#     ap.add_argument("--skip-sync", action="store_true", help="Skip Phase 1 if manifest already exists")
#     args = ap.parse_args()

#     os.makedirs(cfg.OUT_DIR, exist_ok=True)

#     if not args.skip_sync or not os.path.exists(cfg.MANIFEST_PATH):
#         print("=== Phase 1: sync ===")
#         sync.build_manifest()
#     else:
#         print("=== Phase 1: sync [skipped] ===")

#     print(f"\n=== Phase 2: perceive (frame {args.frame}) ===")
#     perc = perceive.run_frame(args.frame)
#     if perc is None:
#         print("[run] Phase 2 produced no output — aborting")
#         sys.exit(1)

#     print(f"\n=== Phase 3: project (frame {args.frame}) ===")
#     proj = project.run_frame(args.frame)
#     if proj is None:
#         print("[run] Phase 3 produced no output — aborting")
#         sys.exit(1)

#     print(f"\n=== Phase 4: match (frame {args.frame}) ===")
#     result = match.run_frame(args.frame)
#     if result is None:
#         print("[run] Phase 4 produced no match — aborting")
#         sys.exit(1)

#     best = result["best_match"]
#     print(f"\n{'='*50}")
#     print(f"RESULT  frame={args.frame}")
#     print(f"  depth       {proj['depth_m']:.2f} m")
#     print(f"  target GPS  {proj['target_lat']:.6f}, {proj['target_lon']:.6f}")
#     print(f"  OSM match   {best['centroid_lat']:.6f}, {best['centroid_lon']:.6f}")
#     print(f"  score       {best['score']:.1f}/100")
#     print(f"  gmaps       {proj['gmaps']}")
#     print(f"{'='*50}")


# if __name__ == "__main__":
#     main()


#--------------------------------------------






















# import argparse
# import os
# import sys
# import cfg
# import sync
# import perceive
# import project
# import match


# def main():
#     ap = argparse.ArgumentParser(description="Falcons building geo-association pipeline")
#     ap.add_argument("--frame",     type=int, default=840)
#     ap.add_argument("--skip-sync", action="store_true")
#     args = ap.parse_args()

#     os.makedirs(cfg.OUT_DIR, exist_ok=True)

#     if not args.skip_sync or not os.path.exists(cfg.MANIFEST_PATH):
#         print("=== Phase 1: sync ===")
#         sync.build_manifest()
#     else:
#         print("=== Phase 1: sync [skipped] ===")

#     print(f"\n=== Phase 2: perceive (frame {args.frame}) ===")
#     perc = perceive.run_frame(args.frame)
#     if perc is None:
#         print("[run] Phase 2 no output — abort")
#         sys.exit(1)

#     print(f"\n=== Phase 3: project (frame {args.frame}) ===")
#     proj = project.run_frame(args.frame)
#     if proj is None:
#         print("[run] Phase 3 no output — abort")
#         sys.exit(1)

#     print(f"\n=== Phase 4: match (frame {args.frame}) ===")
#     result = match.run_frame(args.frame)
#     if result is None:
#         print("[run] Phase 4 no match — abort")
#         sys.exit(1)

#     best = result["best_match"]
#     print(f"\n{'='*52}")
#     print(f"RESULT  frame={args.frame}")
#     print(f"  depth        {proj['depth_m']:.2f} m")
#     print(f"  target GPS   {proj['target_lat']:.6f}, {proj['target_lon']:.6f}")
#     print(f"  GOB match    {best['centroid_lat']:.6f}, {best['centroid_lon']:.6f}")
#     print(f"  score        {best['score']:.1f}/100")
#     print(f"  confidence   {best['confidence']}")
#     print(f"  gmaps        {proj['gmaps']}")
#     print(f"{'='*52}")


# if __name__ == "__main__":
#     main()





















# import argparse
# import os
# import sys
# import cv2
# import cfg
# import sync
# import perceive
# import project
# import match

# def main():
#     ap = argparse.ArgumentParser(description="Falcons building geo-association pipeline")
#     ap.add_argument("--frame",     type=int, default=840)
#     ap.add_argument("--skip-sync", action="store_true")
#     args = ap.parse_args()

#     os.makedirs(cfg.OUT_DIR, exist_ok=True)

#     if not args.skip_sync or not os.path.exists(cfg.MANIFEST_PATH):
#         print("=== Phase 1: sync ===")
#         sync.build_manifest()
#     else:
#         print("=== Phase 1: sync [skipped] ===")

#     print(f"\n=== Phase 2: perceive (frame {args.frame}) ===")
#     perc = perceive.run_frame(args.frame)
#     if perc is None:
#         print("[run] Phase 2 no output — abort")
#         sys.exit(1)

#     print(f"\n=== Phase 3: project (frame {args.frame}) ===")
#     proj = project.run_frame(args.frame)
#     if proj is None:
#         print("[run] Phase 3 no output — abort")
#         sys.exit(1)

#     print(f"\n=== Phase 4: match (frame {args.frame}) ===")
#     result = match.run_frame(args.frame)
#     if result is None:
#         print("[run] Phase 4 no match — abort")
#         sys.exit(1)

#     best = result["best_match"]
#     print(f"\n{'='*52}")
#     print(f"RESULT  frame={args.frame}")
#     print(f"  depth        {proj['depth_m']:.2f} m")
#     print(f"  target GPS   {proj['target_lat']:.6f}, {proj['target_lon']:.6f}")
#     print(f"  GOB match    {best['centroid_lat']:.6f}, {best['centroid_lon']:.6f}")
#     print(f"  score        {best['score']:.1f}/100")
#     print(f"  confidence   {best['confidence']}")
#     print(f"  gmaps        {proj['gmaps']}")
#     print(f"{'='*52}")

#     # =========================================================
#     # === NEW: FINAL PRESENTATION VISUALIZATION FOR THE GUIDE ===
#     # =========================================================
#     print("\n[run] Generating final presentation visual...")
#     img = cv2.imread(perc["vis"])
    
#     if img is not None:
#         h, w = img.shape[:2]
        
#         # 1. Car Position (Bottom Center of the image)
#         car_pt = (w // 2, h)
        
#         # 2. Building Target Point (Center of the YOLO bounding box)
#         box = perc["bbox_px"]
#         bldg_pt = (int((box[0] + box[2]) / 2), int((box[1] + box[3]) / 2))
        
#         # 3. Draw connecting line (Yellow) and a target dot (Orange)
#         cv2.line(img, car_pt, bldg_pt, (0, 255, 255), 4, cv2.LINE_AA)
#         cv2.circle(img, bldg_pt, 8, (0, 165, 255), -1) 
        
#         # 4. Calculate where to put the text box so it doesn't clip off screen
#         text_x = bldg_pt[0] + 20
#         if text_x > w - 400:  # If too far right, flip text to the left side
#             text_x = bldg_pt[0] - 420
            
#         text_y = bldg_pt[1] - 40
#         if text_y < 50: # If too high up, push it down
#             text_y = 50
        
#         font = cv2.FONT_HERSHEY_SIMPLEX
        
#         # Draw a semi-transparent black background box for text readability
#         overlay = img.copy()
#         cv2.rectangle(overlay, (text_x - 10, text_y - 30), (text_x + 440, text_y + 90), (0, 0, 0), -1)
#         cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)
        
#         # Write the Data!
#         cv2.putText(img, f"Depth: {proj['depth_m']:.1f}m", (text_x, text_y), font, 0.8, (0, 255, 255), 2)
#         cv2.putText(img, f"Est GPS: {proj['target_lat']:.5f}, {proj['target_lon']:.5f}", (text_x, text_y + 35), font, 0.6, (255, 255, 255), 1)
#         cv2.putText(img, f"GOB Match: {best['centroid_lat']:.5f}, {best['centroid_lon']:.5f}", (text_x, text_y + 70), font, 0.7, (0, 255, 0), 2)
        
#         # Save the final masterpiece
#         final_vis_path = os.path.join(cfg.OUT_DIR, f"frame_{args.frame:06d}_FINAL.jpg")
#         cv2.imwrite(final_vis_path, img)
#         print(f"[run] ✅ Saved presentation visual to -> {final_vis_path}")

# if __name__ == "__main__":
#     main()








































# import argparse
# import os
# import sys
# import cv2
# import cfg
# import sync
# import perceive
# import project
# import match


# def main():
#     ap = argparse.ArgumentParser(description="Falcons building geo-association pipeline")
#     ap.add_argument("--frame",     type=int, default=840)
#     ap.add_argument("--skip-sync", action="store_true")
#     args = ap.parse_args()

#     os.makedirs(cfg.OUT_DIR, exist_ok=True)

#     # ── Phase 1: Sync ─────────────────────────────────────────────────────
#     if not args.skip_sync or not os.path.exists(cfg.MANIFEST_PATH):
#         print("=== Phase 1: sync ===")
#         sync.build_manifest()
#     else:
#         print("=== Phase 1: sync [skipped] ===")

#     # ── Phase 2: Perceive ─────────────────────────────────────────────────
#     print(f"\n=== Phase 2: perceive (frame {args.frame}) ===")
#     perc = perceive.run_frame(args.frame)
#     if perc is None:
#         print("[run] Phase 2 no output — abort")
#         sys.exit(1)

#     # ── Phase 3: Project ──────────────────────────────────────────────────
#     print(f"\n=== Phase 3: project (frame {args.frame}) ===")
#     proj = project.run_frame(args.frame)
#     if proj is None:
#         print("[run] Phase 3 no output — abort")
#         sys.exit(1)

# #     # ── Phase 4: Match ────────────────────────────────────────────────────
#     print(f"\n=== Phase 4: match (frame {args.frame}) ===")
#     result = match.run_frame(args.frame)
#     if result is None:
#         print("[run] Phase 4 no match — abort")
#         sys.exit(1)

#     best = result["best_match"]

#     # --- Generate Batch Summary JSON ---
#     summary_data = {
#         "frame": args.frame,
#         "depth_m": proj['depth_m'],
#         "target_gps": [proj['target_lat'], proj['target_lon']],
#         "match_gps": [best['centroid_lat'], best['centroid_lon']],
#         "score": best['score'],
#         "confidence": best['confidence'],
#         "timestamp": args.saved_at if hasattr(args, 'saved_at') else "2026-04-17"
#     }
    
#     summary_dir = os.path.join(cfg.OUT_DIR, "summary")
#     os.makedirs(summary_dir, exist_ok=True)
#     summary_path = os.path.join(summary_dir, f"summary_{args.frame:06d}.json")
    
#     import json
#     with open(summary_path, "w") as f:
#         json.dump(summary_data, f, indent=4)
#     print(f"[run] ✅ Summary JSON -> {summary_path}")

#     print(f"\n{'='*52}")
#     print(f"RESULT  frame={args.frame}")
#     print(f"  depth        {proj['depth_m']:.2f} m")
#     print(f"  target GPS   {proj['target_lat']:.6f}, {proj['target_lon']:.6f}")
#     print(f"  GOB match    {best['centroid_lat']:.6f}, {best['centroid_lon']:.6f}")
#     print(f"  score        {best['score']:.1f}/100")
#     print(f"  confidence   {best['confidence']}")
#     print(f"  gmaps        {proj['gmaps']}")
#     print(f"{'='*52}")

#     # ── Final Presentation Visual ─────────────────────────────────────────
#     print("\n[run] Generating final presentation visual...")

#     # Organize perceive_vis vs final folders
#     vis_dir = os.path.join(cfg.OUT_DIR, "perceive_vis")
#     final_dir = os.path.join(cfg.OUT_DIR, "final")
#     os.makedirs(vis_dir, exist_ok=True)
#     os.makedirs(final_dir, exist_ok=True)

#     vis_path = perc.get("vis") or os.path.join(vis_dir, f"frame_{args.frame:06d}_perceive_vis.jpg")
#     img = cv2.imread(vis_path)

#     if img is not None:
#         h, w = img.shape[:2]
#         car_pt  = (w // 2, h)

#         box     = perc.get("bbox_px") or perc.get("bbox")
#         bldg_pt = (int((box[0] + box[2]) / 2), int((box[1] + box[3]) / 2))

#         cv2.line(img, car_pt, bldg_pt, (0, 255, 255), 4, cv2.LINE_AA)
#         cv2.circle(img, bldg_pt, 8, (0, 165, 255), -1)

#         text_x = bldg_pt[0] + 20
#         if text_x > w - 440:
#             text_x = bldg_pt[0] - 460
#         text_y = max(bldg_pt[1] - 40, 50)

#         font    = cv2.FONT_HERSHEY_SIMPLEX
#         overlay = img.copy()
#         cv2.rectangle(overlay, (text_x - 10, text_y - 30),
#                       (text_x + 460, text_y + 100), (0, 0, 0), -1)
#         cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)

#         cv2.putText(img, f"Depth: {proj['depth_m']:.1f}m",
#                     (text_x, text_y),      font, 0.8, (0, 255, 255), 2)
#         cv2.putText(img, f"Est GPS: {proj['target_lat']:.5f}, {proj['target_lon']:.5f}",
#                     (text_x, text_y + 35), font, 0.6, (255, 255, 255), 1)
#         cv2.putText(img, f"GOB Match: {best['centroid_lat']:.5f}, {best['centroid_lon']:.5f}",
#                     (text_x, text_y + 70), font, 0.7, (0, 255, 0), 2)

#         final_path = os.path.join(final_dir, f"frame_{args.frame:06d}_FINALio.jpg")
#         cv2.imwrite(final_path, img)
#         print(f"[run] ✅ Final visual → {final_path}")
#     else:
#         print(f"[run] ⚠️  Could not load vis image from {vis_path} — skipping final visual")


# if __name__ == "__main__":
#     main()

















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
    """Helper to save JSON files in specific subdirectories."""
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

    # ── Phase 1: Sync ─────────────────────────────────────────────────────
    if not args.skip_sync or not os.path.exists(cfg.MANIFEST_PATH):
        print("=== Phase 1: sync ===")
        sync.build_manifest()
    else:
        print("=== Phase 1: sync [skipped] ===")

    # ── Phase 2: Perceive ─────────────────────────────────────────────────
    print(f"\n=== Phase 2: perceive (frame {args.frame}) ===")
    perc = perceive.run_frame(args.frame)
    if perc is None:
        print("[run] Phase 2 no output — abort")
        sys.exit(1)
    # Save perceive output to perceive_json folder
    save_json(perc, "perceive_json", f"frame_{args.frame:06d}_perceive.json")

    # ── Phase 3: Project ──────────────────────────────────────────────────
    print(f"\n=== Phase 3: project (frame {args.frame}) ===")
    proj = project.run_frame(args.frame)
    if proj is None:
        print("[run] Phase 3 no output — abort")
        sys.exit(1)
    # Save project output to project_json folder
    save_json(proj, "project_json", f"frame_{args.frame:06d}_project.json")

    # ── Phase 4: Match ────────────────────────────────────────────────────
    print(f"\n=== Phase 4: match (frame {args.frame}) ===")
    result = match.run_frame(args.frame)
    if result is None:
        print("[run] Phase 4 no match — abort")
        sys.exit(1)
    # Save match output to match_json folder
    save_json(result, "match_json", f"frame_{args.frame:06d}_match.json")

    best = result["best_match"]

    # ── Phase 5: Batch Summary ───────────────────────────────────────────
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

    # ── Final Presentation Visual ─────────────────────────────────────────
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

        # UI Overlay Logic
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

        # Save to 'final' folder
        final_dir = os.path.join(cfg.OUT_DIR, "final")
        os.makedirs(final_dir, exist_ok=True)
        final_path = os.path.join(final_dir, f"frame_{args.frame:06d}_FINAL.jpg")
        
        cv2.imwrite(final_path, img)
        print(f"[run] ✅ Final visual → {final_path}")
    else:
        print(f"[run] ⚠️  Could not load image — skipping final visual")

if __name__ == "__main__":
    main()