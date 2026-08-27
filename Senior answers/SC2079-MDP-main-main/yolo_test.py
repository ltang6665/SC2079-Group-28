from ultralytics import YOLO
import cv2
import numpy as np

model = YOLO("best.pt")

with open("images/3.jpg", "rb") as f:
    jpg_bytes = f.read()

frame = cv2.imdecode(np.frombuffer(jpg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)

# 4) YOLO inference
result = model.predict(
    frame, save=False, imgsz=frame.shape[1],
    conf=0.7, verbose=False
)[0]

boxes = result.boxes  # Boxes object for bounding box outputs
masks = result.masks  # Masks object for segmentation masks outputs
keypoints = result.keypoints  # Keypoints object for pose outputs
probs = result.probs  # Probs object for classification outputs
obb = result.obb  # Oriented boxes object for OBB outputs
result.show()  # display to screen
result.save(filename="result.jpg")  # save to disk