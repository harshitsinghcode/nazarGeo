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





















import argparse
import os
import sys
import cv2
import cfg
import sync
import perceive
import project
import match

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

    print(f"\n=== Phase 3: project (frame {args.frame}) ===")
    proj = project.run_frame(args.frame)
    if proj is None:
        print("[run] Phase 3 no output — abort")
        sys.exit(1)

    print(f"\n=== Phase 4: match (frame {args.frame}) ===")
    result = match.run_frame(args.frame)
    if result is None:
        print("[run] Phase 4 no match — abort")
        sys.exit(1)

    best = result["best_match"]
    print(f"\n{'='*52}")
    print(f"RESULT  frame={args.frame}")
    print(f"  depth        {proj['depth_m']:.2f} m")
    print(f"  target GPS   {proj['target_lat']:.6f}, {proj['target_lon']:.6f}")
    print(f"  GOB match    {best['centroid_lat']:.6f}, {best['centroid_lon']:.6f}")
    print(f"  score        {best['score']:.1f}/100")
    print(f"  confidence   {best['confidence']}")
    print(f"  gmaps        {proj['gmaps']}")
    print(f"{'='*52}")

    # =========================================================
    # === NEW: FINAL PRESENTATION VISUALIZATION FOR THE GUIDE ===
    # =========================================================
    print("\n[run] Generating final presentation visual...")
    img = cv2.imread(perc["vis"])
    
    if img is not None:
        h, w = img.shape[:2]
        
        # 1. Car Position (Bottom Center of the image)
        car_pt = (w // 2, h)
        
        # 2. Building Target Point (Center of the YOLO bounding box)
        box = perc["bbox_px"]
        bldg_pt = (int((box[0] + box[2]) / 2), int((box[1] + box[3]) / 2))
        
        # 3. Draw connecting line (Yellow) and a target dot (Orange)
        cv2.line(img, car_pt, bldg_pt, (0, 255, 255), 4, cv2.LINE_AA)
        cv2.circle(img, bldg_pt, 8, (0, 165, 255), -1) 
        
        # 4. Calculate where to put the text box so it doesn't clip off screen
        text_x = bldg_pt[0] + 20
        if text_x > w - 400:  # If too far right, flip text to the left side
            text_x = bldg_pt[0] - 420
            
        text_y = bldg_pt[1] - 40
        if text_y < 50: # If too high up, push it down
            text_y = 50
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        # Draw a semi-transparent black background box for text readability
        overlay = img.copy()
        cv2.rectangle(overlay, (text_x - 10, text_y - 30), (text_x + 440, text_y + 90), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, img, 0.3, 0, img)
        
        # Write the Data!
        cv2.putText(img, f"Depth: {proj['depth_m']:.1f}m", (text_x, text_y), font, 0.8, (0, 255, 255), 2)
        cv2.putText(img, f"Est GPS: {proj['target_lat']:.5f}, {proj['target_lon']:.5f}", (text_x, text_y + 35), font, 0.6, (255, 255, 255), 1)
        cv2.putText(img, f"GOB Match: {best['centroid_lat']:.5f}, {best['centroid_lon']:.5f}", (text_x, text_y + 70), font, 0.7, (0, 255, 0), 2)
        
        # Save the final masterpiece
        final_vis_path = os.path.join(cfg.OUT_DIR, f"frame_{args.frame:06d}_FINAL.jpg")
        cv2.imwrite(final_vis_path, img)
        print(f"[run] ✅ Saved presentation visual to -> {final_vis_path}")

if __name__ == "__main__":
    main()