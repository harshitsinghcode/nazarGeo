import argparse
import os
import sys
import cfg
import sync
import perceive
import project
import match


def main():
    ap = argparse.ArgumentParser(description="Building geo-association pipeline")
    ap.add_argument("--frame", type=int, default=5, help="Frame index to process")
    ap.add_argument("--skip-sync", action="store_true", help="Skip Phase 1 if manifest already exists")
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
        print("[run] Phase 2 produced no output — aborting")
        sys.exit(1)

    print(f"\n=== Phase 3: project (frame {args.frame}) ===")
    proj = project.run_frame(args.frame)
    if proj is None:
        print("[run] Phase 3 produced no output — aborting")
        sys.exit(1)

    print(f"\n=== Phase 4: match (frame {args.frame}) ===")
    result = match.run_frame(args.frame)
    if result is None:
        print("[run] Phase 4 produced no match — aborting")
        sys.exit(1)

    best = result["best_match"]
    print(f"\n{'='*50}")
    print(f"RESULT  frame={args.frame}")
    print(f"  depth       {proj['depth_m']:.2f} m")
    print(f"  target GPS  {proj['target_lat']:.6f}, {proj['target_lon']:.6f}")
    print(f"  OSM match   {best['centroid_lat']:.6f}, {best['centroid_lon']:.6f}")
    print(f"  score       {best['score']:.1f}/100")
    print(f"  gmaps       {proj['gmaps']}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()