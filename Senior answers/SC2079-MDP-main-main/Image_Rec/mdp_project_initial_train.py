from ultralytics import YOLO

model = YOLO("bestv8n.pt")

model.train(
    data="data.yaml",
    epochs=50,
    imgsz=640,
    batch=32,
    name="exp_v8n",
    project="YOLO_runs_task2",
    cache=False,
    resume=False,
    patience=30,
    exist_ok=True,
    augment=False,
    workers=2,
)
