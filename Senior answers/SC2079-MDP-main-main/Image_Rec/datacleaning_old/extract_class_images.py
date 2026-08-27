"""
Extract images containing specific classes into separate folders
"""
from pathlib import Path
import shutil

def extract_class_images(class_id, class_name, source_images_dir, source_labels_dir, output_dir):
    """
    Find all images containing a specific class and copy them to output folder
    
    Args:
        class_id: The class ID to search for (as string)
        class_name: Name for the output folder
        source_images_dir: Path to images folder
        source_labels_dir: Path to labels folder
        output_dir: Base output directory
    """
    source_images = Path(source_images_dir)
    source_labels = Path(source_labels_dir)
    output_path = Path(output_dir) / class_name
    output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\nSearching for class {class_id} ({class_name})...")
    
    copied_count = 0
    
    # Go through all label files
    for label_file in source_labels.glob('*.txt'):
        # Check if this label file contains the target class
        has_class = False
        with open(label_file, 'r') as f:
            for line in f:
                if line.strip().startswith(class_id + ' '):
                    has_class = True
                    break
        
        if has_class:
            # Find corresponding image file
            image_name = label_file.stem  # filename without .txt
            
            # Try different image extensions
            for ext in ['.jpg', '.jpeg', '.png', '.bmp']:
                image_file = source_images / f"{image_name}{ext}"
                if image_file.exists():
                    # Copy image to output folder
                    dest = output_path / image_file.name
                    shutil.copy2(image_file, dest)
                    copied_count += 1
                    break
    
    print(f"✓ Copied {copied_count} images with {class_name} to {output_path}")
    return copied_count


if __name__ == '__main__':
    # Paths
    images_dir = 'imagesSet/train/images'
    labels_dir = 'imagesSet/train/labels'
    output_base = 'extracted_classes'
    
    print("=" * 70)
    print("EXTRACTING CLASS IMAGES")
    print("=" * 70)
    
    # Extract id28 (S) - class index 20
    extract_class_images('20', 'id28_S', images_dir, labels_dir, output_base)
    
    # Extract id26 (Right Arrow) - class index 18
    extract_class_images('18', 'id26_Right', images_dir, labels_dir, output_base)
    
    print("\n" + "=" * 70)
    print(f"✓ Done! Images saved in: {output_base}/")
    print("=" * 70)
