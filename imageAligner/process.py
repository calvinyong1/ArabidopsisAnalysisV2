import cv2
import cv2.aruco as aruco
import numpy as np
import os
import pathlib
import sys
import scipy.ndimage

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
            ty = 0
            M = np.float32([[1, 0, tx], [0, 1, ty]])
            transforms.append(M)
    
    return transforms

# def compute_transforms(marker_corners):
#       if marker_corners[0] is None:
#           raise ValueError("No ArUco marker detected in the first frame — cannot establish reference.")

#       # Collect all centroids
#       centroids = []
#       for corners in marker_corners:
#           if corners is None:
#               centroids.append(None)
#           else:
#               pts = corners[0][0].astype(np.float32)
#               centroids.append(np.mean(pts, axis=0))

#       # Fill None gaps with nearest valid centroid for smoothing
#       filled = _fill_none(centroids)

#       # Smooth tx/ty series with a Gaussian filter
#       xs = scipy.ndimage.gaussian_filter1d([c[0] for c in filled], sigma=5)
#       ys = scipy.ndimage.gaussian_filter1d([c[1] for c in filled], sigma=5)
  
#       ref_x, ref_y = xs[0], ys[0]
  
#       transforms = []
#       for i, corners in enumerate(marker_corners):
#           if corners is None:
#               transforms.append(None)
#           else:
#               M = np.float32([[1, 0, ref_x - xs[i]],
#                               [0, 1, ref_y - ys[i]]])
#               transforms.append(M)

#       return transforms


# def _fill_none(centroids):
#     filled = list(centroids)
#     # Forward fill
#     last = None
#     for i, c in enumerate(filled):
#         if c is not None:
#             last = c
#         elif last is not None:
#             filled[i] = last
#     # Backward fill for leading Nones
#     last = None
#     for i in range(len(filled) - 1, -1, -1):
#         if filled[i] is not None:
#             last = filled[i]
#         elif last is not None:
#             filled[i] = last
#     return filled
            
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