"""
Count annotations for all classes in the dataset
"""
from pathlib import Path
from collections import Counter
import yaml

# Load class names from yaml
with open('imagesSet/data.yaml', 'r') as f:
    data = yaml.safe_load(f)

class_names = data['names']

# Count labels
labels = []
label_files = list(Path('imagesSet/train/labels').glob('*.txt'))

print(f"Reading {len(label_files)} label files...\n")

for f in label_files:
    with open(f, 'r') as file:
        for line in file:
            line = line.strip()
            if line:
                class_id = line.split()[0]
                labels.append(class_id)

# Count occurrences
counter = Counter(labels)

# Display results
print("=" * 70)
print("CLASS DISTRIBUTION")
print("=" * 70)
print(f"{'Class ID':<10} {'Class Name':<30} {'Count':<10}")
print("-" * 70)

total = 0
for i, name in enumerate(class_names):
    count = counter.get(str(i), 0)
    total += count
    print(f"{i:<10} {name:<30} {count:<10}")

print("-" * 70)
print(f"{'TOTAL':<40} {total:<10}")
print("=" * 70)

# Find imbalanced classes
avg_count = total / len(class_names)
print(f"\nAverage per class: {avg_count:.1f}")
print("\nClasses with low samples (<50% of average):")
for i, name in enumerate(class_names):
    count = counter.get(str(i), 0)
    if count < avg_count * 0.5:
        print(f"  {name} (Class {i}): {count} (add more!)")
