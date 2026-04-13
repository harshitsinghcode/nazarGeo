import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR  = os.path.join(BASE_DIR, "out")

KITTI_ROOT      = os.path.join("data", "raw", "kitti")
KITTI_DATE      = "2011_09_26"
KITTI_DRIVE     = "2011_09_26_drive_0005_sync"
KITTI_CALIB_DIR = os.path.join(KITTI_ROOT, KITTI_DATE)
KITTI_DRIVE_DIR = os.path.join(KITTI_ROOT, KITTI_DATE, KITTI_DRIVE)

IMU_CSV_PATH   = os.path.join(KITTI_ROOT, "imu_all_topics.csv")
MANIFEST_PATH  = os.path.join(OUT_DIR, "manifest.json")

KITTI_FPS        = 10.0
KITTI_START_FRAME = 0
KITTI_END_FRAME  = 153

YOLO_MODEL       = "yolov8s-world.pt"
SAM_MODEL        = "mobile_sam.pt"
YOLO_CLASSES     = ["building", "house", "commercial building", "brick wall", "facade"]
YOLO_CONF        = 0.10
YOLO_IOU         = 0.50

OSM_RADIUS_M     = 100
ANGLE_CONE_DEG   = 30.0

SCORE_ANGLE_MAX  = 40.0
SCORE_PROX_MAX   = 40.0
SCORE_WIDTH_MAX  = 20.0
PROX_DECAY_M     = 20.0

CAMERA_HFOV_DEG  = 90.0