import csv
import sys
import os
import math
from collections import defaultdict

import matplotlib.pyplot as plt


SAMPLE_PERIOD = 0.020  # 20 ms = 50 Hz

#True:first valid sample is 0 degrees. False: raw integrated gyro yaw.
""" The next command starts its plot at 0° again, even though the underlying gyro yaw continues accumulating.
its a signed net rotation: turning back toward the starting heading reduces the plotted yaw. It does not sum the absolute amount of turning. """
RELATIVE_YAW = True


def load_log(filename):

    data = defaultdict(
        lambda: {
            "time": [],
            "a": [],
            "b": [],
            "yaw": [],
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
                try:
                    yaw = float(row.get("yaw_deg", ""))
                    if not math.isfinite(yaw):
                        yaw = float("nan")
                except (ValueError, TypeError):
                    yaw = float("nan")
                data[command_id]["yaw"].append(yaw)

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
    yaw = command_data["yaw"]
    yaw_origin = next((value for value in yaw if math.isfinite(value)), 0.0)
    # Keep acquisition order, including repeated/decreasing yaw values.
    # total_angle is already cumulative; do not wrap it to +/-180 degrees.
    plot_yaw = [value - yaw_origin if RELATIVE_YAW else value for value in yaw]

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

    a_accel = [float("nan")]
    b_accel = [float("nan")]

    for i in range(1, len(a_speed)):

        dt = times[i] - times[i - 1]

        if dt <= 0:
            dt = float("nan")

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

    fig, axes = plt.subplots(
        2,
        2,
        figsize=(14, 9)
    )
    ax_speed, ax_speed_yaw = axes[0]
    ax_accel, ax_accel_yaw = axes[1]

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
        "Time since first command sample (s)"
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
        "Time since first command sample (s)"
    )

    ax_accel.set_ylabel(
        "Encoder acceleration (counts/s²)"
    )

    ax_accel.legend()
    ax_accel.grid(True)

    yaw_label = ("Yaw relative to first command sample (degrees)"
                 if RELATIVE_YAW else "Integrated gyro yaw (degrees)")
    for ax, a_values, b_values, title, units in (
        (ax_speed_yaw, a_speed, b_speed, "Wheel Speed vs Yaw", "Encoder counts / second"),
        (ax_accel_yaw, a_accel, b_accel, "Wheel Acceleration vs Yaw", "Encoder acceleration (counts/s²)"),
    ):
        ax.set_title(title)
        ax.set_xlabel(yaw_label)
        ax.set_ylabel(units)
        ax.grid(True)
        if any(math.isfinite(value) for value in plot_yaw):
            ax.plot(plot_yaw, a_values, ".-", label="Motor A (Left)", linewidth=1, markersize=3)
            ax.plot(plot_yaw, b_values, ".-", label="Motor B (Right)", linewidth=1, markersize=3)
            ax.legend()
        else:
            ax.text(0.5, 0.5, "No yaw data in this log.\nRecord a new log with updated firmware/logger.",
                    ha="center", va="center", transform=ax.transAxes)

    # Prevent graphs/titles overlapping
    fig.tight_layout(rect=(0, 0, 1, 0.95))

def main():

    if len(sys.argv) != 2:

        print(
            "Usage: python plotter.py "
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
