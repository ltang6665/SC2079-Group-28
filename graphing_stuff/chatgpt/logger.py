"""Record STM32 robot telemetry without merging data across MCU resets.

Examples
--------
Raspberry Pi GPIO UART::

    python logger_fixed.py --port /dev/serial0

Windows USB serial adapter::

    python logger_fixed.py --port COM5

The logger accepts the original ENC/TRN protocol and the optional STR record
described in SC2079_ROBOT_REPAIR_GUIDE.md.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

import serial


BAUD_RATE = 115200
RESET_BACKSTEP_MS = 1_000

CSV_FIELDS = [
    "host_time",
    "session_id",
    "record_type",
    "stm_tick_ms",
    "command_id",
    "command",
    "motor_a_delta",
    "motor_b_delta",
    "sample_dt_ms",
    "yaw_deg",
    "target_deg",
    "yaw_rate_dps",
    "turn_error_deg",
    "turn_effort",
    "left_pwm",
    "right_pwm",
    "servo_ccr",
    "servo_center_ccr",
    "servo_offset_ccr",
    "steer_cmd_percent",
    "turn_phase",
    "fault_code",
]


def parse_args() -> argparse.Namespace:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_port = "COM3" if sys.platform.startswith("win") else "/dev/serial0"

    parser = argparse.ArgumentParser(description="Record SC2079 robot telemetry")
    parser.add_argument(
        "--port",
        default=default_port,
        help=f"Serial port (default: {default_port})",
    )
    parser.add_argument("--baud", type=int, default=BAUD_RATE)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(f"rt_{timestamp}.csv"),
    )
    return parser.parse_args()


class SessionTracker:
    """Assign a new session whenever the STM32 millisecond tick restarts."""

    def __init__(self) -> None:
        self.session_id = 1
        self.last_tick: int | None = None

    def observe(self, tick: int) -> tuple[int, bool]:
        reset_detected = False

        if (
            self.last_tick is not None
            and tick + RESET_BACKSTEP_MS < self.last_tick
        ):
            self.session_id += 1
            reset_detected = True

        self.last_tick = tick
        return self.session_id, reset_detected


def empty_record() -> dict[str, object]:
    return {field: "" for field in CSV_FIELDS}


def scaled_angle(value: str) -> float:
    return int(value) / 1000.0


def decode_line(
    line: str,
    tracker: SessionTracker,
) -> tuple[dict[str, object] | None, bool]:
    parts = line.split(",")
    kind = parts[0]

    try:
        if kind == "CMD" and len(parts) == 4:
            command_id = int(parts[1])
            tick = int(parts[2])
            session_id, reset = tracker.observe(tick)

            row = empty_record()
            row.update(
                host_time=time.time(),
                session_id=session_id,
                record_type="CMD",
                stm_tick_ms=tick,
                command_id=command_id,
                command=parts[3],
            )
            return row, reset

        # Original: ENC,tick,id,a,b
        # Extended: ENC,tick,id,a,b,dt_ms
        if kind == "ENC" and len(parts) in (5, 6):
            tick = int(parts[1])
            session_id, reset = tracker.observe(tick)

            row = empty_record()
            row.update(
                host_time=time.time(),
                session_id=session_id,
                record_type="ENC",
                stm_tick_ms=tick,
                command_id=int(parts[2]),
                motor_a_delta=int(parts[3]),
                motor_b_delta=int(parts[4]),
                sample_dt_ms=int(parts[5]) if len(parts) == 6 else "",
            )
            return row, reset

        # TRN,tick,id,yaw,target,rate,error,effort,left,right,phase
        if kind == "TRN" and len(parts) == 11:
            tick = int(parts[1])
            session_id, reset = tracker.observe(tick)

            row = empty_record()
            row.update(
                host_time=time.time(),
                session_id=session_id,
                record_type="TRN",
                stm_tick_ms=tick,
                command_id=int(parts[2]),
                yaw_deg=scaled_angle(parts[3]),
                target_deg=scaled_angle(parts[4]),
                yaw_rate_dps=scaled_angle(parts[5]),
                turn_error_deg=scaled_angle(parts[6]),
                turn_effort=int(parts[7]),
                left_pwm=int(parts[8]),
                right_pwm=int(parts[9]),
                turn_phase=int(parts[10]),
            )
            return row, reset

        # Straight telemetry
        #
        # Old format:
        # STR,tick,id,yaw,target,rate,error,servo,left_pwm,right_pwm
        #
        # New format:
        # STR,tick,id,yaw,target,rate,error,
        #     servo,center,steer_percent,left_pwm,right_pwm

        if kind == "STR" and len(parts) in (10, 12):
            tick = int(parts[1])
            session_id, reset = tracker.observe(tick)

            row = empty_record()

            servo_ccr = int(parts[7])

            if len(parts) == 12:
                # New telemetry format
                servo_center = int(parts[8])
                steer_percent = scaled_angle(parts[9])
                left_pwm = int(parts[10])
                right_pwm = int(parts[11])

                servo_offset = servo_ccr - servo_center

            else:
                # Old telemetry format compatibility
                servo_center = ""
                servo_offset = ""
                steer_percent = ""

                left_pwm = int(parts[8])
                right_pwm = int(parts[9])

            row.update(
                host_time=time.time(),
                session_id=session_id,
                record_type="STR",
                stm_tick_ms=tick,
                command_id=int(parts[2]),
                yaw_deg=scaled_angle(parts[3]),
                target_deg=scaled_angle(parts[4]),
                yaw_rate_dps=scaled_angle(parts[5]),
                turn_error_deg=scaled_angle(parts[6]),
                servo_ccr=servo_ccr,
                servo_center_ccr=servo_center,
                servo_offset_ccr=servo_offset,
                steer_cmd_percent=steer_percent,
                left_pwm=left_pwm,
                right_pwm=right_pwm,
            )

            return row, reset
        
        # Optional fault telemetry: FLT,tick,id,code
        if kind == "FLT" and len(parts) == 4:
            tick = int(parts[1])
            session_id, reset = tracker.observe(tick)

            row = empty_record()
            row.update(
                host_time=time.time(),
                session_id=session_id,
                record_type="FLT",
                stm_tick_ms=tick,
                command_id=int(parts[2]),
                fault_code=parts[3],
            )
            return row, reset

    except ValueError:
        return None, False

    return None, False


def main() -> int:
    args = parse_args()
    tracker = SessionTracker()

    try:
        ser = serial.Serial(args.port, args.baud, timeout=1)
    except serial.SerialException as exc:
        print(f"Could not open {args.port}: {exc}", file=sys.stderr)
        return 1

    print(f"Logging {args.port} at {args.baud} baud to {args.output}")
    print("Press Ctrl+C to stop.")

    try:
        with ser, args.output.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
            writer.writeheader()

            while True:
                raw = ser.readline()
                if not raw:
                    continue

                try:
                    line = raw.decode("ascii", errors="strict").strip()
                except UnicodeDecodeError:
                    continue

                if not line:
                    continue

                print(line)
                row, reset_detected = decode_line(line, tracker)

                if reset_detected:
                    print(
                        f"--- STM32 reset detected; starting session "
                        f"{tracker.session_id} ---"
                    )

                if row is not None:
                    writer.writerow(row)
                    stream.flush()

    except KeyboardInterrupt:
        print(f"\nLogging stopped. Saved: {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
