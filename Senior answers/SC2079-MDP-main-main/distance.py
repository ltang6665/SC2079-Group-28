import argparse
import os
import sys
import time
import cv2
import numpy as np

# If StreamListener is in another file, adjust this import.
from StreamListener import StreamListener

# -------------------------
# Constants & helpers
# -------------------------
ARROW_TAGS   = {"38", "39", "arrow_right", "arrow_left", "right", "left"}
BULLSEYE_TAG = {"45", "bullseye", "target"}

def _as_list(res):
    return res if isinstance(res, (list, tuple)) else [res]

def _center_xyxy(box):
    x1, y1, x2, y2 = map(float, box)
    return (0.5*(x1+x2), 0.5*(y1+y2))

def _parse_dets(results, min_conf=0.0):
    out = []
    for r in _as_list(results):
        if r.boxes is None or len(r.boxes) == 0:
            continue
        names = r.names
        xyxy = r.boxes.xyxy.cpu().numpy()
        cls  = r.boxes.cls.cpu().numpy().astype(int)
        conf = r.boxes.conf.cpu().numpy().astype(float)
        for (x1,y1,x2,y2), c, p in zip(xyxy, cls, conf):
            if p >= min_conf:
                name = str(names.get(int(c), int(c))).strip().lower()
                out.append({
                    "name": name,
                    "cls": int(c),
                    "conf": float(p),
                    "box": [float(x1), float(y1), float(x2), float(y2)]
                })
    return out

def _pick_best(items):
    return max(items, key=lambda d: d["conf"]) if items else None

def _order_quad(pts):
    # pts: (4,2) -> TL, TR, BR, BL
    pts = np.array(pts, dtype=np.float32)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    tl = pts[np.argmin(s)]
    br = pts[np.argmax(s)]
    tr = pts[np.argmin(d)]
    bl = pts[np.argmax(d)]
    return np.array([tl, tr, br, bl], dtype=np.float32)

def _find_square_corners(frame_bgr, bbox_xyxy):
    """Find a quadrilateral inside the bullseye bbox (used for homography)."""
    x1, y1, x2, y2 = map(int, bbox_xyxy)
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(frame_bgr.shape[1]-1, x2), min(frame_bgr.shape[0]-1, y2)
    if x2 <= x1+3 or y2 <= y1+3:
        return None

    roi = frame_bgr[y1:y2, x1:x2]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5,5), 0)

    edges = cv2.Canny(gray, 50, 150)
    edges = cv2.dilate(edges, np.ones((3,3), np.uint8), iterations=1)

    cnts, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return None

    cnts = sorted(cnts, key=cv2.contourArea, reverse=True)[:5]
    h, w = gray.shape[:2]
    img_area = w*h
    for c in cnts:
        area = cv2.contourArea(c)
        if area < 0.02*img_area:  # ignore very small
            continue
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02*peri, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            quad = approx.reshape(-1,2).astype(np.float32)
            quad[:,0] += x1
            quad[:,1] += y1
            return _order_quad(quad)
    return None

def _warp_to_world(pt_xy, Hinv):
    x, y = float(pt_xy[0]), float(pt_xy[1])
    v = np.array([x, y, 1.0], dtype=np.float64)
    w = Hinv @ v
    if abs(w[2]) < 1e-9:
        return None
    return (float(w[0]/w[2]), float(w[1]/w[2]))

def measure_arrow_bullseye_distance_planar_cm(
    results,
    frame_bgr,
    bullseye_side_cm=6.0,
    min_conf=0.5,
    annotate_on=None
):
    """
    Perspective-correct distance on a plane using the bullseye's square corners to build a homography.
    Falls back to size-based scaling if corners aren't reliable.
    """
    dets = _parse_dets(results, min_conf=min_conf)
    arrows    = [d for d in dets if d["name"] in ARROW_TAGS]
    bullseyes = [d for d in dets if d["name"] in BULLSEYE_TAG]

    arrow = _pick_best(arrows)
    bull = _pick_best(bullseyes)
    if arrow is None or bull is None:
        return {"ok": False, "reason": "arrow or bullseye missing", "nearest_cm": None}

    # Try planar method (homography from square corners)
    quad_img = _find_square_corners(frame_bgr, bull["box"])
    if quad_img is not None:
        world_sq = np.array([
            [0, 0],
            [bullseye_side_cm, 0],
            [bullseye_side_cm, bullseye_side_cm],
            [0, bullseye_side_cm]
        ], dtype=np.float32)

        H, _ = cv2.findHomography(world_sq, quad_img, method=cv2.RANSAC, ransacReprojThreshold=3.0)
        if H is not None:
            Hinv = np.linalg.inv(H)
            a_px = _center_xyxy(arrow["box"])
            b_px = _center_xyxy(bull["box"])
            a_world = _warp_to_world(a_px, Hinv)
            b_world = _warp_to_world(b_px, Hinv)
            if a_world and b_world:
                dx = a_world[0] - b_world[0]
                dy = a_world[1] - b_world[1]
                dist_cm = float((dx*dx + dy*dy) ** 0.5)

                if annotate_on is not None:
                    ac = tuple(map(int, a_px))
                    bc = tuple(map(int, b_px))
                    cv2.line(annotate_on, ac, bc, (0,255,0), 2)
                    cv2.putText(annotate_on, f"{dist_cm:.1f} cm (planar)",
                                (int((ac[0]+bc[0])/2), int((ac[1]+bc[1])/2)-8),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2, cv2.LINE_AA)
                    q = quad_img.astype(int)
                    for i in range(4):
                        cv2.line(annotate_on, tuple(q[i]), tuple(q[(i+1)%4]), (255,0,0), 2)

                return {"ok": True, "nearest_cm": dist_cm, "method": "planar"}

    # Fallback: scale using bullseye size (perspective-biased)
    x1, y1, x2, y2 = bull["box"]
    w_px, h_px = float(x2-x1), float(y2-y1)
    px_side_est = (w_px*h_px) ** 0.5
    if px_side_est <= 1e-6:
        return {"ok": False, "reason": "invalid bullseye geometry", "nearest_cm": None}

    cm_per_px = bullseye_side_cm / px_side_est
    a_cx, a_cy = _center_xyxy(arrow["box"])
    b_cx, b_cy = _center_xyxy(bull["box"])
    d_px = ((a_cx - b_cx)**2 + (a_cy - b_cy)**2) ** 0.5
    dist_cm = float(d_px * cm_per_px)

    if annotate_on is not None:
        ac = (int(a_cx), int(a_cy)); bc = (int(b_cx), int(b_cy))
        cv2.line(annotate_on, ac, bc, (0,255,255), 2)
        cv2.putText(annotate_on, f"{dist_cm:.1f} cm (fallback)",
                    (int((ac[0]+bc[0])/2), int((ac[1]+bc[1])/2)-8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2, cv2.LINE_AA)

    return {"ok": True, "nearest_cm": dist_cm, "method": "fallback"}