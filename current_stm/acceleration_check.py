import serial
import time
import matplotlib.pyplot as plt

# Update with your actual Windows COM port
SERIAL_PORT = 'COM3' 
BAUD_RATE = 115200

def main():
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
    time.sleep(1) # Allow connection to settle
    
    # Send the forward command to trigger the acceleration
    ser.write(b'f1000\n')
    
    times, a_vals, b_vals = [], [], []
    start_time = time.time()
    
    print("Recording data...")
    # Record telemetry for 2.5 seconds
    while time.time() - start_time < 2.5:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if ',' in line:
            try:
                a, b = map(int, line.split(','))
                times.append(time.time() - start_time)
                a_vals.append(a)
                b_vals.append(b)
            except ValueError:
                pass # Ignore malformed lines
                
    ser.write(b's\n') # Send stop command just in case
    ser.close()
    
    # Plotting the results
    plt.figure(figsize=(10, 5))
    plt.plot(times, a_vals, label='Motor A (Left)', alpha=0.8)
    plt.plot(times, b_vals, label='Motor B (Right)', alpha=0.8)
    plt.title('Motor Acceleration Profile (Step Response)')
    plt.xlabel('Time (seconds)')
    plt.ylabel('Speed (Encoder Deltas / 20ms)')
    plt.legend()
    plt.grid(True)
    plt.show()

if __name__ == '__main__':
    main()