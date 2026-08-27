import argparse
import os
import sys
import time
import cv2
import numpy as np

from StreamListener import StreamListener
from distance import measure_arrow_bullseye_distance_planar_cm

def main():
    parser = argparse.ArgumentParser(description="StreamListener with planar (perspective-correct) distance")
    parser.add_argument("--weights", required=True, help="Path to YOLO weights")
    parser.add_argument("--conf", type=float, default=0.7, help="Detection confidence threshold")
    parser.add_argument("--min-conf", type=float, default=0.5, help="Min conf for distance calc")
    parser.add_argument("--bullseye-side-cm", type=float, default=6.0, help="Physical side of bullseye tag (cm)")
    parser.add_argument("--no-gui", action="store_true", help="Disable live window")
    parser.add_argument("--save-dir", default="", help="Directory to save annotated frames")
    args = parser.parse_args()

    if args.save_dir:
        os.makedirs(args.save_dir, exist_ok=True)

    listener = StreamListener(weights=args.weights)

    last_t = None
    frame_idx = 0

    def on_result(res, annotated_frame):
        nonlocal last_t, frame_idx
        frame_idx += 1
        now = time.perf_counter()
        fps = 1.0 / (now - last_t) if last_t else 0.0
        last_t = now

        # draw on the annotated frame if GUI is on
        draw_on = None if args.no_gui else annotated_frame

        if res is None:
            print(f"[{frame_idx:06d}] no detections | fps={fps:.1f}", end="\r")
        else:
            out = measure_arrow_bullseye_distance_planar_cm(
                results=res,
                frame_bgr=annotated_frame,                  # use the current frame
                bullseye_side_cm=args.bullseye_side_cm,
                min_conf=args.min_conf,
                annotate_on=draw_on
            )

            if out["ok"]:
                nearest = out["nearest_cm"]
                method = out.get("method", "?")
                print(f"[{frame_idx:06d}] distance: {nearest:.1f} cm ({method}) | fps={fps:.1f}   ")
            else:
                print(f"[{frame_idx:06d}] distance N/A ({out['reason']}) | fps={fps:.1f}   ")

            # Save if requested (save what we drew on)
            if args.save_dir and annotated_frame is not None:
                out_path = os.path.join(args.save_dir, f"frame_{frame_idx:06d}.jpg")
                try:
                    cv2.imwrite(out_path, annotated_frame)
                except Exception as e:
                    print(f"\nFailed to save {out_path}: {e}")

    def on_disconnect():
        print("\nDisconnected from server.")

    try:
        listener.start_stream_read(
            on_result=on_result,
            on_disconnect=on_disconnect,
            conf_threshold=args.conf,
            show_video=not args.no_gui,
        )
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        listener.close()

if __name__ == "__main__":
    sys.exit(main())
