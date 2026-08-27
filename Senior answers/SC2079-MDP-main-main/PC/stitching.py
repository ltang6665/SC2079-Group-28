import cv2
import numpy as np
import math
from datetime import datetime 
import random
import logging
logging.basicConfig(level=logging.INFO)

from ultralytics import YOLO
from classes import CLASS_IDS

def add_to_stitching_dict(stitching_dict, img_id, conf_level, frame):
    if img_id not in stitching_dict or (
        conf_level > stitching_dict[img_id][0]
    ):
        # Store the best confidence level and corresponding frame
        stitching_dict[img_id] = (
            conf_level,
            frame,
        )
        logging.info(f"Saw {img_id} with confidence level {conf_level}.")
    

def stitch_images(
    id_arr,
    stitching_dict,
    filename="task",
    tile_size=(320, 320),
    ncols=3,
    pad=8,
    bg=(0, 0, 0),
    show=True,
    label=True,
    topmost=False
):
    """
    Build a grid collage from (img_id -> (best_conf, frame)) in stitching_dict.

    Returns: saved image path, or None on early exit.
    """
    # --- Guard rails ---
    if not id_arr:
        print("[stitch] No images to stitch.")
        return None
    # filter to ids that actually exist in dict (preserve order)
    ids = [img_id for img_id in id_arr if img_id in stitching_dict]
    if not ids:
        print("[stitch] None of the requested image IDs exist in stitching_dict.")
        return None

    tw, th = int(tile_size[0]), int(tile_size[1])
    n = len(ids)
    nrows = math.ceil(n / ncols)

    # Canvas size (pad between tiles, no outer margin; add your own if desired)
    canvas_w = ncols * tw + (ncols - 1) * pad
    canvas_h = nrows * th + (nrows - 1) * pad
    canvas = np.full((canvas_h, canvas_w, 3), bg, dtype=np.uint8)

    # Prepare a reusable blank tile
    blank = np.zeros((th, tw, 3), dtype=np.uint8)

    def _resize_tile(img):
        # choose interpolation based on scale
        ih, iw = img.shape[:2]
        if iw > tw or ih > th:
            interp = cv2.INTER_AREA  # downscale
        else:
            interp = cv2.INTER_LINEAR  # upscale or same
        return cv2.resize(img, (tw, th), interpolation=interp)

    for idx, img_id in enumerate(ids):
        conf, frame = stitching_dict.get(img_id, (None, None))

        if frame is None:
            tile = blank.copy()
        else:
            # ensure 3-channel uint8 BGR
            if frame.ndim == 2:
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            elif frame.shape[2] == 4:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            tile = _resize_tile(frame)

        # Optional label overlay
        if label:
            label_text = img_id if conf is None else f"{img_id} ({conf:.2f}) {CLASS_IDS[img_id]}"
            cv2.putText(
                tile, label_text, (8, th - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA
            )

        r, c = divmod(idx, ncols)
        y0 = r * (th + pad)
        x0 = c * (tw + pad)
        canvas[y0:y0+th, x0:x0+tw] = tile

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = f"{filename}_collage_{ts}.jpg"
    ok = cv2.imwrite(save_path, canvas)
    if not ok:
        print(f"[stitch] Failed to write {save_path}")
        return None

    if show:
        win = f"collage: {filename}"
        cv2.imshow(win, canvas)
        if topmost:
            try:
                cv2.setWindowProperty(win, cv2.WND_PROP_TOPMOST, 1)
            except cv2.error:
                pass
        # Non-blocking small wait; caller can close later if they want
        cv2.waitKey(1)

    return save_path

def add_to_stitching_dict_2(stitching_dict, obstacle_id, img_id, conf_level, frame):
    """
    Keep best (conf, frame) for each (obstacle_id, img_id).
    Structure:
      stitching_dict = {
          obstacle_id: {
              img_id: (best_conf, frame)
          }, ...
      }
    """
    if obstacle_id not in stitching_dict:
        stitching_dict[obstacle_id] = {}

    cur = stitching_dict[obstacle_id].get(img_id)
    if (cur is None) or (conf_level > cur[0]):
        stitching_dict[obstacle_id][img_id] = (conf_level, frame)
        logging.info(f"[stitch] Obstacle {obstacle_id} saw {img_id} @ {conf_level:.3f} (updated).")


def stitch_images_2(
    id_arr,
    stitching_dict,
    filename="task",
    tile_size=(320, 320),
    ncols=3,
    pad=8,
    bg=(0, 0, 0),
    show=True,
    label=True,
    topmost=False
):
    """
    Build a grid collage from nested dict:
      stitching_dict[obstacle_id][img_id] = (best_conf, frame)

    id_arr may be:
      - list of (obstacle_id, img_id) pairs (recommended), OR
      - list of obstacle_id only (we’ll pick that obstacle’s best img by confidence), OR
      - list of plain img_id (back-compat: we’ll search across obstacles and take the best hit)

    Returns: saved image path, or None on early exit.
    """
    # --- Normalize requested tiles -> list of (obstacle_id, img_id) ---
    pairs = []

    def _best_pair_for_obstacle(oid):
        """Return (oid, best_img_id) by highest confidence within that obstacle, or None."""
        if oid not in stitching_dict or not stitching_dict[oid]:
            return None
        best_img = max(stitching_dict[oid].items(), key=lambda kv: kv[1][0])[0]
        return (oid, best_img)

    def _best_pair_for_img(img_id):
        """Search all obstacles; return (oid, img_id) where that img_id has the best conf."""
        best = None
        for oid, inner in stitching_dict.items():
            if img_id in inner:
                conf = inner[img_id][0]
                if (best is None) or (conf > best[2]):
                    best = (oid, img_id, conf)
        return None if best is None else (best[0], best[1])

    for item in id_arr:
        if isinstance(item, tuple) and len(item) == 2:
            oid, iid = item
            if oid in stitching_dict and iid in stitching_dict[oid]:
                pairs.append((oid, iid))
        elif isinstance(item, (str, int)):  # ambiguous: could be obstacle_id or img_id
            # Prefer interpreting as obstacle_id; if not present, fall back to img_id search.
            p = _best_pair_for_obstacle(item)
            if p is None:
                p = _best_pair_for_img(item)
            if p is not None:
                pairs.append(p)
        else:
            # unsupported entry type; skip
            pass

    if not pairs:
        print("[stitch] No valid (obstacle_id, img_id) pairs to stitch.")
        return None

    # --- Canvas prep ---
    tw, th = int(tile_size[0]), int(tile_size[1])
    n = len(pairs)
    nrows = math.ceil(n / ncols)

    canvas_w = ncols * tw + (ncols - 1) * pad
    canvas_h = nrows * th + (nrows - 1) * pad
    canvas = np.full((canvas_h, canvas_w, 3), bg, dtype=np.uint8)

    blank = np.zeros((th, tw, 3), dtype=np.uint8)

    def _resize_tile(img):
        ih, iw = img.shape[:2]
        interp = cv2.INTER_AREA if (iw > tw or ih > th) else cv2.INTER_LINEAR
        return cv2.resize(img, (tw, th), interpolation=interp)

    # --- Draw tiles ---
    for idx, (oid, iid) in enumerate(pairs):
        conf, frame = stitching_dict.get(oid, {}).get(iid, (None, None))

        if frame is None:
            tile = blank.copy()
        else:
            if frame.ndim == 2:
                frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
            elif frame.shape[2] == 4:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            tile = _resize_tile(frame)

        if label:
            cls = ""
            try:
                cls = f" {CLASS_IDS[iid]}"
            except Exception:
                pass
            label_text = f"Obs {oid} | {iid}"
            if conf is not None:
                label_text += f" ({conf:.2f}){cls}"
            cv2.putText(
                tile, label_text, (8, th - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA
            )

        r, c = divmod(idx, ncols)
        y0 = r * (th + pad)
        x0 = c * (tw + pad)
        canvas[y0:y0+th, x0:x0+tw] = tile

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_path = f"{filename}_collage_{ts}.jpg"
    ok = cv2.imwrite(save_path, canvas)
    if not ok:
        print(f"[stitch] Failed to write {save_path}")
        return None

    if show:
        win = f"collage: {filename}"
        cv2.imshow(win, canvas)
        if topmost:
            try:
                cv2.setWindowProperty(win, cv2.WND_PROP_TOPMOST, 1)
            except cv2.error:
                pass
        cv2.waitKey(1)

    return save_path

def test_stitch():
    paths = {
        "IMG1": "image1.jpg",
        "IMG2": "image2.jpg",
        "IMG3": "image3.jpg",
        "IMG4": "image4.jpg",
    }

    frames = {}
        
    model = YOLO("bestv8n.pt")
    stitching_dict = {}
    for img_id, p in paths.items():
        with open(p, "rb") as f:
            jpg_bytes = f.read()
            frame = cv2.imdecode(np.frombuffer(jpg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)

            result = model.predict(
                frame, save=False, imgsz=frame.shape[1],
                conf=0.7, verbose=False
            )[0]
            
            
            if result is not None:
                names = result.names
                
                max_rec = None  

                for box in result.boxes:
                    cls_id = int(box.cls[0].item())
                    detected_img_id = names[cls_id]
                    if str(detected_img_id) in ["45"]:
                        continue

                    w = float(box.xywh[0][2].item())
                    h = float(box.xywh[0][3].item())
                    area = w * h
                    conf = float(box.conf[0].item()) if getattr(box.conf, "ndim", 0) else float(box.conf.item())

                    if (max_rec is None or
                        area > max_rec["area"] or
                        (area == max_rec["area"] and conf > max_rec["conf"])):
                        max_rec = {"detected_img_id": detected_img_id, "box": box, "area": area, "conf": conf}

                if max_rec is not None:
                    detected_img_id = max_rec["detected_img_id"]
                    detected_conf_level = max_rec["conf"]

                    add_to_stitching_dict(stitching_dict, detected_img_id, detected_conf_level, frame)

    id_arr = [id for id in stitching_dict.keys()]

    save_path = stitch_images(
        id_arr=id_arr,
        stitching_dict=stitching_dict,
        filename="task1",
        # tile_size=(320, 320),
        # ncols=2,
        # pad=4,
        # bg=(0, 0, 0),
        # show=True,
        # label=True,
        # topmost=True
    )
    print("Saved collage to:", save_path)

    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    test_stitch()