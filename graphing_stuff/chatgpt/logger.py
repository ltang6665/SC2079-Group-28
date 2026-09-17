import csv
import serial
import time
from datetime import datetime
from pathlib import Path


SERIAL_PORT = "/dev/serial0"
BAUD_RATE = 115200


timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

output_file = Path(
    f"robot_telemetry_{timestamp}.csv"
)


ser = serial.Serial(
    SERIAL_PORT,
    BAUD_RATE,
    timeout=1
)


with output_file.open(
    "w",
    newline=""
) as f:

    writer = csv.writer(f)

    writer.writerow([
        "host_time",
        "record_type",
        "stm_tick_ms",
        "command_id",
        "command",
        "motor_a_delta",
        "motor_b_delta",
        "yaw_deg",
        "target_deg",
        "yaw_rate_dps",
        "turn_error_deg",
        "turn_effort",
        "left_pwm",
        "right_pwm",
        "turn_phase"
    ])

    print(
        f"Logging telemetry to {output_file}"
    )

    print(
        "Press Ctrl+C to stop."
    )

    try:

        while True:

            raw = ser.readline()

            if not raw:
                continue

            try:
                line = raw.decode(
                    "ascii",
                    errors="strict"
                ).strip()

            except UnicodeDecodeError:
                continue

            if not line:
                continue

            print(line)

            parts = line.split(",")

            host_time = time.time()


            # ---------------------------------
            # CMD
            #
            # CMD,id,tick,command
            # ---------------------------------

            if (
                len(parts) == 4
                and parts[0] == "CMD"
            ):

                try:

                    command_id = int(parts[1])
                    stm_tick = int(parts[2])
                    command = parts[3]

                except ValueError:
                    continue

                writer.writerow([
                    host_time,
                    "CMD",
                    stm_tick,
                    command_id,
                    command,
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    ""
                ])

                f.flush()


            # ---------------------------------
            # ENC
            #
            # ENC,tick,id,a,b
            # ---------------------------------

            elif (
                len(parts) == 5
                and parts[0] == "ENC"
            ):

                try:

                    stm_tick = int(parts[1])
                    command_id = int(parts[2])
                    motor_a = int(parts[3])
                    motor_b = int(parts[4])

                except ValueError:
                    continue

                writer.writerow([
                    host_time,
                    "ENC",
                    stm_tick,
                    command_id,
                    "",
                    motor_a,
                    motor_b,
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    ""
                ])

                f.flush()


            # ---------------------------------
            # TRN
            #
            # Angles/rate arrive scaled by 1000:
            # TRN,tick,id,yaw,target,rate,error,
            #     effort,left_pwm,right_pwm,phase
            # ---------------------------------

            elif (
                len(parts) == 11
                and parts[0] == "TRN"
            ):

                try:

                    stm_tick = int(parts[1])
                    command_id = int(parts[2])
                    yaw_deg = int(parts[3]) / 1000.0
                    target_deg = int(parts[4]) / 1000.0
                    yaw_rate_dps = int(parts[5]) / 1000.0
                    turn_error_deg = int(parts[6]) / 1000.0
                    turn_effort = int(parts[7])
                    left_pwm = int(parts[8])
                    right_pwm = int(parts[9])
                    turn_phase = int(parts[10])

                except ValueError:
                    continue

                writer.writerow([
                    host_time,
                    "TRN",
                    stm_tick,
                    command_id,
                    "",
                    "",
                    "",
                    yaw_deg,
                    target_deg,
                    yaw_rate_dps,
                    turn_error_deg,
                    turn_effort,
                    left_pwm,
                    right_pwm,
                    turn_phase
                ])

                f.flush()


    except KeyboardInterrupt:

        print("\nLogging stopped.")


ser.close()

print(
    f"Saved: {output_file}"
)
