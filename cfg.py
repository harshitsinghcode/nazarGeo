import os
import math

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR  = os.path.join(BASE_DIR, "outi")           # ← your updated output folder name

LENS1_DIR    = r"C:\Users\Admin\Desktop\falcons\mine\LENS1_fixed"
IMU_CSV_PATH = r"C:\Users\Admin\Desktop\falcons\mine\19012026_imu_gnss_sliced_740_to_940.csv"
L1_PCAP_PATH = r"C:\Users\Admin\Desktop\falcons\l1_sliced_740_to_940.pcap"
L2_PCAP_PATH = r"C:\Users\Admin\Desktop\falcons\l2_sliced_740_to_940.pcap"
GOB_CSV_PATH = r"C:\Users\Admin\Desktop\falcons\gob_india.csv"

MANIFEST_PATH = os.path.join(OUT_DIR, "manifest.json")

FRAME_START = 1
FRAME_END   = 3599
CAMERA_FPS  = 30.0

IMG_W = 3840
IMG_H = 2160

FX = 1106.46
FY = 1077.77
CX = 1920.0    
CY = 1080.0    

HFOV_DEG = math.degrees(2 * math.atan2(IMG_W / 2, FX))

T_LIDAR_TO_CAM = [
    [ 0.20927,    -0.977663,  -0.0195126,  2.05416  ],
    [ 0.0386136,   0.0282009, -0.998856,   0.401883 ],
    [ 0.977095,    0.208277,   0.0436527, -0.035744 ],
    [ 0.0,         0.0,        0.0,        1.0      ],
]

T_L2_TO_L1 = [
    [ 0.9997594356536865,    0.020968914031982422, -0.0064355251379311085, -0.11370490491390228 ],
    [-0.021027371287345886,  0.9997369647026062,   -0.009154382161796093,   0.9193867444992065  ],
    [ 0.006241875234991312,  0.009287501685321331,  0.9999374151229858,    -0.001643864088691771],
    [ 0.0,                   0.0,                   0.0,                    1.0                 ],
]

YOLO_MODEL    = "yolov8s-world.pt"
SAM_MODEL     = "mobile_sam.pt"
YOLO_CONF     = 0.25
YOLO_IOU      = 0.45
FALLBACK_CONF = 0.10

YOLO_CLASSES = [
    "building", "house", "commercial building",
    "brick wall", "facade", "multi-storey building",
    "concrete building", "flat roof building",
]
FALLBACK_CLASSES = [
    "building", "house", "wall", "structure",
    "apartment", "office building", "storefront",
    "architecture", "concrete structure",
    "terrace building", "construction",
]

GOB_RADIUS_M   = 150     
ANGLE_CONE_DEG = 35.0     
GOB_CONF_MIN   = 0.0      
SCORE_ANGLE_MAX = 50.0
SCORE_PROX_MAX  = 30.0
SCORE_WIDTH_MAX = 15.0
PROX_DECAY_M    =  5.0   
PROJECTION_LAT_OFFSET = 0.0 
PROJECTION_LON_OFFSET = 0.0 
ALONG_RAY_OFFSET_M = 25.00
CROSS_RAY_OFFSET_M = -6.00