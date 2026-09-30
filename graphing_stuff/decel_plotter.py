"""Straight-run heading + deceleration analysis for the STM32 robot car.

New telemetry support:
- SPID rows carry the Kp/Ki/Kd values compiled into the STM32.
- STR rows may carry the actual P/I/D contributions and final controller-domain
  correction calculated by motorTask.
- The plotter therefore does not need hard-coded PID gains for new logs.

Legacy CSVs are still supported. If they do not contain SPID/actual PID terms,
supply --kp and --kd to reconstruct the controller output.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import matplotlib
import pandas as pd

BAND_DEG = 0.2
COUNTS_PER_CM = 73.7


def _finite(value) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def load_runs(path: Path):
    df = pd.read_csv(path)
    if "record_type" not in df.columns:
        raise ValueError(f"{path}: no record_type column")

    # New columns may not exist in old CSVs. Add them as NaN so the same
    # plotting code can handle both generations of files.
    optional = [
        "steer_kp",
        "steer_ki",
        "steer_kd",
        "steer_p_percent",
        "steer_i_percent",
        "steer_d_percent",
        "steer_corr_percent",
    ]
    for name in optional:
        if name not in df.columns:
            df[name] = float("nan")

    cmds = {}
    for _, r in df[df.record_type == "CMD"].iterrows():
        cmds[(r.session_id, r.command_id)] = r.command

    pid_cfg = {}
    for _, r in df[df.record_type == "SPID"].iterrows():
        pid_cfg[(r.session_id, r.command_id)] = {
            "kp": r.steer_kp,
            "ki": r.steer_ki,
            "kd": r.steer_kd,
        }

    str_cols = [
        "stm_tick_ms",
        "yaw_deg",
        "yaw_rate_dps",
        "turn_error_deg",
        "steer_cmd_percent",
        "steer_p_percent",
        "steer_i_percent",
        "steer_d_percent",
        "steer_corr_percent",
    ]
    wpi_cols = [
        "stm_tick_ms",
        "cps_a_f",
        "cps_b_f",
        "wheel_speed_error_cps",
        "wheel_pi_i_acc",
        "wheel_pi_off",
        "drive_percent",
    ]

    missing_wpi = [c for c in wpi_cols if c not in df.columns]
    if missing_wpi:
        raise ValueError(
            f"{path}: missing WPI CSV columns: {', '.join(missing_wpi)}"
        )

    runs = []
    strs = df[df.record_type == "STR"]
    wpis = df[df.record_type == "WPI"]

    for key, s in strs.groupby(["session_id", "command_id"]):
        if key[1] == 0:
            continue

        w = wpis[
            (wpis.session_id == key[0])
            & (wpis.command_id == key[1])
        ]
        if w.empty:
            continue

        # Keep the original session-wide ENC selection because the distance
        # calculation below time-crops it and can include the immediate
        # post-brake roll.
        enc = df[
            (df.record_type == "ENC")
            & (df.session_id == key[0])
        ][["stm_tick_ms", "motor_a_delta", "motor_b_delta"]]

        runs.append(
            {
                "file": path.name,
                "cmd": cmds.get(key, "?"),
                "enc": enc,
                "s": s[str_cols]
                .sort_values("stm_tick_ms")
                .reset_index(drop=True),
                "w": w[wpi_cols]
                .sort_values("stm_tick_ms")
                .reset_index(drop=True),
                "pid": pid_cfg.get(key),
            }
        )

    return runs


def resolve_pid(run, fallback_kp, fallback_ki, fallback_kd):
    cfg = run.get("pid")
    if cfg and all(_finite(cfg[name]) for name in ("kp", "ki", "kd")):
        return (
            float(cfg["kp"]),
            float(cfg["ki"]),
            float(cfg["kd"]),
            "STM32 SPID",
        )

    if fallback_kp is not None and fallback_kd is not None:
        return (
            float(fallback_kp),
            float(fallback_ki) if fallback_ki is not None else float("nan"),
            float(fallback_kd),
            "command line",
        )

    return float("nan"), float("nan"), float("nan"), "unavailable"


def analyse(run, fallback_kp, fallback_ki, fallback_kd):
    s, w = run["s"].copy(), run["w"].copy()

    if s.empty or w.empty:
        raise ValueError("empty STR/WPI data")

    t0 = w.stm_tick_ms.min()
    s["t"] = (s.stm_tick_ms - t0) / 1000.0
    w["t"] = (w.stm_tick_ms - t0) / 1000.0

    ab = w.cps_a_f - w.cps_b_f
    launch_gap = ab[w.t <= 0.7].mean()
    peak_gap = ab[w.t <= 1.0].abs().max()

    early = s[s.t <= 2.0]
    yaw_at_2s = (
        early.yaw_deg.iloc[-1]
        if not early.empty
        else s.yaw_deg.iloc[-1]
    )

    peak = w.drive_percent.max()
    peak_rows = w[w.drive_percent >= peak]
    if peak_rows.empty:
        raise ValueError("cannot determine deceleration start")
    t_dec = float(peak_rows.t.max())

    s["t"] -= t_dec
    w["t"] -= t_dec
    t_last_ctrl = w.t.max()

    kp, ki, kd, gain_source = resolve_pid(
        run, fallback_kp, fallback_ki, fallback_kd
    )

    logged_terms = all(
        s[col].notna().any()
        for col in (
            "steer_p_percent",
            "steer_i_percent",
            "steer_d_percent",
            "steer_corr_percent",
        )
    )

    if logged_terms:
        # These are the actual values calculated by STM32 motorTask.
        s["p"] = s.steer_p_percent
        s["i"] = s.steer_i_percent
        s["d"] = s.steer_d_percent
        s["corr_pct"] = s.steer_corr_percent
        term_source = "STM32 STR"
    else:
        if not (_finite(kp) and _finite(kd)):
            raise ValueError(
                "legacy STR data has no logged P/I/D terms and no PID gains; "
                "use --kp and --kd"
            )

        # Legacy reconstruction. For scripted reverse, physical steering has
        # the same sign as controller correction; forward has the opposite sign.
        command_upper = str(run["cmd"]).upper()
        reverse = command_upper.startswith("REV") or "MAN_REV" in command_upper
        s["corr_pct"] = (
            s.steer_cmd_percent if reverse else -s.steer_cmd_percent
        )
        s["p"] = kp * s.turn_error_deg
        s["d"] = -kd * s.yaw_rate_dps
        s["i"] = s["corr_pct"] - s["p"] - s["d"]
        term_source = "reconstructed"

    # Post-brake STR rows are useful for final yaw, but they are not active
    # controller output. Hide control traces after the last WPI sample.
    post_brake = s.t > t_last_ctrl + 0.02
    s.loc[
        post_brake,
        ["corr_pct", "p", "i", "d"],
    ] = float("nan")

    pre = s[(s.t <= 0) & (s.t > -1.0)]
    post = s[s.t > 0]

    before_decel = s[s.t <= 0]
    if before_decel.empty:
        at0 = float("nan")
        yaw0 = s.yaw_deg.iloc[0]
    else:
        at0 = before_decel.iloc[-3:].turn_error_deg.mean()
        yaw0 = before_decel.yaw_deg.iloc[-1]

    win = s[(s.t > 0) & (s.t <= 0.3)]
    kick = (
        (win.yaw_deg - yaw0).abs().max()
        if len(win)
        else float("nan")
    )

    final_err = s.turn_error_deg.iloc[-1]

    dist_cm = float("nan")
    target_cm = float("nan")
    try:
        target_cm = float(str(run["cmd"]).split(":")[1])
        e = run["enc"]
        e = e[
            (e.stm_tick_ms >= t0 - 50)
            & (
                e.stm_tick_ms
                <= t0 + (s.t.max() + t_dec) * 1000 + 50
            )
        ]
        dist_cm = (
            (e.motor_a_delta.sum() + e.motor_b_delta.sum())
            / 2.0
            / COUNTS_PER_CM
        )
    except (IndexError, ValueError):
        pass

    summary = {
        "file": run["file"],
        "cmd": run["cmd"],
        "Kp": round(kp, 4) if _finite(kp) else float("nan"),
        "Ki": round(ki, 4) if _finite(ki) else float("nan"),
        "Kd": round(kd, 4) if _finite(kd) else float("nan"),
        "gain_source": gain_source,
        "term_source": term_source,
        "decel_start_s": round(t_dec, 2),
        "err_at_decel": round(at0, 3),
        "pre_std": round(pre.turn_error_deg.std(), 3),
        "kick_0.3s": round(kick, 3),
        "max_err_post": round(post.turn_error_deg.abs().max(), 3),
        "final_err": round(final_err, 3),
        "post_steer_abs": round(post.steer_cmd_percent.abs().mean(), 1),
        "overshoot_cm": round(dist_cm - target_cm, 2),
        "launch_gap_cps": round(launch_gap, 0),
        "peak_gap_cps": round(peak_gap, 0),
        "yaw_at_2s": round(yaw_at_2s, 2),
    }
    return s, w, summary


def plot_run(s, w, summary, plt):
    # Six separate panels. No panel contains more than three data traces.
    fig, ax = plt.subplots(6, 1, figsize=(12, 15), sharex=True)

    gain_text = (
        f"Kp={summary['Kp']}  Ki={summary['Ki']}  Kd={summary['Kd']}"
        if _finite(summary["Kp"])
        else "PID gains unavailable"
    )
    title = (
        f"{summary['file']}  {summary['cmd']}  "
        f"({gain_text}; t=0 is decel start)"
    )

    # 1: Heading only.
    ax[0].plot(
        s.t,
        s.turn_error_deg,
        label="heading error",
    )
    ax[0].axhspan(
        -BAND_DEG,
        BAND_DEG,
        alpha=0.12,
        label=f"+/-{BAND_DEG} deg",
    )
    ax[0].axhline(0, linewidth=0.7, linestyle="--")
    ax[0].set_ylabel("error (deg)")
    ax[0].set_title(title)
    ax[0].legend(loc="upper left")

    # 2: Raw PID contributions: exactly three traces.
    ax[1].plot(s.t, s["p"], label="P")
    ax[1].plot(s.t, s["i"], label="I")
    ax[1].plot(s.t, s["d"], label="D")
    ax[1].axhline(0, linewidth=0.5)
    ax[1].set_ylabel("PID term (%)")
    ax[1].set_title(f"Steering PID terms ({summary['term_source']})")
    ax[1].legend(loc="upper left", ncol=3)

    # 3: Final controller output vs actual physical steering request.
    ax[2].plot(
        s.t,
        s["corr_pct"],
        linewidth=1.4,
        label="controller correction",
    )
    ax[2].plot(
        s.t,
        s.steer_cmd_percent,
        linewidth=1.0,
        label="physical steer request",
    )
    ax[2].axhline(0, linewidth=0.5)
    ax[2].set_ylabel("steer (%)")
    ax[2].set_title("Steering output")
    ax[2].legend(loc="upper left")

    # 4: Wheel speed only: two traces.
    ax[3].plot(w.t, w.cps_a_f, label="left cps")
    ax[3].plot(w.t, w.cps_b_f, label="right cps")
    ax[3].set_ylabel("speed (cps)")
    ax[3].set_title("Filtered wheel speed")
    ax[3].legend(loc="upper right")

    # 5: Motion profile only.
    ax[4].plot(w.t, w.drive_percent, label="drive %")
    ax[4].set_ylabel("drive (%)")
    ax[4].set_title("Acceleration / deceleration profile")
    ax[4].legend(loc="upper right")

    # 6: Wheel-balance controller: two traces.
    ax[5].plot(
        w.t,
        w.wheel_speed_error_cps,
        label="wheel speed error",
    )
    ax[5].plot(
        w.t,
        w.wheel_pi_off / 4.0,
        linewidth=0.9,
        label="wheel PI off / 4",
    )
    ax[5].axhline(0, linewidth=0.5)
    ax[5].set_ylabel("cps / scaled off")
    ax[5].set_xlabel("seconds relative to decel start")
    ax[5].set_title("Wheel-speed PI")
    ax[5].legend(loc="upper right")

    for a in ax:
        a.axvline(0, linestyle=":", linewidth=1.2)
        a.grid(True, alpha=0.4)

    fig.tight_layout()
    return fig


def plot_overlay(all_s, labels, plt):
    fig, ax = plt.subplots(figsize=(11, 5))
    for s, lab in zip(all_s, labels):
        ax.plot(s.t, s.turn_error_deg, linewidth=1.1, label=lab)
    ax.axhspan(-BAND_DEG, BAND_DEG, alpha=0.12)
    ax.axhline(0, linewidth=0.7, linestyle="--")
    ax.axvline(0, linestyle=":", linewidth=1.2)
    ax.set_xlabel("seconds relative to decel start")
    ax.set_ylabel("heading error (deg)")
    ax.set_title("Heading error aligned on decel start")
    ax.grid(True, alpha=0.4)
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    return fig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", nargs="+")
    ap.add_argument(
        "--kp",
        type=float,
        default=None,
        help="legacy CSV fallback only; new logs read Kp from SPID",
    )
    ap.add_argument(
        "--ki",
        type=float,
        default=None,
        help="legacy CSV display fallback only",
    )
    ap.add_argument(
        "--kd",
        type=float,
        default=None,
        help="legacy CSV fallback only; new logs read Kd from SPID",
    )
    ap.add_argument("--overlay", action="store_true")
    ap.add_argument(
        "--save",
        metavar="DIR",
        help="write PNGs here instead of opening windows",
    )
    args = ap.parse_args()

    if args.save:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rows = []
    all_s = []
    labels = []
    figs = []

    for name in args.csv:
        try:
            runs = load_runs(Path(name))
        except Exception as exc:  # noqa: BLE001
            print(f"skip {name}: {exc}")
            continue

        for run in runs:
            try:
                s, w, summ = analyse(
                    run,
                    args.kp,
                    args.ki,
                    args.kd,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"skip {name} {run['cmd']}: {exc}")
                continue

            rows.append(summ)
            all_s.append(s)
            labels.append(
                f"{Path(name).stem[-6:]} {summ['cmd']}"
            )
            figs.append(
                (
                    f"{Path(name).stem}_"
                    f"{str(summ['cmd']).replace(':', '')}.png",
                    plot_run(s, w, summ, plt),
                )
            )

    if not rows:
        print("no usable runs")
        sys.exit(1)

    table = pd.DataFrame(rows)
    pd.set_option("display.width", 240)
    print(table.to_string(index=False))

    print(
        "\nmean |err_at_decel| = %.3f   "
        "mean |final_err| = %.3f   "
        "mean kick = %.3f"
        % (
            table.err_at_decel.abs().mean(),
            table.final_err.abs().mean(),
            table["kick_0.3s"].mean(),
        )
    )

    if args.overlay:
        figs.append(
            (
                "overlay.png",
                plot_overlay(all_s, labels, plt),
            )
        )

    if args.save:
        out = Path(args.save)
        out.mkdir(parents=True, exist_ok=True)
        for fname, fig in figs:
            fig.savefig(out / fname, dpi=110)
        table.to_csv(out / "summary.csv", index=False)
        print(
            f"saved {len(figs)} figures + summary.csv to {out}"
        )
    else:
        plt.show()


if __name__ == "__main__":
    main()
