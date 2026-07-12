from pathlib import Path
import cv2
import numpy as np

def check_mask(mask):
    if len(mask.shape) != 2:
        return False

    unique_values = np.unique(mask)
    if (
        not np.array_equal(unique_values, [0, 255])
        and not np.array_equal(unique_values, [0])
        and not np.array_equal(unique_values, [255])
    ):
        return False

    return True

if __name__ == "__main__":
    masks_dir = Path("sample200/masks")

    mask_files = sorted(masks_dir.glob("*[0-9].png"))

    valid_masks = []
    invalid_masks = []

    for file_path in mask_files:
        mask = cv2.imread(str(file_path), cv2.IMREAD_GRAYSCALE)

        if mask is None:
            print(f"Could not read {file_path.name}")
            continue

        if check_mask(mask):
            valid_masks.append(file_path)
            print(f"Valid: {file_path.name}")
        else:
            invalid_masks.append(file_path)
            print(f"Invalid: {file_path.name} (Values: {np.unique(mask)})")

    print(f"\n{len(valid_masks)} valid masks and {len(invalid_masks)} invalid masks.")