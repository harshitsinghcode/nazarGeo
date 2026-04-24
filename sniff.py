import os
import json
import argparse
from collections import OrderedDict
import cfg

def load_all_matches(start_frame, end_frame):
    """Read all match JSON files and return a dict of unique buildings."""
    unique = OrderedDict()
    for fid in range(start_frame, end_frame + 1):
        match_path = os.path.join(cfg.OUT_DIR, f"match_json/frame_{fid:06d}_match.json")
        if not os.path.exists(match_path):
            continue
        with open(match_path) as f:
            data = json.load(f)
        best = data.get("best_match")
        if not best:
            continue
        lat = best["centroid_lat"]
        lon = best["centroid_lon"]
        key = f"{lat:.5f}_{lon:.5f}"
        if key in unique:
            if best["score"] > unique[key]["score"]:
                unique[key] = best
        else:
            unique[key] = best
        print(f"Frame {fid:06d}: processed, unique count = {len(unique)}")
    return list(unique.values())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=cfg.FRAME_START)
    ap.add_argument("--end", type=int, default=cfg.FRAME_END)
    ap.add_argument("--out", default="unique_buildings1.json")
    args = ap.parse_args()

    print(f"[aggregator] Scanning frames {args.start} to {args.end}...")
    buildings = load_all_matches(args.start, args.end)
    print(f"[aggregator] Total unique buildings: {len(buildings)}")

    for i, b in enumerate(buildings):
        b["id"] = f"gob_{i}"

    out_path = os.path.join(cfg.OUT_DIR, args.out)
    with open(out_path, "w") as f:
        json.dump(buildings, f, indent=2)
    print(f"[aggregator] Saved to {out_path}")

if __name__ == "__main__":
    main()