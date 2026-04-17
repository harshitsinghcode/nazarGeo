import os
import cv2

# INPUT & OUTPUT PATHS
input_folder = r"C:\Users\Admin\Desktop\falcons\mine\LENS1"
output_folder = r"C:\Users\Admin\Desktop\falcons\mine\LENS1_fixed"

# Create output folder if not exists
os.makedirs(output_folder, exist_ok=True)

# Choose rotation:
# cv2.ROTATE_90_CLOCKWISE
# cv2.ROTATE_90_COUNTERCLOCKWISE
# cv2.ROTATE_180

ROTATION_TYPE = cv2.ROTATE_90_COUNTERCLOCKWISE  

count = 0

for filename in os.listdir(input_folder):
    if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
        
        input_path = os.path.join(input_folder, filename)
        output_path = os.path.join(output_folder, filename)

        # Read image
        img = cv2.imread(input_path)

        if img is None:
            print(f"❌ Skipped (can't read): {filename}")
            continue

        # Rotate image
        rotated = cv2.rotate(img, ROTATION_TYPE)

        # Save image
        cv2.imwrite(output_path, rotated)

        count += 1
        print(f"✅ Processed: {filename}")

print(f"\n🎉 Done! Total images processed: {count}")