import serial
import time
import csv

# Adjust this to the correct Pi serial port (e.g., /dev/ttyUSB0 if using a cable, or /dev/serial0 for GPIO)
SERIAL_PORT = '/dev/serial0' 
BAUD_RATE = 115200
RECORD_TIME = 2.5  # Seconds to record

def main():
    print(f"Connecting to STM32 on {SERIAL_PORT}...")
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
    time.sleep(1) # Let connection settle

    # Flush old data so we only capture the fresh step response
    ser.reset_input_buffer() 
    
    # Send the forward command
    print("Triggering f1000...")
    ser.write(b'f1000\n')
    
    start_time = time.time()
    data_log = []

    print(f"Recording data for {RECORD_TIME} seconds...")
    while time.time() - start_time < RECORD_TIME:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if ',' in line:
            try:
                a, b = line.split(',')
                # Record timestamp, motor A, motor B
                data_log.append([round(time.time() - start_time, 3), a, b])
            except ValueError:
                pass # Ignore malformed lines during transit

    # Stop the car safely
    ser.write(b's\n')
    ser.close()

    # Save to CSV
    filename = 'motor_log.csv'
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Time_s', 'Motor_A', 'Motor_B'])
        writer.writerows(data_log)
        
    print(f"Done! Saved {len(data_log)} samples to {filename}")

if __name__ == '__main__':
    main()