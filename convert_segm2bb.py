import os
import cv2
from dotenv import load_dotenv

load_dotenv()

DATASET_DIR = os.getenv("DATASET_DIR")
MASKS_DIR = os.path.join(DATASET_DIR, "masks")
LABELS_DIR = os.path.join(DATASET_DIR, "labels") 

CLASS_ID = 0  
MIN_AREA = 5

os.makedirs(LABELS_DIR, exist_ok=True)

def mask_to_yolo():
    mask_files = [f for f in os.listdir(MASKS_DIR) if f.endswith(('.png', '.jpg'))]
    
    for mask_name in mask_files:
        mask_path = os.path.join(MASKS_DIR, mask_name)
        
        # Load mask in grayscale
        mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
        if mask is None:
            continue
            
        img_height, img_width = mask.shape
        
        # RETR_EXTERNAL to only get the outer boundary of the holes
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        base_num = mask_name.split('_')[-1].split('.')[0] 
        txt_name = f"file_namergb_{base_num}.txt" 
        txt_path = os.path.join(LABELS_DIR, txt_name)
        
        with open(txt_path, 'w') as f:
            for cnt in contours:
                if cv2.contourArea(cnt) < MIN_AREA:
                    continue
                    
                x, y, w, h = cv2.boundingRect(cnt)
                
                x_center = (x + (w / 2)) / img_width
                y_center = (y + (h / 2)) / img_height
                norm_width = w / img_width
                norm_height = h / img_height
                
        
                f.write(f"{CLASS_ID} {x_center:.6f} {y_center:.6f} {norm_width:.6f} {norm_height:.6f}\n")
                
    print(f"Converted {len(mask_files)} masks to YOLO_BBs in {LABELS_DIR}")

if __name__ == "__main__":
    mask_to_yolo()
