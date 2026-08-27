"""
Convert SC2079 dataset to internal label schema and copy into imagesSet
"""
import shutil
from pathlib import Path
import yaml

# Paths
SRC_ROOT = Path(r"C:\Users\kwang\Downloads\SC2079 MDP 2024.v1i.yolov11")
DST_ROOT = Path(r"C:\github\MDP_imgReg\imagesSet")

# Mapping from source class names to our class IDs (as strings)
NAME_TO_ID = {
    'A': '20', 'B': '21', 'Bullseye': '33', 'C': '22', 'D': '23',
    'E': '24', 'F': '25', 'G': '26', 'H': '27', 'S': '28', 'T': '29',
    'U': '30', 'V': '31', 'W': '32', 'X': '33', 'Y': '34', 'Z': '35',
    'circle': '40', 'down': '37', 'eight': '18', 'five': '15', 'four': '14',
    'left': '39', 'nine': '19', 'one': '11', 'right': '38', 'seven': '17',
    'six': '16', 'three': '13', 'two': '12', 'up': '36'
}

def load_source_names():
    data_yaml = SRC_ROOT / "data.yaml"
    with open(data_yaml, 'r') as f:
        data = yaml.safe_load(f)
    return data['names']

def build_mapping():
    src_names = load_source_names()
    mapping = {}
    for idx, name in enumerate(src_names):
        if name not in NAME_TO_ID:
            raise ValueError(f"No mapping for class '{name}' (index {idx})")
        mapping[str(idx)] = NAME_TO_ID[name]
    return mapping

def copy_split(split):
    print(f"\n=== Processing {split} split ===")
    src_img_dir = SRC_ROOT / split / "images"
    src_lbl_dir = SRC_ROOT / split / "labels"
    dst_img_dir = DST_ROOT / split / "images"
    dst_lbl_dir = DST_ROOT / split / "labels"
    
    if not src_img_dir.exists():
        print(f"Skipping {split}: no images found")
        return
    
    dst_img_dir.mkdir(parents=True, exist_ok=True)
    dst_lbl_dir.mkdir(parents=True, exist_ok=True)
    
    mapping = build_mapping()
    
    # Copy images
    image_files = list(src_img_dir.glob("*.*"))
    print(f"Copying {len(image_files)} images...")
    for img in image_files:
        dest = dst_img_dir / img.name
        shutil.copy2(img, dest)
    
    # Convert labels
    label_files = list(src_lbl_dir.glob("*.txt"))
    print(f"Converting {len(label_files)} label files...")
    for lbl in label_files:
        dst_lbl_file = dst_lbl_dir / lbl.name
        lines = []
        with open(lbl, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                src_id = parts[0]
                if src_id not in mapping:
                    raise ValueError(f"Unknown class id {src_id} in {lbl}")
                parts[0] = mapping[src_id]
                lines.append(" ".join(parts))
        with open(dst_lbl_file, 'w') as f:
            if lines:
                f.write("\n".join(lines) + "\n")
            else:
                f.write("")
    
    print(f"✓ {split} split done (images copied + labels converted)")

if __name__ == "__main__":
    print("======================================================")
    print("Converting SC2079 dataset to internal label schema...")
    print("Source:", SRC_ROOT)
    print("Destination:", DST_ROOT)
    print("======================================================")
    
    for split in ["train", "valid", "test"]:
        copy_split(split)
    
    print("\nAll splits processed. Ready for training!")
