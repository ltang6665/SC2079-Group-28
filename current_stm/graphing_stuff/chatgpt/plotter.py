import csv
import sys
import os
from collections import defaultdict

import matplotlib.pyplot as plt


SAMPLE_PERIOD = 0.020  # 20 ms = 50 Hz


def load_log(filename):

    data = defaultdict(
        lambda: {
            "time": [],
            "a": [],
            "b": [],
            "command": ""
        }
    )

    command_names = {}

    with open(filename, "r", newline="") as f:

        reader = csv.DictReader(f)

        for row in reader:

            record_type = row["record_type"]

            # ==============================
            # Command-start record
            # ==============================

            if record_type == "CMD":

                try:
                    command_id = int(row["command_id"])
                except ValueError:
                    continue

                command_names[command_id] = row["command"]

            # ==============================
            # Encoder sample
            # ==============================

            elif record_type == "ENC":

                try:
                    command_id = int(row["command_id"])
                    stm_tick_ms = int(row["stm_tick_ms"])
                    motor_a = int(row["motor_a_delta"])
                    motor_b = int(row["motor_b_delta"])

                except ValueError:
                    continue

                # command_id == 0 means robot is not executing
                # a logged command
                if command_id == 0:
                    continue

                data[command_id]["time"].append(
                    stm_tick_ms / 1000.0
                )

                data[command_id]["a"].append(
                    motor_a
                )

                data[command_id]["b"].append(
                    motor_b
                )

    # Attach command names after reading entire file
    for command_id in data:

        data[command_id]["command"] = (
            command_names.get(
                command_id,
                "UNKNOWN"
            )
        )

    return data


def plot_command(
    command_id,
    command_data
):

    times = command_data["time"]
    a_delta = command_data["a"]
    b_delta = command_data["b"]
    command = command_data["command"]

    if len(times) < 2:
        return

    # ==========================================
    # Relative command time
    # ==========================================

    t0 = times[0]

    relative_time = [
        t - t0
        for t in times
    ]

    # ==========================================
    # Convert encoder delta to speed
    #
    # counts / 20 ms -> counts / second
    # ==========================================

    a_speed = [
        value / SAMPLE_PERIOD
        for value in a_delta
    ]

    b_speed = [
        value / SAMPLE_PERIOD
        for value in b_delta
    ]

    # ==========================================
    # Calculate acceleration
    # ==========================================

    a_accel = [0.0]
    b_accel = [0.0]

    for i in range(1, len(a_speed)):

        dt = times[i] - times[i - 1]

        if dt <= 0:
            dt = SAMPLE_PERIOD

        a_accel.append(
            (a_speed[i] - a_speed[i - 1])
            / dt
        )

        b_accel.append(
            (b_speed[i] - b_speed[i - 1])
            / dt
        )

    # ==========================================
    # ONE WINDOW FOR THIS COMMAND
    # ==========================================

    fig, (ax_speed, ax_accel) = plt.subplots(
        2,
        1,
        figsize=(10, 8)
    )

    # Set actual Windows window title
    manager = fig.canvas.manager

    if manager is not None:
        manager.set_window_title(
            f"Command {command_id}: {command}"
        )

    # Main title for whole window
    fig.suptitle(
        f"Command {command_id}: {command}",
        fontsize=14
    )

    # ==========================================
    # SPEED GRAPH
    # ==========================================

    ax_speed.plot(
        relative_time,
        a_speed,
        label="Motor A (Left)",
        linewidth=2
    )

    ax_speed.plot(
        relative_time,
        b_speed,
        label="Motor B (Right)",
        linewidth=2
    )

    ax_speed.set_title(
        "Wheel Speed"
    )

    ax_speed.set_xlabel(
        "Time since command start (s)"
    )

    ax_speed.set_ylabel(
        "Encoder counts / second"
    )

    ax_speed.legend()
    ax_speed.grid(True)

    # ==========================================
    # ACCELERATION GRAPH
    # ==========================================

    ax_accel.plot(
        relative_time,
        a_accel,
        label="Motor A acceleration",
        linewidth=2
    )

    ax_accel.plot(
        relative_time,
        b_accel,
        label="Motor B acceleration",
        linewidth=2
    )

    ax_accel.set_title(
        "Wheel Acceleration"
    )

    ax_accel.set_xlabel(
        "Time since command start (s)"
    )

    ax_accel.set_ylabel(
        "Encoder acceleration (counts/s²)"
    )

    ax_accel.legend()
    ax_accel.grid(True)

    # Prevent graphs/titles overlapping
    fig.tight_layout()

def main():

    if len(sys.argv) != 2:

        print(
            "Usage: python3 plot_robot_log.py "
            "robot_telemetry.csv"
        )

        return

    filename = sys.argv[1]

    if not os.path.exists(filename):

        print(
            f"File not found: {filename}"
        )

        return

    data = load_log(filename)

    print(
        f"Found {len(data)} commands."
    )

    for command_id in sorted(data):

        command = data[
            command_id
        ]["command"]

        samples = len(
            data[command_id]["time"]
        )

        print(
            f"Plotting command "
            f"{command_id}: {command} "
            f"({samples} samples)"
        )

        plot_command(
            command_id,
            data[command_id]
        )
        
    plt.show()



if __name__ == "__main__":
    main()