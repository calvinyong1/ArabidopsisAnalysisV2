import cv2
import cv2.aruco as aruco
import numpy as np
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from singlePlantAnalysis.analysis.qr import aruco_detect

# Open folder_path and return every image as a list
def get_input_folder(folder_path):
    folder_path = pathlib.Path(folder_path)
    extensions = {".png",".tif",".tiff"}
    
    matching_files = sorted(
        p for p in folder_path.glob("*") 
        if p.is_file() and p.suffix.lower() in extensions
    )
    
    return matching_files

# Detect the marker corners in each image and return them as a list
def detect_marker_corners(image_paths):
    marker_corners = [] # Array of coordinates of the marker in each frame with shape (N,1,4,2)
    for image in image_paths:
        corners = aruco_detect(str(image))
        
        if corners is None:
            print(f"Warning: no marker detected in {image.name}")
            marker_corners.append(None)
        else:
            marker_corners.append(corners)
        
    return marker_corners

# Aligns images to the aruco marker in the first frame
def compute_transforms(marker_corners):
    if marker_corners[0] is None:
        raise ValueError("No ArUco marker detected in the first frame — cannot establish reference.")
    
    # The first image is used as the reference point
    reference = marker_corners[0][0][0].astype(np.float32)
    transforms = [] # Array of transformation that needs to be applied to each image
    
    for i, corners in enumerate(marker_corners):
        if corners is None:
            transforms.append(None)
        else:
            current = corners[0][0].astype(np.float32)
            ref_centroid = np.mean(reference, axis=0)
            cur_centroid = np.mean(current, axis=0)
            tx = ref_centroid[0] - cur_centroid[0]
            ty = ref_centroid[1] - cur_centroid[1]
            M = np.float32([[1, 0, tx], [0, 1, ty]])
            transforms.append(M)
    
    return transforms
            
def apply_transforms(image_paths,transform_matrices):
    # Create the output directory
    output_folder = pathlib.Path(image_paths[0]).parent / "aligned"
    output_folder.mkdir(exist_ok=True)
    
    for i in range(0,len(image_paths)):
        file_name = os.path.basename(image_paths[i])
        name, extension = os.path.splitext(file_name)
        file_name = name + "_aligned" + extension
        
        
        image = cv2.imread(str(image_paths[i]))
        h, w = image.shape[:2]
        
        if transform_matrices[i] is None:
          print(f"Warning: no transform for {os.path.basename(image_paths[i])}, copying unmodified")
          transformed_image = image
        else:
            transformed_image = cv2.warpAffine(image, transform_matrices[i], (w, h))

        full_path = os.path.join(output_folder, file_name)
        cv2.imwrite(full_path, transformed_image)
        

if __name__ == "__main__":
    folder_path = "/Users/calvinyong/Desktop/UW Madison/Research Materials/Dataset/Experiment  20260528_124038/plate2"
    matching_files = get_input_folder(folder_path)
    marker_corners = detect_marker_corners(matching_files)
    transforms = compute_transforms(marker_corners)
    apply_transforms(matching_files, transforms)