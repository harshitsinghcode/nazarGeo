# presniff.py - fixed: in-process, LiDAR cached, all 4 steps

import os
import argparse
import cfg
import lidar_pcap
import sync
import perceive
import project
import match

def process_frames(start, end, step):
    os.makedirs(cfg.OUT_DIR, exist_ok=True)
    os.makedirs(os.path.join(cfg.OUT_DIR, "perceive_json"), exist_ok=True)
    os.makedirs(os.path.join(cfg.OUT_DIR, "perceive_vis"), exist_ok=True)
    os.makedirs(os.path.join(cfg.OUT_DIR, "project_json"), exist_ok=True)
    os.makedirs(os.path.join(cfg.OUT_DIR, "match_json"),   exist_ok=True)
    os.makedirs(os.path.join(cfg.OUT_DIR, "raw"),          exist_ok=True)

    # Step 0: build manifest once
    print("=== Building manifest ===")
    sync.build_manifest()

    # Step 1: pre-load LiDAR ONCE — cached in lidar_pcap._cache
    print("=== Pre-loading LiDAR (one-time, ~45M pts) ===")
    lidar_pcap.load_both(cfg.L1_PCAP_PATH, cfg.L2_PCAP_PATH)
    print("=== LiDAR cached. Starting frame loop ===\n")

    total   = len(range(start, end + 1, step))
    success = 0
    skipped = 0

    for i, fid in enumerate(range(start, end + 1, step)):
        print(f"\n{'='*52}")
        print(f"  Frame {fid:06d}  ({i+1}/{total})")
        print(f"{'='*52}")

        # ── perceive ──────────────────────────────────────────
        try:
            perc = perceive.run_frame(fid)
        except FileNotFoundError as e:
            print(f"  [SKIP] image missing: {e}")
            skipped += 1
            continue
        except Exception as e:
            print(f"  [SKIP] perceive error: {e}")
            skipped += 1
            continue

        if perc is None:
            print(f"  [SKIP] no building detected")
            skipped += 1
            continue

        # ── project ───────────────────────────────────────────
        try:
            proj = project.run_frame(fid)
        except Exception as e:
            print(f"  [SKIP] project error: {e}")
            skipped += 1
            continue

        if proj is None:
            print(f"  [SKIP] project returned None")
            skipped += 1
            continue

        # ── match ─────────────────────────────────────────────
        try:
            result = match.run_frame(fid)
        except Exception as e:
            print(f"  [WARN] match error: {e}")
            continue   # don't skip — perceive+project still saved

        if result is None:
            print(f"  [WARN] no GOB match found")
            continue

        success += 1
        best = result["best_match"]
        print(f"  ✓ score={best['score']:.1f}  "
              f"GPS=({best['centroid_lat']:.6f}, {best['centroid_lon']:.6f})")

    print(f"\n{'='*52}")
    print(f"DONE  {success} matched / {skipped} skipped / {total} total")
    print(f"Run:  python sniff.py --start {start} --end {end}")
    print(f"{'='*52}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=cfg.FRAME_START)
    ap.add_argument("--end",   type=int, default=cfg.FRAME_END)
    ap.add_argument("--step",  type=int, default=25)
    args = ap.parse_args()
    process_frames(args.start, args.end, args.step)