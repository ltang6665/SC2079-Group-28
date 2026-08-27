import os
import json
from time import sleep
from threading import Thread, Event
from time import time
import logging
logging.basicConfig(level=logging.INFO)

from dotenv import load_dotenv
load_dotenv()

from communications.android import Android
from communications.pc import PC
from communications.stm import STM
from streaming.stream_server import StreamServer

class Checklist:
    """
    Class for managing the checklist process.
    """

    def __init__(self):
        """
        Constructor for Checklist.
        Initializes communication with Android tablet, PC, and STM32 microcontroller.
        """
        self.process_pc_stream = None
        self.pc_thread = None
        self.android_thread = None
        self.stm_thread = None
        
        self.android = Android()
        self.pc = PC()
        self.stm = STM()
        
        self.stop_event = Event()
        self.detect_event = Event()
        
        self.obstacles = []
        self.detect_image = False
        self.stm_stopped = False
        self.stop = False
        
        self.segments = []
        self.segments_index = 0
        self.obstacle_order = []
        
        self.timeout = 2  # seconds

    def start_checklist_one(self):
        """
        Starts the checklist process.
        """
        logging.info("Starting checklist 1 process.")
        self.android.connect()
        self.stm.connect()
        
        logging.info("Waiting for message from Android...")
        android_msg = self.android.wait_receive()
        self.stm.send("FW20" + "\n")
        
        self.android.disconnect()
        self.stm.disconnect()
        
    def test_rpi_android_pc(self):
        """
        Test the communication between Raspberry Pi, Android tablet, and PC.
        """
        logging.info("Starting RPI-Android-PC test.")
        self.android.connect()
        self.pc.connect()
        obstacles = []

        while True:
            # messages come in the format "OBSTACLE,id,x,y,dir" e.g "OBSTACLE,2,50,160,NORTH"
            # keep listening until receive "BEGIN"
            android_msg = self.android.wait_receive()
            if android_msg == "BEGIN":
                logging.info("Received BEGIN from Android, ending obstacle input.")
                break
            #Convert OBSTACLE message to a dict with keys id, x, y, dir. dir converted to int where NORTH=0, EAST=2, SOUTH=4, WEST=6, SKIP=8 (for no obstacle)
            
            logging.info(f"Received from Android: {android_msg}")
            msg_parts = android_msg.split(',')
            if msg_parts[0] == "OBSTACLE":
                obstacle = {
                    "id": int(msg_parts[1]),
                    "x": int(msg_parts[2]),
                    "y": int(msg_parts[3]),
                    "d": {"NORTH": 0, "EAST": 2, "SOUTH": 4, "WEST": 6, "SKIP": 8}.get(msg_parts[4], -1)
                }
                obstacles.append(obstacle)
                logging.info(f"Added obstacle: {obstacle}")
        
        self.pc.send("OBSTACLES," + json.dumps(obstacles))
        logging.info("Sent obstacles to PC.")
        
        pc_msg = self.pc.wait_receive()
        logging.info(f"Received from PC: {pc_msg}")
            
        self.android.disconnect()
        self.pc.disconnect()
        
    def checklist_a5(self):
        """
        Send 4 obstacles on the same (x,y) but different directions to the PC. Get back commands and send to STM32. The robot will visit each side of the obstacle. If image is detected, end, else continue.
        """
        logging.info("Starting checklist A5 process.")
        self.initialize()
        
        obstacles = [
            {"x": 10, "y": 10, "id": 1, "d": 0},
            {"x": 10, "y": 10, "id": 2, "d": 2},
            {"x": 10, "y": 10, "id": 3, "d": 4},
            {"x": 10, "y": 10, "id": 4, "d": 6},
        ]
        
        self.process_pc_stream = Thread(target=self.stream_start)
        self.process_pc_stream.start()
        sleep(5)

        logging.info("starting stream")
        
        self.pc_thread = Thread(target=self.pc_receive)
        self.stm_thread = Thread(target=self.stm_receive)
        self.pc_thread.start()
        self.stm_thread.start()
        self.pc.send("OBSTACLES," + json.dumps(obstacles))
        logging.info("Sent obstacles to PC.")
        self.pc_thread.join()
        self.stm_thread.join()
        
    def initialize(self):
        self.pc.connect()
        self.stm.connect()
        
    def stream_start(self):
        StreamServer().connect()
            
    def pc_receive(self) -> None:
        while True:
            try:
                pc_msg = self.pc.receive()
                print(f"Received from PC: {pc_msg}")
                if pc_msg.startswith("PATH"):
                    path = json.loads(pc_msg.split("PATH,")[1])
                    self.segments = path['segments']
                    self.obstacle_order = path['obstacle_ids']
                    logging.info(f"Received path segments: {self.segments}")
                    
                    cmd = ",".join(self.segments[self.segments_index]) + "\n"
                    self.stm.send(f"{cmd}")
                    logging.info(f"Sent path segment {self.segments_index + 1} to STM: {cmd}")
                    self.segments_index += 1
                elif pc_msg.startswith("OBJECT"):
                    self.detect_image = False
                    msg_split = pc_msg.split(",")[1:]

                    obstacle_id, conf_str, object_id = msg_split
                    confidence_level = None

                    try:
                        confidence_level = float(conf_str)
                    except ValueError:
                        confidence_level = None

                    print("OBJECT ID:", object_id)

                    if confidence_level is not None:
                        self.stop_event.set()
                        self.detect_event.set()
                        self.pc.send(f'STITCH')

            except OSError as e:
                print(f"Error: {e}")
                break
            
    def stm_receive(self) -> None:
        while True:
            try:
                if self.stop_event.is_set():
                    logging.info("Stop event set")
                    break
                stm_msg = self.stm.receive()
                if not stm_msg:
                    continue
                print(f"Received from STM: {stm_msg}")
                # if "SNAP" in stm_msg:
                #     self.detect_image = True
                #     message_content = f"DETECT,{self.obstacle_order[self.segments_index - 1]}"
                #     self.pc.send(message_content.encode("utf-8"))
                if "OK" in stm_msg:
                    self.detect_image = True
                    message_content = f"DETECT,{self.obstacle_order[self.segments_index - 1]}"
                    self.pc.send(message_content)
                    
                    # end_time = time() + self.timeout
                    # # if image still being processed, wait until done or timeout
                    # while self.detect_image and time() < end_time:
                    #     pass
                    
                    # if self.stop_event.is_set():
                    #     logging.info("Stop event observed")
                    #     break
                    self.detect_event.clear()
                    deadline = time() + self.timeout
                    while True:
                        if self.stop_event.is_set():
                            logging.info("Stop observed in stm_receive; halting.")
                            try:
                                self.stm.send("S\n")   # optional
                            except Exception:
                                pass
                            return  # or break the loop

                        if self.detect_event.is_set():
                            break  # PC replied with OBJECT

                        if time() >= deadline:
                            logging.info("Detection wait timed out.")
                            break

                        # tiny sleep to avoid hot loop; stm.receive is separate
                        # (or use time.sleep(0.01))
                        pass
                    
                    if self.segments_index < len(self.segments):
                        cmd = ",".join(self.segments[self.segments_index]) + "\n"
                        self.stm.send(f"{cmd}")
                        logging.info(f"Sent path segment {self.segments_index + 1}/{len(self.segments)} to STM: {self.segments[self.segments_index]}")
                        self.segments_index += 1
                    else:
                        self.pc.send(f'STITCH,{len(self.segments) - 1}') # -1 cause of FIN segment
                        self.android.disconnect()
                        self.pc.disconnect()
                        self.stm.disconnect()
            except OSError as e:
                    print(f"Error: {e}")
                    continue
        

if __name__ == "__main__":
    checklist = Checklist()
    checklist.checklist_a5()