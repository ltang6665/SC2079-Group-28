import serial
import time
import csv

SERIAL_PORT = '/dev/serial0'
BAUD_RATE = 115200
RECORD_TIME = 2.5


def main():
    print(f"Connecting to STM32 on {SERIAL_PORT}...")

    ser = serial.Serial(
        SERIAL_PORT,
        BAUD_RATE,
        timeout=0.1
    )

    time.sleep(1)

    # Remove old messages already sitting in the RX buffer
    ser.reset_input_buffer()

    print("Triggering f1000...")
    ser.write(b'f1000\n')

    start_time = time.time()

    data_log = []

    print(f"Recording data for {RECORD_TIME} seconds...")

    while time.time() - start_time < RECORD_TIME:

        line = (
            ser.readline()
            .decode('utf-8', errors='ignore')
            .strip()
        )

        # Only process encoder packets
        if not line.startswith("E,"):
            continue

        try:
            _, stm_tick, a, b = line.split(',')

            data_log.append([
                int(stm_tick) / 1000.0,
                int(a),
                int(b)
            ])

        except ValueError:
            pass

    # Stop robot
    ser.write(b's\n')

    time.sleep(0.1)

    ser.close()

    filename = 'motor_log.csv'

    with open(filename, 'w', newline='') as f:

        writer = csv.writer(f)

        writer.writerow([
            'Time_s',
            'Motor_A',
            'Motor_B'
        ])

        writer.writerows(data_log)

    print(
        f"Done! Saved {len(data_log)} samples "
        f"to {filename}"
    )


if __name__ == '__main__':
    main()