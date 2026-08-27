"""Check for images without labels or labels without images"""
from pathlib import Path

base = Path('imagesSet')

for split in ['train', 'valid', 'test']:
    img_dir = base / split / 'images'
    lbl_dir = base / split / 'labels'
    
    if not img_dir.exists():
        continue
    
    imgs = {p.stem for p in img_dir.glob('*.*') if p.suffix.lower() in {'.jpg','.jpeg','.png','.bmp'}}
    lbls = {p.stem for p in lbl_dir.glob('*.txt')}
    
    missing_lbl = imgs - lbls
    missing_img = lbls - imgs
    
    if missing_lbl or missing_img:
        print(f"\nSplit {split}:")
        print(f"  {len(missing_lbl)} images without labels")
        print(f"  {len(missing_img)} labels without images")
        
        if missing_lbl:
            print(f"  First 10 images without labels: {sorted(list(missing_lbl))[:10]}")
        if missing_img:
            print(f"  First 10 labels without images: {sorted(list(missing_img))[:10]}")
    else:
        print(f"\n✓ {split}: All images have labels and vice versa")

print("\n✓ Check complete")
