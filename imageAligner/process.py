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
    
    for corners in marker_corners:
        if corners is None:
            transforms.append(None)
        else:
            current = corners[0][0].astype(np.float32)
            M = cv2.getPerspectiveTransform(current,reference)
            transforms.append(M)
    
    return transforms
            
# def apply_transforms(image_paths):
        

if __name__ == "__main__":
    folder_path = "/Users/calvinyong/Desktop/UW Madison/Research Materials/Dataset/Experiment  20260528_124038/plate2"
    matching_files = get_input_folder(folder_path)
    marker_corners = detect_marker_corners(matching_files)
    transforms = compute_transforms(marker_corners)
    print (transforms)
    
    