"""Plot SC2079 telemetry as separate command runs and respect real sample time.

This version fixes two important problems in the original plotter:

1. command IDs are scoped to an STM32 boot session, so ID 1 after a reset is
   not merged with ID 1 from an earlier boot;
2. encoder delta is divided by its actual sampling interval instead of always
   assuming exactly 20 ms.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt


NOMINAL_SAMPLE_MS = 20.0
RESET_BACKSTEP_MS = 1_000


def new_run() -> dict[str, object]:
    return {
        "command": "UNKNOWN",
        "enc_time": [],
        "enc_dt_ms": [],
        "a_delta": [],
        "b_delta": [],
        "turn_time": [],
        "yaw": [],
        "target": [],
        "yaw_rate": [],
        "error": [],
        "effort": [],
        "left_pwm": [],
        "right_pwm": [],
        "phase": [],
        "straight_time": [],
        "straight_yaw": [],
        "straight_target": [],
        "straight_rate": [],
        "straight_error": [],
        "servo_ccr": [],
        "straight_left_pwm": [],
        "straight_right_pwm": [],
        "faults": [],
    }


def as_int(row: dict[str, str], field: str) -> int:
    return int(row[field])


def as_float(row: dict[str, str], field: str) -> float:
    return float(row[field])


def load_log(
    filename: Path,
) -> tuple[dict[tuple[int, int], dict], int, dict[int, list[str]]]:
    runs: defaultdict[tuple[int, int], dict] = defaultdict(new_run)
    names: dict[tuple[int, int], str] = {}
    last_enc_tick: dict[int, int] = {}
    session_faults: defaultdict[int, list[str]] = defaultdict(list)

    inferred_session = 1
    last_global_tick: int | None = None
    highest_session = 1

    with filename.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)

        for row in reader:
            try:
                tick = as_int(row, "stm_tick_ms")
            except (KeyError, TypeError, ValueError):
                continue

            explicit_session = row.get("session_id", "").strip()
            if explicit_session:
                try:
                    session = int(explicit_session)
                except ValueError:
                    continue
            else:
                if (
                    last_global_tick is not None
                    and tick + RESET_BACKSTEP_MS < last_global_tick
                ):
                    inferred_session += 1
                session = inferred_session

            highest_session = max(highest_session, session)
            last_global_tick = tick
            kind = row.get("record_type", "")

            try:
                command_id = as_int(row, "command_id")
            except (KeyError, TypeError, ValueError):
                command_id = 0

            key = (session, command_id)

            if kind == "CMD":
                names[key] = row.get("command", "UNKNOWN") or "UNKNOWN"
                runs[key]["command"] = names[key]
                continue

            if kind == "ENC":
                previous_tick = last_enc_tick.get(session)
                supplied_dt = row.get("sample_dt_ms", "").strip()

                if supplied_dt:
                    try:
                        dt_ms = float(supplied_dt)
                    except ValueError:
                        dt_ms = NOMINAL_SAMPLE_MS
                elif previous_tick is not None:
                    dt_ms = float(tick - previous_tick)
                else:
                    dt_ms = NOMINAL_SAMPLE_MS

                last_enc_tick[session] = tick

                # ID zero is idle data. It is still used above to establish the
                # interval of the first sample after a command starts.
                if command_id == 0:
                    continue

                if dt_ms <= 0.0 or dt_ms > 1_000.0:
                    dt_ms = NOMINAL_SAMPLE_MS

                try:
                    motor_a = as_int(row, "motor_a_delta")
                    motor_b = as_int(row, "motor_b_delta")
                except (KeyError, TypeError, ValueError):
                    continue

                run = runs[key]
                run["enc_time"].append(tick / 1000.0)
                run["enc_dt_ms"].append(dt_ms)
                run["a_delta"].append(motor_a)
                run["b_delta"].append(motor_b)
                continue

            if kind == "FLT":
                code = row.get("fault_code", "UNKNOWN") or "UNKNOWN"
                session_faults[session].append(code)
                if command_id != 0:
                    runs[key]["faults"].append(code)
                continue

            if command_id == 0:
                continue

            run = runs[key]

            if kind == "TRN":
                try:
                    run["turn_time"].append(tick / 1000.0)
                    run["yaw"].append(as_float(row, "yaw_deg"))
                    run["target"].append(as_float(row, "target_deg"))
                    run["yaw_rate"].append(as_float(row, "yaw_rate_dps"))
                    run["error"].append(as_float(row, "turn_error_deg"))
                    run["effort"].append(as_float(row, "turn_effort"))
                    run["left_pwm"].append(as_int(row, "left_pwm"))
                    run["right_pwm"].append(as_int(row, "right_pwm"))
                    run["phase"].append(as_int(row, "turn_phase"))
                except (KeyError, TypeError, ValueError):
                    # Keep arrays aligned by dropping a partially appended row.
                    lengths = [
                        len(run[name])
                        for name in (
                            "turn_time",
                            "yaw",
                            "target",
                            "yaw_rate",
                            "error",
                            "effort",
                            "left_pwm",
                            "right_pwm",
                            "phase",
                        )
                    ]
                    keep = min(lengths)
                    for name in (
                        "turn_time",
                        "yaw",
                        "target",
                        "yaw_rate",
                        "error",
                        "effort",
                        "left_pwm",
                        "right_pwm",
                        "phase",
                    ):
                        del run[name][keep:]
                continue

            if kind == "STR":
                try:
                    run["straight_time"].append(tick / 1000.0)
                    run["straight_yaw"].append(as_float(row, "yaw_deg"))
                    run["straight_target"].append(as_float(row, "target_deg"))
                    run["straight_rate"].append(as_float(row, "yaw_rate_dps"))
                    run["straight_error"].append(as_float(row, "turn_error_deg"))
                    run["servo_ccr"].append(as_int(row, "servo_ccr"))
                    run["straight_left_pwm"].append(as_int(row, "left_pwm"))
                    run["straight_right_pwm"].append(as_int(row, "right_pwm"))
                except (KeyError, TypeError, ValueError):
                    lengths = [
                        len(run[name])
                        for name in (
                            "straight_time",
                            "straight_yaw",
                            "straight_target",
                            "straight_rate",
                            "straight_error",
                            "servo_ccr",
                            "straight_left_pwm",
                            "straight_right_pwm",
                        )
                    ]
                    keep = min(lengths)
                    for name in (
                        "straight_time",
                        "straight_yaw",
                        "straight_target",
                        "straight_rate",
                        "straight_error",
                        "servo_ccr",
                        "straight_left_pwm",
                        "straight_right_pwm",
                    ):
                        del run[name][keep:]
                continue

    for key, run in runs.items():
        run["command"] = names.get(key, run["command"])

    # Discard placeholder entries that contain no command data.
    useful = {
        key: run
        for key, run in runs.items()
        if key[1] != 0
        and (
            run["enc_time"]
            or run["turn_time"]
            or run["straight_time"]
            or run["faults"]
        )
    }
    return useful, highest_session, dict(session_faults)


def moving_average(values: list[float], window: int) -> list[float]:
    if window <= 1 or len(values) < 2:
        return list(values)

    result: list[float] = []
    running = 0.0

    for index, value in enumerate(values):
        running += value
        if index >= window:
            running -= values[index - window]
        count = min(index + 1, window)
        result.append(running / count)

    return result


def relative(values: list[float], origin: float) -> list[float]:
    return [value - origin for value in values]


def safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in value)


def summarize_run(session: int, command_id: int, run: dict) -> None:
    command = run["command"]
    print(f"Session {session}, command {command_id}: {command}")

    dt_values = run["enc_dt_ms"]
    if dt_values:
        irregular = sum(not 15.0 <= value <= 30.0 for value in dt_values)
        print(
            f"  encoder samples={len(dt_values)}, "
            f"irregular intervals={irregular}"
        )

    if run["turn_time"]:
        duration = run["turn_time"][-1] - run["turn_time"][0]
        final_yaw = run["yaw"][-1]
        final_target = run["target"][-1]
        final_error = run["error"][-1]
        peak_rate = max(abs(value) for value in run["yaw_rate"])
        yaw_span = max(run["yaw"]) - min(run["yaw"])
        peak_effort = max(run["effort"])

        print(
            f"  duration={duration:.3f}s, final yaw={final_yaw:.2f}°, "
            f"target={final_target:.2f}°, error={final_error:+.2f}°, "
            f"peak rate={peak_rate:.1f}°/s"
        )

        demanded_change = abs(final_target - run["yaw"][0])
        if demanded_change > 10.0 and yaw_span < 1.0 and peak_effort > 500.0:
            print("  WARNING: gyro feedback appears frozen or invalid")
        elif abs(final_error) > 5.0:
            print("  WARNING: turn ended well outside the target tolerance")

    if run["straight_time"]:
        yaw_change = run["straight_yaw"][-1] - run["straight_yaw"][0]
        print(f"  straight-run yaw change={yaw_change:+.2f}°")

    if run["faults"]:
        print(f"  reported faults: {', '.join(run['faults'])}")


def plot_run(
    session: int,
    command_id: int,
    run: dict,
    smooth_window: int,
) -> plt.Figure:
    enc_time = run["enc_time"]
    turn_time = run["turn_time"]
    straight_time = run["straight_time"]

    origins = [series[0] for series in (enc_time, turn_time, straight_time) if series]
    origin = min(origins)

    enc_relative = relative(enc_time, origin)
    turn_relative = relative(turn_time, origin)
    straight_relative = relative(straight_time, origin)

    a_speed = [
        delta * 1000.0 / dt
        for delta, dt in zip(run["a_delta"], run["enc_dt_ms"])
    ]
    b_speed = [
        delta * 1000.0 / dt
        for delta, dt in zip(run["b_delta"], run["enc_dt_ms"])
    ]
    a_smooth = moving_average(a_speed, smooth_window)
    b_smooth = moving_average(b_speed, smooth_window)

    has_turn = len(turn_time) >= 2
    has_straight = len(straight_time) >= 2

    if has_turn:
        fig, axes = plt.subplots(4, 1, figsize=(11, 13), sharex=True)
        ax_speed, ax_heading, ax_error, ax_output = axes
    elif has_straight:
        fig, axes = plt.subplots(3, 1, figsize=(11, 10), sharex=True)
        ax_speed, ax_heading, ax_output = axes
    else:
        fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
        ax_speed, ax_accel = axes

    command = run["command"]
    title = f"Session {session}, Command {command_id}: {command}"
    fig.suptitle(title, fontsize=14)
    if fig.canvas.manager is not None:
        fig.canvas.manager.set_window_title(title)

    if enc_time:
        ax_speed.plot(enc_relative, a_speed, color="tab:blue", alpha=0.25)
        ax_speed.plot(enc_relative, b_speed, color="tab:orange", alpha=0.25)
        ax_speed.plot(enc_relative, a_smooth, label="Motor A (Left)", color="tab:blue")
        ax_speed.plot(enc_relative, b_smooth, label="Motor B (Right)", color="tab:orange")
    ax_speed.set_title("Wheel Speed (actual sample intervals)")
    ax_speed.set_ylabel("Encoder counts/s")
    ax_speed.legend()
    ax_speed.grid(True)

    if has_turn:
        ax_heading.plot(turn_relative, run["yaw"], label="Measured yaw")
        ax_heading.plot(
            turn_relative,
            run["target"],
            label="Target yaw",
            linestyle="--",
        )
        ax_heading.set_title("Yaw Tracking")
        ax_heading.set_ylabel("Angle (degrees)")
        ax_heading.legend()
        ax_heading.grid(True)

        ax_error.plot(turn_relative, run["error"], label="Yaw error", color="tab:red")
        ax_error.axhline(0.0, color="black", linewidth=1)
        ax_error.set_title("Error and Angular Speed")
        ax_error.set_ylabel("Error (degrees)")
        ax_error.grid(True)

        ax_rate = ax_error.twinx()
        ax_rate.plot(
            turn_relative,
            run["yaw_rate"],
            label="Yaw rate",
            color="tab:purple",
        )
        ax_rate.set_ylabel("Yaw rate (degrees/s)")
        lines1, labels1 = ax_error.get_legend_handles_labels()
        lines2, labels2 = ax_rate.get_legend_handles_labels()
        ax_error.legend(lines1 + lines2, labels1 + labels2, loc="best")

        ax_output.plot(turn_relative, run["left_pwm"], label="Left PWM compare")
        ax_output.plot(turn_relative, run["right_pwm"], label="Right PWM compare")
        ax_output.set_title("Controller Output (higher compare = less motor drive)")
        ax_output.set_ylabel("PWM compare")
        ax_output.set_xlabel("Time since command start (s)")
        ax_output.grid(True)

        ax_effort = ax_output.twinx()
        ax_effort.plot(
            turn_relative,
            run["effort"],
            label="Outer-wheel effort",
            color="tab:green",
            linestyle="--",
        )
        ax_effort.set_ylabel("Effort counts")
        lines1, labels1 = ax_output.get_legend_handles_labels()
        lines2, labels2 = ax_effort.get_legend_handles_labels()
        ax_output.legend(lines1 + lines2, labels1 + labels2, loc="best")

    elif has_straight:
        ax_heading.plot(straight_relative, run["straight_yaw"], label="Measured yaw")
        ax_heading.plot(
            straight_relative,
            run["straight_target"],
            label="Target yaw",
            linestyle="--",
        )
        ax_heading.set_title("Straight Heading")
        ax_heading.set_ylabel("Angle (degrees)")
        ax_heading.legend()
        ax_heading.grid(True)

        ax_output.plot(straight_relative, run["servo_ccr"], label="Servo CCR")
        ax_output.plot(
            straight_relative,
            run["straight_left_pwm"],
            label="Left PWM compare",
            alpha=0.8,
        )
        ax_output.plot(
            straight_relative,
            run["straight_right_pwm"],
            label="Right PWM compare",
            alpha=0.8,
        )
        ax_output.set_title("Straight Controller Outputs")
        ax_output.set_ylabel("CCR / PWM compare")
        ax_output.set_xlabel("Time since command start (s)")
        ax_output.legend()
        ax_output.grid(True)

    else:
        a_accel = [0.0]
        b_accel = [0.0]
        for index in range(1, len(a_smooth)):
            dt_s = run["enc_dt_ms"][index] / 1000.0
            if dt_s <= 0.0:
                dt_s = NOMINAL_SAMPLE_MS / 1000.0
            a_accel.append((a_smooth[index] - a_smooth[index - 1]) / dt_s)
            b_accel.append((b_smooth[index] - b_smooth[index - 1]) / dt_s)

        ax_accel.plot(enc_relative, a_accel, label="Motor A acceleration")
        ax_accel.plot(enc_relative, b_accel, label="Motor B acceleration")
        ax_accel.set_title("Smoothed Wheel Acceleration")
        ax_accel.set_xlabel("Time since command start (s)")
        ax_accel.set_ylabel("Encoder counts/s²")
        ax_accel.legend()
        ax_accel.grid(True)

    fig.tight_layout(rect=(0, 0, 1, 0.97))
    return fig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plot SC2079 robot telemetry")
    parser.add_argument("filename", type=Path)
    parser.add_argument(
        "--smooth",
        type=int,
        default=3,
        help="Trailing moving-average window for wheel speed (default: 3)",
    )
    parser.add_argument(
        "--save-dir",
        type=Path,
        help="Optional directory in which each command graph is saved as PNG",
    )
    parser.add_argument("--no-show", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.filename.exists():
        print(f"File not found: {args.filename}")
        return 1

    runs, session_count, session_faults = load_log(args.filename)
    print(f"Found {len(runs)} command runs across {session_count} STM32 sessions.")

    for session, faults in sorted(session_faults.items()):
        print(f"Session {session} faults: {', '.join(faults)}")

    if args.save_dir:
        args.save_dir.mkdir(parents=True, exist_ok=True)

    for (session, command_id), run in sorted(runs.items()):
        summarize_run(session, command_id, run)
        fig = plot_run(session, command_id, run, max(1, args.smooth))

        if args.save_dir:
            output = args.save_dir / (
                f"session_{session:02d}_command_{command_id:03d}_"
                f"{safe_name(run['command'])}.png"
            )
            fig.savefig(output, dpi=150)
            print(f"  saved {output}")

    if args.no_show:
        plt.close("all")
    else:
        plt.show()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
