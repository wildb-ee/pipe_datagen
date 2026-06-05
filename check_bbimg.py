import os
import cv2
from dotenv import load_dotenv

load_dotenv()

DATASET_DIR = os.getenv("DATASET_DIR")
IMAGES_DIR = os.path.join(DATASET_DIR, "rgb_images")
LABELS_DIR = os.path.join(DATASET_DIR, "labels")

SAMPLE_NUMBER = "0002" 

IMAGE_NAME = f"file_namergb_{SAMPLE_NUMBER}.png"
LABEL_NAME = f"file_namergb_{SAMPLE_NUMBER}.txt"

# (must match dataset.yaml)
CLASS_NAMES = {
    0: "corrosion_hole"
}
# Bounding box color (B, G, R) -> Green
BOX_COLOR = (0, 255, 0) 

def visualize_sample():
    img_path = os.path.join(IMAGES_DIR, IMAGE_NAME)
    lbl_path = os.path.join(LABELS_DIR, LABEL_NAME)
    
    img = cv2.imread(img_path)
    if img is None:
        print(f"Error: Could not look up image at {img_path}")
        return
        
    img_h, img_w, _ = img.shape
    
    if not os.path.exists(lbl_path):
        print(f"ACHTUNG: No label file found at {lbl_path}.")
    else:
        with open(lbl_path, 'r') as f:
            lines = f.readlines()
            
        for line in lines:
            parts = line.strip().split()
            if len(parts) != 5:
                continue
                
            class_id = int(parts[0])
            x_center = float(parts[1])
            y_center = float(parts[2])
            norm_w = float(parts[3])
            norm_h = float(parts[4])
            
            w = int(norm_w * img_w)
            h = int(norm_h * img_h)
            x1 = int((x_center * img_w) - (w / 2))
            y1 = int((y_center * img_h) - (h / 2))
            x2 = x1 + w
            y2 = y1 + h
            
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(img_w, x2), min(img_h, y2)
            
            cv2.rectangle(img, (x1, y1), (x2, y2), BOX_COLOR, 2)
            
            class_text = CLASS_NAMES.get(class_id, f"Class {class_id}")
            label_y = y1 - 5 if y1 - 5 > 15 else y1 + 15  # text inside frame if too high
            cv2.putText(img, class_text, (x1, label_y), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, BOX_COLOR, 1)

    window_name = f"YOLO_sample{SAMPLE_NUMBER}"
    cv2.imshow(window_name, img)
    
    print("Press any key while focusing on the image window to close it...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    visualize_sample()
