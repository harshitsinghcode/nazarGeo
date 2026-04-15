# import os

# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# OUT_DIR  = os.path.join(BASE_DIR, "out")

# KITTI_ROOT      = os.path.join("data", "raw", "kitti")
# KITTI_DATE      = "2011_09_26"
# KITTI_DRIVE     = "2011_09_26_drive_0005_sync"
# KITTI_CALIB_DIR = os.path.join(KITTI_ROOT, KITTI_DATE)
# KITTI_DRIVE_DIR = os.path.join(KITTI_ROOT, KITTI_DATE, KITTI_DRIVE)

# IMU_CSV_PATH   = os.path.join(KITTI_ROOT, "imu_all_topics.csv")
# MANIFEST_PATH  = os.path.join(OUT_DIR, "manifest.json")

# KITTI_FPS        = 10.0
# KITTI_START_FRAME = 0
# KITTI_END_FRAME  = 153

# YOLO_MODEL       = "yolov8s-world.pt"
# SAM_MODEL        = "mobile_sam.pt"
# YOLO_CLASSES     = ["building", "house", "commercial building", "brick wall", "facade"]
# YOLO_CONF        = 0.10
# YOLO_IOU         = 0.50

# OSM_RADIUS_M     = 100
# ANGLE_CONE_DEG   = 30.0

# SCORE_ANGLE_MAX  = 40.0
# SCORE_PROX_MAX   = 40.0
# SCORE_WIDTH_MAX  = 20.0
# PROX_DECAY_M     = 20.0

# CAMERA_HFOV_DEG  = 90.0

#--------------------------------------------

# import os

# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# OUT_DIR  = os.path.join(BASE_DIR, "out")

# LENS1_DIR    = r"C:\Users\Admin\Desktop\falcons\mine\LENS1"
# IMU_CSV_PATH = r"C:\Users\Admin\Desktop\falcons\mine\19012026_imu_gnss_sliced_740_to_940.csv"
# L1_PCAP_PATH = r"C:\Users\Admin\Desktop\falcons\l1_sliced_740_to_940.pcap"
# L2_PCAP_PATH = r"C:\Users\Admin\Desktop\falcons\l2_sliced_740_to_940.pcap"
# GOB_CSV_PATH = r"C:\Users\Admin\Desktop\falcons\gob_india.csv"

# MANIFEST_PATH = os.path.join(OUT_DIR, "manifest.json")

# FRAME_START = 740
# FRAME_END   = 940
# CAMERA_FPS  = 30.0

# IMG_W = 1920
# IMG_H = 1080
# HFOV_DEG  = 90.0
# VFOV_DEG  = 60.0

# FX = IMG_W / (2 * __import__('math').tan(__import__('math').radians(HFOV_DEG / 2)))
# FY = IMG_H / (2 * __import__('math').tan(__import__('math').radians(VFOV_DEG / 2)))
# CX = IMG_W / 2.0
# CY = IMG_H / 2.0

# LIDAR_TO_CAM_X_OFFSET = 0.0
# LIDAR_TO_CAM_Y_OFFSET = 0.0
# LIDAR_TO_CAM_Z_OFFSET = 0.0

# YOLO_MODEL    = "yolov8s-world.pt"
# SAM_MODEL     = "mobile_sam.pt"
# YOLO_CLASSES  = ["building", "house", "commercial building", "brick wall", "facade"]
# YOLO_CONF     = 0.10
# YOLO_IOU      = 0.50

# FALLBACK_CLASSES = [
#     "building", "house", "commercial building", "brick wall", "facade",
#     "wall", "structure", "apartment", "office building", "storefront",
#     "architecture", "construction"
# ]
# FALLBACK_CONF = 0.05

# GOB_RADIUS_M    = 100
# ANGLE_CONE_DEG  = 30.0
# GOB_CONF_MIN    = 0.0

# SCORE_ANGLE_MAX = 40.0
# SCORE_PROX_MAX  = 40.0
# SCORE_WIDTH_MAX = 20.0
# PROX_DECAY_M    = 20.0

#------------------------------------------------------------------

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR  = os.path.join(BASE_DIR, "out")

LENS1_DIR    = r"C:\Users\Admin\Desktop\falcons\mine\LENS1"
IMU_CSV_PATH = r"C:\Users\Admin\Desktop\falcons\mine\19012026_imu_gnss_sliced_740_to_940.csv"
L1_PCAP_PATH = r"C:\Users\Admin\Desktop\falcons\l1_sliced_740_to_940.pcap"
L2_PCAP_PATH = r"C:\Users\Admin\Desktop\falcons\l2_sliced_740_to_940.pcap"
GOB_CSV_PATH = r"C:\Users\Admin\Desktop\falcons\gob_india.csv"

MANIFEST_PATH = os.path.join(OUT_DIR, "manifest.json")

# --- FIXED FRAME SYNCHRONIZATION ---
FRAME_START = 1
FRAME_END   = 3599
CAMERA_FPS  = 30.0
# -----------------------------------

IMG_W = 1920
IMG_H = 1080
HFOV_DEG  = 90.0
VFOV_DEG  = 60.0

FX = IMG_W / (2 * __import__('math').tan(__import__('math').radians(HFOV_DEG / 2)))
FY = IMG_H / (2 * __import__('math').tan(__import__('math').radians(VFOV_DEG / 2)))
CX = IMG_W / 2.0
CY = IMG_H / 2.0

LIDAR_TO_CAM_X_OFFSET = 0.0
LIDAR_TO_CAM_Y_OFFSET = 0.0
LIDAR_TO_CAM_Z_OFFSET = 0.0

YOLO_MODEL    = "yolov8s-world.pt"
SAM_MODEL     = "mobile_sam.pt"
YOLO_CLASSES  = ["building", "house", "commercial building", "brick wall", "facade"]
YOLO_CONF     = 0.10
YOLO_IOU      = 0.50

FALLBACK_CLASSES = [
    "building", "house", "commercial building", "brick wall", "facade",
    "wall", "structure", "apartment", "office building", "storefront",
    "architecture", "construction"
]
FALLBACK_CONF = 0.05

GOB_RADIUS_M    = 100
ANGLE_CONE_DEG  = 30.0
GOB_CONF_MIN    = 0.0

SCORE_ANGLE_MAX = 40.0
SCORE_PROX_MAX  = 40.0
SCORE_WIDTH_MAX = 20.0
PROX_DECAY_M    = 20.0

# ----------------------------------------------------------------------------

# import os

# BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# OUT_DIR  = os.path.join(BASE_DIR, "out")

# LENS1_DIR    = r"C:\Users\Admin\Desktop\falcons\mine\LENS1"
# IMU_CSV_PATH = r"C:\Users\Admin\Desktop\falcons\mine\19012026_imu_gnss_sliced_740_to_940.csv"
# L1_PCAP_PATH = r"C:\Users\Admin\Desktop\falcons\l1_sliced_740_to_940.pcap"
# L2_PCAP_PATH = r"C:\Users\Admin\Desktop\falcons\l2_sliced_740_to_940.pcap"
# GOB_CSV_PATH = r"C:\Users\Admin\Desktop\falcons\gob_india.csv"

# MANIFEST_PATH = os.path.join(OUT_DIR, "manifest.json")

# FRAME_START = 740
# FRAME_END   = 940
# CAMERA_FPS  = 30.0

# IMG_W = 1920
# IMG_H = 1080

# HFOV_DEG = 185.0
# VFOV_DEG = 185.0

# _math = __import__('math')
# FX = IMG_W / (2 * _math.tan(_math.radians(min(HFOV_DEG, 179.0) / 2)))
# FY = IMG_H / (2 * _math.tan(_math.radians(min(VFOV_DEG, 179.0) / 2)))
# CX = IMG_W / 2.0
# CY = IMG_H / 2.0

# FISHEYE_K1 = -0.35
# FISHEYE_K2 =  0.12
# FISHEYE_K3 =  0.0
# FISHEYE_K4 =  0.0

# LIDAR_YAW_DEG         =  180
# LIDAR_TO_CAM_X_OFFSET =  0.0
# LIDAR_TO_CAM_Y_OFFSET =  0.0
# LIDAR_TO_CAM_Z_OFFSET =  0.0

# IMAGE_BUILDING_SIDE = "right"

# YOLO_MODEL    = "yolov8s-world.pt"
# SAM_MODEL     = "mobile_sam.pt"
# YOLO_CLASSES  = ["building", "house", "commercial building", "brick wall", "facade"]
# YOLO_CONF     = 0.10
# YOLO_IOU      = 0.50

# FALLBACK_CLASSES = [
#     "building", "house", "commercial building", "brick wall", "facade",
#     "wall", "structure", "apartment", "office building", "storefront",
#     "architecture", "construction"
# ]
# FALLBACK_CONF = 0.05

# GOB_RADIUS_M    = 100
# ANGLE_CONE_DEG  = 30.0
# GOB_CONF_MIN    = 0.0

# SCORE_ANGLE_MAX = 40.0
# SCORE_PROX_MAX  = 40.0
# SCORE_WIDTH_MAX = 20.0
# PROX_DECAY_M    = 20.0