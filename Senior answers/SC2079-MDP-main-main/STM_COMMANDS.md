# STM32 Command Reference

Commands are sent from **RPi → STM32** over serial UART.  
The STM Rx callback **automatically lowercases** all input, so case does not matter when sending.

## Wire Format

```
<cmd1>,<cmd2>,...,<cmdN>\n
```

- Commands in a single line are **comma-separated** (or space-separated — both work)
- The line is **newline-terminated** (`\n`)
- One `OK` reply is sent per **line** (not per command), after the entire sequence finishes
- Example: `FR90,F20,S\n`

---

## Checklist / Task 1 Commands

> These are the commands supported by `stm_hardware/checklist/` and `stm_hardware/task1/`

| Token     | Description                                      |
|-----------|--------------------------------------------------|
| `F{n}`    | Forward `n` cm (e.g. `F20` = forward 20 cm)     |
| `F0`      | Forward forever until ultrasound triggers stop   |
| `R{n}`    | Reverse `n` cm (e.g. `R15`)                     |
| `FR{n}`   | Arc forward-right `n` degrees (e.g. `FR90`)      |
| `FL{n}`   | Arc forward-left `n` degrees  (e.g. `FL90`)      |
| `RR{n}`   | Arc reverse-right `n` degrees (e.g. `RR90`)      |
| `RL{n}`   | Arc reverse-left `n` degrees  (e.g. `RL90`)      |
| `S`       | **Stop** — motor brake + servo center            |
| `RST`     | Emergency abort — drops queue and brakes immediately |

---

## Task 2 Additional Commands

> These are **only** supported by `stm_hardware/task2/`. Not available in checklist firmware.

| Token     | Description                                                    |
|-----------|----------------------------------------------------------------|
| `FU{n}`   | Forward until ultrasound reads ≤ `n` cm (e.g. `FU26`)         |
| `FIR`     | Forward until **right** IR detects wall gone (obstacle → none) |
| `FIL`     | Forward until **left** IR detects wall gone                    |
| `FIRO`    | Forward until **right** IR detects wall present (none → obstacle) |
| `FILO`    | Forward until **left** IR detects wall present                 |
| `SR`      | Slide right (diagonal S-curve)                                 |
| `SL`      | Slide left  (diagonal S-curve)                                 |

---

## STM → RPi Replies

| Message          | When sent                                                    |
|------------------|--------------------------------------------------------------|
| `OK\n`           | End of command line fully executed (all commands done)       |
| `RESEND\n`       | Error detected — RPi should retransmit the last segment      |
| `ir{dist}\n`     | *(Task 2 only)* IR distance reading in cm                    |
| `us{d1},{d2}\n`  | *(Task 2 only)* Ultrasound: travelled dist, stop dist (cm)   |

---

## How RPi Segments Map to STM Lines

`PC/Checklist.py` converts algo-layer commands into STM tokens before sending:

| Algo command | STM token sent  |
|--------------|-----------------|
| `FW{n}`      | `F{n}`          |
| `BW{n}`      | `R{n}`          |
| `FL{n}`      | `FL{n}`         |
| `FR{n}`      | `FR{n}`         |
| `BL{n}`      | `RL90`          |
| `BR{n}`      | `RR90`          |
| `FIN`        | `S`             |
| `SNAP...`    | *(segment break — not sent to STM)* |

Each segment (list of tokens) is joined with commas and sent as one line:
```python
cmd = ",".join(segment) + "\n"
stm.send(cmd)
# e.g. "FR90,F20,S\n"
```

---

## Notes for Checklist Development

- The team is currently focused on **`stm_hardware/checklist/`**, which uses the same command set as Task 1.
- `RST` is an **immediate** hardware abort — it does not send `OK`. Use only in emergencies.
- `S` brakes the motors and recenters the servo. It **does** trigger `OK` as part of normal sequence end.
- To stop the robot from the PC side, send `S` as a one-command line: `"S\n"`.
- The checklist firmware does **not** have `FU`, `FIR`, `FIL`, `SR`, `SL` — those are Task 2 only.
