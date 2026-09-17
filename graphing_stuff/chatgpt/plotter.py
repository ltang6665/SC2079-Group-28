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
            "turn_time": [],
            "yaw": [],
            "target": [],
            "yaw_rate": [],
            "turn_error": [],
            "turn_effort": [],
            "left_pwm": [],
            "right_pwm": [],
            "turn_phase": [],
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

            # ==============================
            # Closed-loop turn sample
            # ==============================

            elif record_type == "TRN":

                try:
                    command_id = int(row["command_id"])
                    stm_tick_ms = int(row["stm_tick_ms"])
                    yaw_deg = float(row["yaw_deg"])
                    target_deg = float(row["target_deg"])
                    yaw_rate_dps = float(row["yaw_rate_dps"])
                    turn_error_deg = float(row["turn_error_deg"])
                    turn_effort = float(row["turn_effort"])
                    left_pwm = int(row["left_pwm"])
                    right_pwm = int(row["right_pwm"])
                    turn_phase = int(row["turn_phase"])

                except (KeyError, TypeError, ValueError):
                    continue

                if command_id == 0:
                    continue

                data[command_id]["turn_time"].append(
                    stm_tick_ms / 1000.0
                )
                data[command_id]["yaw"].append(yaw_deg)
                data[command_id]["target"].append(target_deg)
                data[command_id]["yaw_rate"].append(yaw_rate_dps)
                data[command_id]["turn_error"].append(turn_error_deg)
                data[command_id]["turn_effort"].append(turn_effort)
                data[command_id]["left_pwm"].append(left_pwm)
                data[command_id]["right_pwm"].append(right_pwm)
                data[command_id]["turn_phase"].append(turn_phase)

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
    turn_times = command_data["turn_time"]
    command = command_data["command"]

    has_encoder = len(times) >= 2
    has_turn = len(turn_times) >= 2

    if not has_encoder and not has_turn:
        return

    # ==========================================
    # Relative command time
    # ==========================================

    first_samples = []
    if times:
        first_samples.append(times[0])
    if turn_times:
        first_samples.append(turn_times[0])

    t0 = min(first_samples)

    relative_time = [
        t - t0
        for t in times
    ]

    turn_relative_time = [
        t - t0
        for t in turn_times
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

    if has_turn:
        fig, axes = plt.subplots(
            4,
            1,
            figsize=(11, 13),
            sharex=True
        )
        ax_speed, ax_heading, ax_error, ax_output = axes
    else:
        fig, axes = plt.subplots(
            2,
            1,
            figsize=(10, 8),
            sharex=True
        )
        ax_speed, ax_accel = axes

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

    if has_encoder:
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

    ax_speed.set_ylabel(
        "Encoder counts / second"
    )

    ax_speed.legend()
    ax_speed.grid(True)

    if has_turn:
        ax_heading.plot(
            turn_relative_time,
            command_data["yaw"],
            label="Measured yaw",
            linewidth=2
        )
        ax_heading.plot(
            turn_relative_time,
            command_data["target"],
            label="Target yaw",
            linewidth=2,
            linestyle="--"
        )
        ax_heading.set_title("Yaw Tracking")
        ax_heading.set_ylabel("Angle (degrees)")
        ax_heading.legend()
        ax_heading.grid(True)

        ax_error.plot(
            turn_relative_time,
            command_data["turn_error"],
            label="Yaw error",
            linewidth=2,
            color="tab:red"
        )
        ax_error.axhline(0.0, color="black", linewidth=1)
        ax_error.set_title("Error and Angular Speed")
        ax_error.set_ylabel("Error (degrees)")
        ax_error.grid(True)

        ax_rate = ax_error.twinx()
        ax_rate.plot(
            turn_relative_time,
            command_data["yaw_rate"],
            label="Yaw rate",
            linewidth=1.5,
            color="tab:purple"
        )
        ax_rate.set_ylabel("Yaw rate (degrees/s)")

        error_lines, error_labels = ax_error.get_legend_handles_labels()
        rate_lines, rate_labels = ax_rate.get_legend_handles_labels()
        ax_error.legend(
            error_lines + rate_lines,
            error_labels + rate_labels,
            loc="best"
        )

        ax_output.plot(
            turn_relative_time,
            command_data["left_pwm"],
            label="Left PWM compare",
            linewidth=1.5
        )
        ax_output.plot(
            turn_relative_time,
            command_data["right_pwm"],
            label="Right PWM compare",
            linewidth=1.5
        )
        ax_output.set_title(
            "Controller Output (higher PWM compare means less motor drive)"
        )
        ax_output.set_xlabel("Time since command start (s)")
        ax_output.set_ylabel("PWM compare")
        ax_output.grid(True)

        ax_effort = ax_output.twinx()
        ax_effort.plot(
            turn_relative_time,
            command_data["turn_effort"],
            label="Outer-wheel effort",
            linewidth=1.5,
            linestyle="--",
            color="tab:green"
        )
        ax_effort.set_ylabel("Effort counts")

        pwm_lines, pwm_labels = ax_output.get_legend_handles_labels()
        effort_lines, effort_labels = ax_effort.get_legend_handles_labels()
        ax_output.legend(
            pwm_lines + effort_lines,
            pwm_labels + effort_labels,
            loc="best"
        )

    else:
        # Acceleration is retained for non-turn commands.
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

        ax_accel.set_title("Wheel Acceleration")
        ax_accel.set_xlabel("Time since command start (s)")
        ax_accel.set_ylabel("Encoder acceleration (counts/s²)")
        ax_accel.legend()
        ax_accel.grid(True)

    # Prevent graphs/titles overlapping
    fig.tight_layout(rect=(0, 0, 1, 0.97))

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

        if data[command_id]["turn_error"]:
            final_yaw = data[command_id]["yaw"][-1]
            final_target = data[command_id]["target"][-1]
            final_error = data[command_id]["turn_error"][-1]
            peak_rate = max(
                abs(value)
                for value in data[command_id]["yaw_rate"]
            )

            print(
                f"  final yaw={final_yaw:.2f}°, "
                f"target={final_target:.2f}°, "
                f"error={final_error:+.2f}°, "
                f"peak rate={peak_rate:.1f}°/s"
            )

        plot_command(
            command_id,
            data[command_id]
        )
        
    plt.show()



if __name__ == "__main__":
    main()
