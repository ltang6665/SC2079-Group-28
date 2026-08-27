import argparse
import os
import sys
import time
import cv2

from StreamListener import StreamListener


def main():
    parser = argparse.ArgumentParser(description="Stream YOLO + record MP4; ESC to stop")
    parser.add_argument("--weights", required=True, help="Path to YOLO weights")
    parser.add_argument("--conf", type=float, default=0.7, help="Confidence threshold")
    parser.add_argument("--no-gui", action="store_true", help="Disable live window")
    parser.add_argument("--save-dir", default="", help="Directory to save displayed frames")
    parser.add_argument("--video-out", default="out.mp4", help="Path to the MP4 to write")
    parser.add_argument("--fps", type=float, default=30.0, help="Video FPS for the MP4")
    args = parser.parse_args()

    if args.save_dir:
        os.makedirs(args.save_dir, exist_ok=True)

    listener = StreamListener(weights=args.weights)

    last_t = None
    frame_idx = 0
    writer = None
    writer_size = None
    esc_requested = False
    window_name = "Stream (ESC to save & exit)"

    def _init_writer_if_needed(frame):
        nonlocal writer, writer_size
        if writer is not None or frame is None:
            return
        h, w = frame.shape[:2]
        writer_size = (w, h)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(args.video_out, fourcc, args.fps, writer_size)

    def on_result(res, annotated_frame, raw_frame):
        """
        res: YOLO result object or None
        annotated_frame: frame with boxes (may be None if no detections)
        raw_frame: the original frame from the stream (never None)
        """
        nonlocal last_t, frame_idx, writer, esc_requested

        if esc_requested:
            return

        frame_idx += 1
        now = time.perf_counter()
        fps_live = 1.0 / (now - last_t) if last_t else 0.0
        last_t = now

        # Choose what to show: annotated if available, else the original raw frame
        frame_to_show = annotated_frame if annotated_frame is not None else raw_frame

        # Log detections
        if res is None or getattr(res, "boxes", None) is None or len(res.boxes) == 0:
            print(f"[{frame_idx:06d}] no detections | fps={fps_live:.1f}", end="\r")
        else:
            names = getattr(res, "names", {})
            cls_ids = res.boxes.cls.tolist() if hasattr(res.boxes.cls, "tolist") else res.boxes.cls
            confs = res.boxes.conf.tolist() if hasattr(res.boxes.conf, "tolist") else res.boxes.conf
            dets = ", ".join(f"{names.get(int(c), str(int(c)))}:{conf:.2f}" for c, conf in zip(cls_ids, confs))
            print(f"[{frame_idx:06d}] {len(cls_ids)} det(s): {dets} | fps={fps_live:.1f}   ")

        # Optional per-frame saving (saves what you saw)
        if args.save_dir:
            out_path = os.path.join(args.save_dir, f"frame_{frame_idx:06d}.jpg")
            try:
                cv2.imwrite(out_path, frame_to_show)
            except Exception as e:
                print(f"\nFailed to save {out_path}: {e}")

        # Display & record
        if not args.no_gui:
            _init_writer_if_needed(frame_to_show)

            if writer is not None:
                if (frame_to_show.shape[1], frame_to_show.shape[0]) != writer_size:
                    frame_to_write = cv2.resize(frame_to_show, writer_size)
                else:
                    frame_to_write = frame_to_show
                writer.write(frame_to_write)

            cv2.imshow(window_name, frame_to_show)
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                esc_requested = True
                listener.close()

    def on_disconnect():
        print("\nDisconnected from server.")

    try:
        if not args.no_gui:
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

        # IMPORTANT: start_stream_read must pass raw_frame to on_result (see patch below)
        listener.start_stream_read(
            on_result=on_result,          # expects (res, annotated_frame, raw_frame)
            on_disconnect=on_disconnect,
            conf_threshold=args.conf,
            show_video=not args.no_gui,
        )
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        if writer is not None:
            writer.release()
            print(f"\nSaved video to: {args.video_out}")
        if not args.no_gui:
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass
        listener.close()


if __name__ == "__main__":
    sys.exit(main())