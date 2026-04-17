import cv2
import numpy as np
from ultralytics import YOLO, SAM

# ==========================================
# TEST TARGET
# ==========================================
FRAME_NUM = 840
IMG_PATH = rf"C:\Users\Admin\Desktop\falcons\mine\LENS1\frame_{FRAME_NUM:06d}.jpg"
OUT_PATH = rf"C:\Users\Admin\Desktop\n3\out\isolated_building_{FRAME_NUM}.png"

# Same robust settings from your cfg.py
YOLO_CLASSES = ["building", "house", "commercial building", "brick wall", "facade"]
FALLBACK_CLASSES = [
    "building", "house", "commercial building", "brick wall", "facade",
    "wall", "structure", "apartment", "office building", "storefront",
    "architecture", "construction"
]

print(f"🔍 Loading models to inspect frame {FRAME_NUM}...")
yolo = YOLO("yolov8s-world.pt")
sam = SAM("mobile_sam.pt")

img = cv2.imread(IMG_PATH)
if img is None:
    print(f"❌ Could not find image at {IMG_PATH}")
    exit()

# --- PASS 1: PRIMARY ---
yolo.set_classes(YOLO_CLASSES)
res = yolo(img, conf=0.30, iou=0.50, verbose=False)
boxes = res[0].boxes.xyxy.cpu().numpy()
confs = res[0].boxes.conf.cpu().numpy()

# --- PASS 2: FALLBACK ---
if len(boxes) == 0:
    print("⚠️ Primary pass failed. Engaging fallback...")
    yolo.set_classes(FALLBACK_CLASSES)
    res = yolo(img, conf=0.12, iou=0.50, verbose=False)
    boxes = res[0].boxes.xyxy.cpu().numpy()
    confs = res[0].boxes.conf.cpu().numpy()

if len(boxes) == 0:
    print("❌ No buildings detected at all! Check your confidence thresholds.")
    exit()

# --- LOCK ONTO BEST TARGET ---
best_idx = int(np.argmax(confs))
target_box = boxes[best_idx:best_idx+1]
target_conf = confs[best_idx]

print(f"🎯 Locked onto primary target with {target_conf:.0%} confidence.")
print("✂️  Running SAM to cut out the building...")

# --- RUN SAM ---
sam_res = sam(IMG_PATH, bboxes=target_box, verbose=False)

# Get the raw 2D mask and resize it to match the original image size exactly
mask = sam_res[0].masks.data[0].cpu().numpy()

# --- THE FIX: Convert True/False to 1/0 for OpenCV ---
mask = mask.astype(np.uint8) 

mask = cv2.resize(mask, (img.shape[1], img.shape[0]), interpolation=cv2.INTER_NEAREST)

# --- CREATE TRANSPARENT PNG ---
# Split the original image into Blue, Green, Red channels
b, g, r = cv2.split(img)

# Create an Alpha (transparency) channel. 
# Everywhere the mask is 1, alpha is 255 (solid). Everywhere it's 0, alpha is 0 (invisible).
alpha = (mask * 255).astype(np.uint8)

# Merge back into a 4-channel RGBA image
rgba = cv2.merge([b, g, r, alpha])

# --- CROP OUT THE EMPTY SPACE ---
# We don't need a massive 4K image if the building is just in one corner.
x1, y1, x2, y2 = map(int, target_box[0])

# Ensure boundaries don't accidentally go off-screen
x1, y1 = max(0, x1), max(0, y1)
x2, y2 = min(img.shape[1], x2), min(img.shape[0], y2)

cropped_building = rgba[y1:y2, x1:x2]

# Save it! (MUST be .png to keep the transparent background)
cv2.imwrite(OUT_PATH, cropped_building)
print(f"✅ SUCCESS! Isolated building saved to: {OUT_PATH}")