"""
Debug TFRecord to see what's actually stored
"""
import tensorflow as tf
import numpy as np

# Read a few examples from the training TFRecord
tfrecord_path = 'runs/tensorflow/mdp_train.tfrecord'

feature_description = {
    'image/encoded': tf.io.FixedLenFeature([], tf.string),
    'image/height': tf.io.FixedLenFeature([], tf.int64),
    'image/width': tf.io.FixedLenFeature([], tf.int64),
    'image/object/bbox/xmin': tf.io.VarLenFeature(tf.float32),
    'image/object/bbox/ymin': tf.io.VarLenFeature(tf.float32),
    'image/object/bbox/xmax': tf.io.VarLenFeature(tf.float32),
    'image/object/bbox/ymax': tf.io.VarLenFeature(tf.float32),
    'image/object/class/label': tf.io.VarLenFeature(tf.int64),
}

print("Checking first 10 examples from TFRecord...")
print("="*80)

count_with_boxes = 0
count_without_boxes = 0

dataset = tf.data.TFRecordDataset(tfrecord_path)

for i, raw_record in enumerate(dataset.take(10)):
    example = tf.io.parse_single_example(raw_record, feature_description)
    
    # Get bboxes
    xmins = tf.sparse.to_dense(example['image/object/bbox/xmin']).numpy()
    ymins = tf.sparse.to_dense(example['image/object/bbox/ymin']).numpy()
    xmaxs = tf.sparse.to_dense(example['image/object/bbox/xmax']).numpy()
    ymaxs = tf.sparse.to_dense(example['image/object/bbox/ymax']).numpy()
    classes = tf.sparse.to_dense(example['image/object/class/label']).numpy()
    
    num_boxes = len(xmins)
    
    print(f"\nExample {i+1}:")
    print(f"  Number of boxes: {num_boxes}")
    
    if num_boxes > 0:
        count_with_boxes += 1
        print(f"  Classes: {classes}")
        print(f"  Boxes (normalized [0,1]):")
        for j in range(num_boxes):
            print(f"    Box {j+1}: xmin={xmins[j]:.3f}, ymin={ymins[j]:.3f}, xmax={xmaxs[j]:.3f}, ymax={ymaxs[j]:.3f}")
            # Check if box is valid
            if xmins[j] >= xmaxs[j] or ymins[j] >= ymaxs[j]:
                print(f"      ⚠️ INVALID BOX: xmin >= xmax or ymin >= ymax")
            if xmins[j] < 0 or ymins[j] < 0 or xmaxs[j] > 1 or ymaxs[j] > 1:
                print(f"      ⚠️ OUT OF RANGE: bbox not in [0,1]")
    else:
        count_without_boxes += 1
        print(f"  ⚠️ NO BOXES in this image!")

print("\n" + "="*80)
print(f"Summary of first 10 examples:")
print(f"  With boxes: {count_with_boxes}")
print(f"  Without boxes: {count_without_boxes}")

if count_without_boxes > 5:
    print("\n⚠️ WARNING: More than half the examples have NO boxes!")
    print("   This explains why the model outputs zero bboxes.")
