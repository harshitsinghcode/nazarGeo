n3 — building geo-association pipeline

FILE STRUCTURE
--------------
n3/
├── cfg.py          all paths, thresholds, model names, score weights
├── sync.py         phase 1 — IMU CSV → manifest.json
├── perceive.py     phase 2 — YOLO-World + MobileSAM + LiDAR → depth + bbox
├── project.py      phase 3 — ego pose + depth → target GPS coordinate
├── match.py        phase 4 — OSM query + 3-term scorer → matched polygon
├── run.py          orchestrator — runs all 4 phases for a single frame
└── out/
    ├── manifest.json
    ├── frame_NNNN_perceive.json
    ├── frame_NNNN_project.json
    ├── frame_NNNN_match.json
    └── frame_NNNN_vis.jpg

EXPECTED DATA LAYOUT
--------------------
data/raw/kitti/
├── imu_all_topics.csv
└── 2011_09_26/
    ├── calib_cam_to_cam.txt
    ├── calib_velo_to_cam.txt
    └── 2011_09_26_drive_0005_sync/
        ├── image_02/data/0000000000.png ... 0000000153.png
        └── velodyne_points/data/0000000000.bin ... 0000000153.bin

USAGE
-----
run from the project root (parent of n3/):

    python n3/run.py --frame 5

skip phase 1 if manifest already exists:

    python n3/run.py --frame 5 --skip-sync

run a phase standalone:

    python n3/sync.py
    python n3/perceive.py --frame 5
    python n3/project.py  --frame 5
    python n3/match.py    --frame 5

SCORING (phase 4)
-----------------
total score = angle_score + prox_score + width_score  (max 100)

  angle_score  0–40   penalises angular offset from vehicle heading
  prox_score   0–40   exponential decay:  40 * exp(-dist / 20m)
  width_score  0–20   ratio of detected bbox width vs expected angular footprint width

all weights are in cfg.py (SCORE_ANGLE_MAX, SCORE_PROX_MAX, SCORE_WIDTH_MAX, PROX_DECAY_M)

YAW NOTE
--------
heading_deg in the manifest is passed directly to geodesic().destination().
KITTI oxts yaw is already NED/compass (0=North, CW positive).
No (90 - yaw) conversion is applied.

DEPENDENCIES
------------
pip install ultralytics geopy osmnx opencv-python scipy pandas numpy