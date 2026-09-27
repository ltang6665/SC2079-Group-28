# import cv2
# from picamera.array import PiRGBArray
# from picamera import PiCamera
# import time
# import os

# # Create folder to save images
# save_folder = "photos"
# if not os.path.exists(save_folder):
#     os.makedirs(save_folder)

# camera = PiCamera()
# camera.resolution = (640, 480)
# camera.framerate = 30
# raw_capture = PiRGBArray(camera, size=camera.resolution)

# time.sleep(1)  # Camera warm-up

# photo_counter = 1
# print("Press any key in the window to take a photo. Press 'q' to quit.")

# for frame in camera.capture_continuous(raw_capture, format="bgr", use_video_port=True):
#     image = frame.array
#     cv2.imshow("Camera Preview", image)

#     key = cv2.waitKey(1) & 0xFF
#     if key == ord('q'):  # Quit on 'q'
#         break
#     elif key != 255:  # Any other key pressed
#         filename = os.path.join(save_folder, "image_{}.jpg".format(photo_counter))
#         cv2.imwrite(filename, image)
#         print("Saved {}".format(filename))
#         photo_counter += 1

#     raw_capture.truncate(0)  # Clear the stream for the next frame

# camera.close()
# cv2.destroyAllWindows()

from picamera import PiCamera
from time import sleep
import os

# Path to counter file
counter_file = "/home/pi/MDP/photos/counter.txt"

# Ensure photos folder exists
os.makedirs("/home/pi/MDP/", exist_ok=True)

# Load last counter value if file exists, else create it with 1
if os.path.exists(counter_file):
    with open(counter_file, "r") as f:
        try:
            counter = int(f.read().strip())
        except ValueError:
            counter = 21  # reset if file is empty/corrupted
else:
    counter = 21
    with open(counter_file, "w") as f:
        f.write(str(counter))
print("Success")
camera = PiCamera()
print("Yes")
camera.rotation = 180

while True:
    stro = input("Press Enter to take a photo or type 'e' to quit: ")
    if stro == 'e':
        break

    image_path = f"/home/pi/MDP/photos/image{counter}.jpg"
    camera.start_preview()
    camera.capture(image_path)
    camera.stop_preview()
    print(f"Saved: {image_path}")

    counter += 1
    with open(counter_file, "w") as f:
        f.write(str(counter))

    # S
