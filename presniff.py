import os
import subprocess
import argparse
import cfg

def run_command(cmd):
    print(f"\n[CMD] {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=False)
    if result.returncode != 0:
        print(f"[ERROR] Command failed with code {result.returncode}")
    return result.returncode

def process_frames(start, end, step):
    os.makedirs(cfg.OUT_DIR, exist_ok=True)
    for fid in range(start, end + 1, step):
        print(f"\n{'='*50}")
        print(f"Processing frame {fid:06d} (step {step})")
        print('='*50)

        # 1. Perceive
        ret = run_command(f"python perceive.py --frame {fid}")
        if ret != 0:
            print(f"[SKIP] Frame {fid} perception failed, skipping match.")
            continue

        # 2. Match
        ret = run_command(f"python match.py --frame {fid}")
        if ret != 0:
            print(f"[WARN] Frame {fid} match failed, but continuing.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=cfg.FRAME_START)
    ap.add_argument("--end",   type=int, default=cfg.FRAME_END)
    ap.add_argument("--step",  type=int, default=25)
    args = ap.parse_args()
    process_frames(args.start, args.end, args.step)