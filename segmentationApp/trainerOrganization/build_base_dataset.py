import argparse
import os
import pathlib
import re
import nibabel as nib
import cv2
import numpy as np


def natural_sort_key(s, _nsre=re.compile('([0-9]+)')):
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(_nsre, s)]


def build(input_dir: str, images_out: str, labels_out: str) -> int:
    os.makedirs(images_out, exist_ok=True)
    os.makedirs(labels_out, exist_ok=True)

    image_paths = sorted(
        (str(p) for p in pathlib.Path(input_dir).glob('*/*/*/*.png')),
        key=natural_sort_key
    )

    case_id = 0
    skipped = []

    for path in image_paths:
        mask_path = path.replace('.png', '.nii.gz')
        if not os.path.exists(mask_path):
            skipped.append((path, 'no matching .nii.gz'))
            continue

        mask = nib.load(mask_path).get_fdata().T
        if mask.ndim == 3 and mask.shape[0] == 1:
            mask = mask[0]

        image = cv2.imread(path, 0)
        if image.shape != mask.shape:
            skipped.append((path, f'shape mismatch image={image.shape} mask={mask.shape}'))
            continue

        case_name = f'Case{case_id}'
        cv2.imwrite(os.path.join(images_out, f'{case_name}_0000.png'), image)
        cv2.imwrite(os.path.join(labels_out, f'{case_name}.png'), mask.astype('uint8'))
        case_id += 1

    print(f"Converted {case_id} cases (Case0 to Case{case_id - 1}).")
    if skipped:
        print(f"Skipped {len(skipped)} files:")
        for p, reason in skipped:
            print(f"  {p}: {reason}")

    return case_id


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Convert the raw HuggingFace ChronoRoot2 ArabidopsisDataset folder into nnUNet Case naming'
    )
    parser.add_argument('input_dir', help='Path to the downloaded ArabidopsisDataset folder')
    parser.add_argument('images_out', help='Output directory for Case###_0000.png images (imagesTr)')
    parser.add_argument('labels_out', help='Output directory for Case###.png masks (labelsTr)')
    args = parser.parse_args()

    build(args.input_dir, args.images_out, args.labels_out)
