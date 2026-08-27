import socket
import json
import threading
from time import time_ns, sleep
import logging

logging.basicConfig(level=logging.INFO)

from pathfinding.pathfinding import pathfinding
from stitching import add_to_stitching_dict, stitch_images
from StreamListener import StreamListener
from pathfinding.consts import Direction

PI_IP = "192.168.20.1"
PORT = 5000

class Task1:
    def __init__(self, host=PI_IP, port=PORT):
        self.host = host
        self.port = port
        self.sock = None
        self.exit = False
        self.timeout = 2  # seconds
        self.big_turn = 0
        
        self.IMG_BLACKLIST = ["45"]
        self.conf_threshold = 0.7
        self.lead = 0.75e9 # Threshold before the obstacle timestamp to consider a match (in ns)
        self.lag = 1.5e9 # Threshold after the obstacle timestamp to consider a match (in ns)
        self.img_time_dict = {} # Dictionary of image_id -> (first_seen_timestamp, last_seen_timestamp)
        self.pending_obstacles = [] # List of tuples (obstacle_id, timestamp). Represents obstacles waiting to be matched.
        self.stitching_img_dict = {} # Dictionary of image_id -> (best_confidence_level, frame)
        self.ids_to_stitch = [] # List of image IDs to stitch
        self.should_stitch = False
        self.stitch_len = 0 
        
        self.matched_img_ids = set()
        
        self.model = "bestv8n.pt"
        self.filename = "stitches/task1"
        
        # Threads
        self.pc_receive_thread = None
        self.stream_listener = None
        
    def on_result(self, result, frame):
        """
        Callback function to handle detection results.
        Processes detected images, updates dictionaries, and matches images to obstacles.
        
        1. Updates the stitching dictionary with the best confidence level and corresponding frame.
        2. Updates the image time dictionary with first and last seen timestamps.
        3. Checks for pending obstacles and matches them with detected images based on time overlap.
        4. Sends matched image information to the PC via socket.
        5. Initiates stitching if the required number of images is detected.
        """
        if result is not None:
            names = result.names
            
            # 1) Find the single largest box (skip blacklist)
            max_rec = None  # {"detected_img_id": str, "box": box, "area": float, "conf": float}

            for box in result.boxes:
                cls_id = int(box.cls[0].item())
                detected_img_id = names[cls_id]
                if str(detected_img_id) in self.IMG_BLACKLIST:
                    continue

                w = float(box.xywh[0][2].item())
                h = float(box.xywh[0][3].item())
                area = w * h
                conf = float(box.conf[0].item()) if getattr(box.conf, "ndim", 0) else float(box.conf.item())

                if (max_rec is None or
                    area > max_rec["area"] or
                    (area == max_rec["area"] and conf > max_rec["conf"])):
                    max_rec = {"detected_img_id": detected_img_id, "box": box, "area": area, "conf": conf}

            # 2) If found, run the rest on just that one detection
            if max_rec is not None:
                detected_img_id = max_rec["detected_img_id"]
                detected_conf_level = max_rec["conf"]

                add_to_stitching_dict(self.stitching_img_dict, detected_img_id, detected_conf_level, frame)

                last_seen = time_ns()
                first_seen = self.img_time_dict.get(detected_img_id, (last_seen, None))[0]
                self.img_time_dict[detected_img_id] = (first_seen, last_seen)

                # if len(self.pending_obstacles) > 0:
                #     max_overlap = 0
                #     max_obstacle_id = None
                #     best_idx = None
                #     for i, (obstacle_id, timestamp) in enumerate(self.pending_obstacles):
                #         overlap = self.get_overlap_interval(detected_img_id, timestamp, first_seen, last_seen)
                #         if overlap > max_overlap:
                #             max_overlap = overlap
                #             max_obstacle_id = obstacle_id
                #             best_idx = i

                #     if max_obstacle_id is not None:
                #         self.send_matched_pair(max_obstacle_id, detected_img_id)
                #         self.pending_obstacles.pop(best_idx)

                #         if self.should_stitch and len(self.ids_to_stitch) >= self.stitch_len:
                #             logging.info("Found last image, stitching now...")
                #             self.stream_listener.close()
                #             self.should_stitch = False
                #             stitch_images(self.ids_to_stitch, self.stitching_img_dict, filename=self.filename)

    
    def get_overlap_interval(self, img_id, timestamp, first_seen, last_seen):
        """
        Calculate the overlap interval between the search interval and the image's seen interval.
        Returns the overlap duration in nanoseconds.
        """
        if img_id not in self.img_time_dict:
            return 0
        
        search_interval = (timestamp - self.lead, timestamp + self.lag)
        img_interval = (first_seen, last_seen)
        overlap_start = max(search_interval[0], img_interval[0])
        overlap_end = min(search_interval[1], img_interval[1])
        overlap = max(0, overlap_end - overlap_start)
        return overlap

    def send_matched_pair(self, obstacle_id, img_id):
        """
        Match the detected image with the given obstacle ID and send the information to the PC.
        """
        logging.info(f"Matched image {img_id} to obstacle {obstacle_id}.")
        self.ids_to_stitch.append(img_id)
        logging.info(f"{len(self.ids_to_stitch)} images in current stitching array.")
        
        # Format: OBJECT,<obstacle_id>,<confidence_level>,<image_id>
        message_content = f"OBJECT,{obstacle_id},{self.stitching_img_dict[img_id][0]},{img_id}\n"
        self.IMG_BLACKLIST.append(str(img_id))
        logging.info(f"Sending: {message_content}")
        self.sock.send(message_content.encode("utf-8"))
        
        # Clear stale images from stitching dict
        self.stitching_img_dict = {
            k: v for k, v in self.stitching_img_dict.items()
            if str(k) in self.IMG_BLACKLIST  # keep only those that are matched
        }
        
    def pc_receive(self) -> None:
        self.connect()
        logging.info("PC Socket connection started successfully")

        while not self.exit:
            try:
                data_str = self.sock.recv(1024).decode("utf-8")
                logging.info(f"Received from RPI: {data_str}")
                
                if data_str.startswith("OBSTACLES"):
                    # parse obstacles
                    obstacles = self._parse_obstacles(data_str)
                    logging.info(f"Parsed obstacles: {obstacles}")
                    
                    # call pathfinding
                    path = pathfinding(obstacles)
                    # logging.info(f"Computed path: {path}")
                    
                    commands = path['commands']
                    segments = self._segment_commands(commands)
                    segments['dirs'] = self.get_directions(path)
                    logging.info(f"Segmented commands: {segments}")
                    
                    # send path back to server
                    self.sock.send(f"PATH,{json.dumps(segments)}\n".encode("utf-8"))
                    logging.info(f"Sent path back to rpi.")

                elif "DETECT" in data_str:
                    obstacle_id = data_str.split(",")[1]
                    timestamp = time_ns()
                    
                    max_overlap = 0
                    max_img_id = None
                    for img_id, (first_seen, last_seen) in self.img_time_dict.items():
                        overlap = self.get_overlap_interval(img_id, timestamp, first_seen, last_seen)
                        logging.info(f"Overlap: {overlap}, Max overlap: {max_overlap}")
                        if overlap > 0 and overlap >= max_overlap:
                            logging.info(f"Replacing max overlap with {overlap}")
                            max_overlap = overlap
                            max_img_id = img_id
                    
                    if max_img_id is not None:
                        self.send_matched_pair(obstacle_id, max_img_id)
                        del self.img_time_dict[max_img_id]
                    else:
                        self.pending_obstacles.append((obstacle_id, timestamp))

                elif "STITCH" in data_str:
                    self.stitch_len = int(data_str.split(",")[1])
                    
                    # Sanity check to see if all images have been detected. If not, wait for more images to be detected.
                    if len(self.ids_to_stitch) < self.stitch_len:
                        logging.info("Stitch request received, wait for completion...")
                        self.should_stitch = True
                        sleep(self.lag * 2e-9)
                        # If still not enough images, stitch what we have
                        stitch_images(self.ids_to_stitch, self.stitching_img_dict, filename=self.filename)
                    else:
                        logging.info("All images present, stitching now...")
                        self.stream_listener.close()
                        stitch_images(self.ids_to_stitch, self.stitching_img_dict, filename=self.filename)

                if not data_str:
                    logging.info("Connection closed by server.")
                    if self.ids_to_stitch:
                        stitch_images(self.ids_to_stitch, self.stitching_img_dict, filename=self.filename)
                    break
            except OSError as e:
                logging.error(f"Error in sending data: {e}")
                break
            
    def start_stream(self):
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
            self.sock.close()
            self.sock = None
            self.exit = True
        
    def start_task_1(self):        
        self.pc_receive_thread = threading.Thread(target=self.pc_receive, daemon=True)
        print("Starting Task 1 server...")
        self.stream_listener = threading.Thread(target=self.start_stream, daemon=True)
        self.stream_listener.start()
        self.pc_receive_thread.start()
        self.pc_receive_thread.join()
                
    def _parse_obstacles(self, data_str):
        parts = data_str.split("OBSTACLES,")
        obstacle = json.loads(parts[1])
        return obstacle
    
    def _segment_commands(self, commands):
        # segment based on 'SNAP' commands into a list of lists
        segments = []
        current_segment = []
        obstacle_ids = []
        for cmd in commands:
            dist = cmd[2:]
            if cmd.startswith("BW"):
                cmd = "R"
                cmd += dist
            elif cmd.startswith("BL"):
                cmd = "RL"
                cmd += dist
            elif cmd.startswith("BR"):
                cmd = "RR"
                cmd += dist
            elif cmd.startswith("FW"):
                cmd = "F"
                cmd += dist
            elif cmd.startswith("FIN"):
                cmd = "S"
            if cmd.startswith("SNAP"):
                # SNAP<obstacle_id>[_L|_C|_R]
                snap_payload = cmd[4:]
                snap_id = snap_payload.split("_", 1)[0]
                obstacle_ids.append(snap_id)
                segments.append(current_segment)
                current_segment = []
                continue
            current_segment.append(cmd)
        if current_segment:
            segments.append(current_segment)
        return {"obstacle_ids": obstacle_ids, "segments": segments}
    
    def direction_to_name(self, d):
        """Return 'NORTH', 'SOUTH', etc. Works if d is an enum, int, or string."""
        # Already an enum with .name
        if hasattr(d, "name"):
            return d.name
        # Int -> enum name if possible
        try:
            return Direction(int(d)).name
        except Exception:
            pass
        # Fallback: if it's already a string
        if isinstance(d, str):
            return d.upper()
        # Last resort
        return str(d)
    
    def get_directions(self, full_path):
        path = full_path['path'][1:] if full_path else []
        # dirs = [{
        #         'd': self.direction_to_name(cmd['d']),
        #         'x': int(cmd['x']),
        #         'y': int(cmd['y'])
        #     } for cmd in path]
        
        dirs = [{
                'd': "NORTH",
                'x': 1,
                'y': 1
            }]

        return dirs
    
    def test_pathfinding(self):
        obstacles = [
            {"x": 10,  "y": 10,  "id": 1, "d": 2},
            {"x": 5, "y": 12,  "id": 2, "d": 4},
            {"x": 8, "y": 5,  "id": 3, "d": 0},
            {"x": 11, "y": 14, "id": 4, "d": 2},
            {"x": 15, "y": 12, "id": 5, "d": 6},
            {"x": 16, "y": 19, "id": 6, "d": 4},
            # {"x": 19,  "y": 9, "id": 7, "d": 6},
            # {"x": 7,  "y": 19, "id": 8, "d": 4},
        ]
        path = pathfinding(obstacles, robot_x=1, robot_y=1, big_turn=self.big_turn)
        print(path)
        snap = self.get_directions(path)
        print(snap)
        segments = self._segment_commands(path['commands'])
        print(segments)
        # for ob_id in segments['obstacle_ids']:
        #     print(self.direction_to_name((obstacles[int(ob_id) - 1]["d"] + 4) % 8))
        
server = Task1()
# server.test_pathfinding()
server.start_task_1()

