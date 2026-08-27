import socket
import json
import threading
from time import time_ns, sleep
import logging

logging.basicConfig(level=logging.INFO)

from pathfinding.pathfinding import pathfinding
from stitching import add_to_stitching_dict, stitch_images, add_to_stitching_dict_2, stitch_images_2
from StreamListener import StreamListener

PI_IP = "192.168.20.1"
PORT = 5000

class Task2:
    def __init__(self, host=PI_IP, port=PORT):
        self.host = host
        self.port = port
        self.sock = None
        self.exit = False
        self.timeout = 2  # seconds

        self.detection_gate = threading.Event() # when SET: block on_result
        self.detection_gate.clear()
        self.obstacle_lock = threading.RLock() # guard obstacle_id and coupled state
        self.stitch_lock = threading.RLock() # guard stitching_img_dict

        # Tunables
        self.cooldown_s = 1.0 # how long to suppress detections after SEEN (non-blocking)
        self.debounce_hits = 2 # optional: require N consecutive frames for same id

        self.obstacle_id = 1
        self.current_image_id = None
        self.consecutive_hits = 0 # for debounce
        
        self.prev_detected_id = None 

        self.IMG_BLACKLIST = ["45"]
        self.conf_threshold = 0.7

        # { obstacle_id: { image_id: (best_conf, frame) } }
        self.stitching_img_dict = {}

        self.model = "bestv8n.pt"
        self.filename = "stitches/task2"

        # Threads
        self.pc_receive_thread = None
        self.stream_listener = None

        self.LEFT_ARROW_ID = "39"
        self.RIGHT_ARROW_ID = "38"

        self.last_image = None

    def _start_cooldown_and_advance(self):
        """Non-blocking cooldown: suppress detections briefly and advance obstacle_id safely."""
        # Set gate so on_result returns early during cooldown
        self.detection_gate.set()
        with self.obstacle_lock:
            self.obstacle_id += 1
            self.current_image_id = None
            self.consecutive_hits = 0
            logging.info(f"Advanced to obstacle {self.obstacle_id} (cooldown {self.cooldown_s}s).")

        # Clear the gate later without blocking recv thread
        t = threading.Timer(self.cooldown_s, self.detection_gate.clear)
        t.daemon = True
        t.start()

    def on_result(self, result, frame):
        # If in cooldown, ignore any detections
        if self.detection_gate.is_set():
            return

        message_content = None
        detected_img_id = None

        if result is not None:
            cls_idx = int(result.boxes[0].cls[0].item())
            detected_img_id = result.names[cls_idx]
            detected_conf_level = result.boxes[0].conf.item()

            # Basic filtering
            if (
                detected_img_id not in [self.LEFT_ARROW_ID, self.RIGHT_ARROW_ID] or
                detected_conf_level < self.conf_threshold or
                detected_img_id in self.IMG_BLACKLIST
            ):
                # reset debounce if irrelevant
                self.consecutive_hits = 0
                return

            if detected_img_id == self.prev_detected_id:
                self.consecutive_hits += 1
            else:
                self.consecutive_hits = 1
            self.prev_detected_id = detected_img_id

            if self.consecutive_hits < self.debounce_hits:
                return

            # Prepare the one-shot "seen" message only once per stable sighting
            if self.current_image_id is None:
                message_content = f"{detected_conf_level},{detected_img_id}\n"
                self.current_image_id = detected_img_id

            # Safely snapshot obstacle id
            with self.obstacle_lock:
                obs_id = self.obstacle_id

            # Update stitching dict for this obstacle/image pair
            with self.stitch_lock:
                if obs_id not in self.stitching_img_dict:
                    self.stitching_img_dict[obs_id] = {}
                add_to_stitching_dict_2(
                    self.stitching_img_dict,
                    obs_id,
                    detected_img_id,
                    detected_conf_level,
                    frame
                )

            self.last_image = detected_img_id

        # Emit the message if needed
        if message_content is not None and self.sock:
            # logging.info(f"Sending: {message_content.strip()}")
            try:
                self.sock.send(message_content.encode("utf-8"))
            except OSError as e:
                logging.error(f"Send error: {e}")
            finally:
                self.current_image_id = None

    def pc_receive(self) -> None:
        self.connect()
        logging.info("PC Socket connection started successfully")

        while not self.exit:
            try:
                data_str = self.sock.recv(1024).decode("utf-8")
                if not data_str:
                    continue
                logging.info(f"Received from RPI: {data_str}")

                if "SEEN" in data_str:
                    self._start_cooldown_and_advance()

                elif "STITCH" in data_str:
                    with self.stitch_lock:
                        keys = sorted(self.stitching_img_dict.keys())[-2:] or [1, 2]
                        stitch_images_2(keys, self.stitching_img_dict, self.filename, ncols=2, show=False)

            except OSError as e:
                logging.error(f"Error in receiving data: {e}")
                break

    def start_stream(self):
        self.detection_gate.clear()
        self.stream_listener = StreamListener(weights=self.model)
        self.stream_listener.start_stream_read(
            on_result=self.on_result,
            on_disconnect=self.disconnect,
            conf_threshold=self.conf_threshold,
            show_video=False
        )
        logging.info("Stream Started")

    def connect(self, retries: int = 10, delay: float = 1.0):
        last_err = None
        for attempt in range(1, retries + 1):
            try:
                logging.info(f"Connecting to {self.host}:{self.port} (attempt {attempt}/{retries})")
                self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
                self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                self.sock.settimeout(None)
                logging.info("Connected.")
                return
            except OSError as e:
                last_err = e
                logging.warning(f"Connect failed: {e}; retrying in {delay}s")
                sleep(delay)
        raise ConnectionError(f"Unable to connect to {self.host}:{self.port}") from last_err

    def disconnect(self):
        if self.sock:
            try:
                self.sock.close()
            finally:
                self.sock = None
        self.exit = True

    def start_task_2(self):
        self.pc_receive_thread = threading.Thread(target=self.pc_receive, daemon=True)
        print("Starting Task 2 server...")
        stream_thread = threading.Thread(target=self.start_stream, daemon=True)
        stream_thread.start()
        self.pc_receive_thread.start()
        self.pc_receive_thread.join()


if __name__ == "__main__":
    server = Task2()
    server.start_task_2()
