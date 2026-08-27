# Component Communication Reference

## Overview

```
Android Tablet
    │  Bluetooth RFCOMM (channel 1, SPP)
    ▼
Raspberry Pi ──── Serial UART ────► STM32
    │  TCP socket (RPi is server, port 5000)
    ▼
PC (Windows)
    ▲
    │  TCP socket (RPi is server, separate STREAM_PORT)
    └──────────────── Camera Stream
```

---

## 1. Android ↔ RPi — Bluetooth RFCOMM

**Android → RPi**
```
OBSTACLE,2,50,160,NORTH     # id=2, x=50mm÷10=5, y=160mm÷10=16, facing North
OBSTACLE,1,80,100,EAST
CLEAR                        # wipe obstacle list
PATH                         # trigger: RPi forwards obstacles to PC
BEGIN                        # start executing path on STM
```

**RPi → Android**
```
TARGET,2,23                  # obstacle 2 matched image class 23
```

---

## 2. RPi ↔ PC — TCP Socket
> RPi is the **server**. PC connects to RPi on `RPI_HOST:RPI_PORT`.

**RPi → PC**
```
OBSTACLES,[{"id":1,"x":5.0,"y":10.0,"d":0},{"id":2,"x":8.0,"y":5.0,"d":4}]

DETECT,1                     # robot just photographed obstacle 1, what did you see?

STITCH,3                     # all 3 obstacles visited, build final image collage
```

**PC → RPi**
```
PATH,{"segments":[["FR90","F20"],["FL90","F15","S"]],"obstacle_ids":["1","2"],"dirs":[...]}

OBJECT,1,0.9521,23           # obstacle 1 matched image class 23, confidence 0.95

STITCH                       # (checklist) trigger stitch immediately
```

---

## 3. RPi ↔ STM32 — Serial UART

> Commands are **comma-separated**, **newline-terminated**.  
> STM automatically **lowercases** all input so casing does not matter.  
> One `OK` is returned per **line** (not per command).

**RPi → STM**
```
FR90,F20,S\n                 # turn right 90°, forward 20 cm, stop
FL90,F15,FR90,F10,S\n        # sequence of moves in one segment
F0\n                         # forward until ultrasound triggers
RST\n                        # emergency abort, immediate brake, no OK reply
```

**STM → RPi**
```
OK\n                         # entire line finished, ready for next segment
RESEND\n                     # error — RPi should retransmit the last line
```

---

## 4. RPi ↔ PC — Camera Stream (separate socket)
> RPi is the **server** on `RPI_HOST:STREAM_PORT`.  
> Each frame is prefixed with a **4-byte big-endian length**, followed by raw JPEG bytes.

**PC → RPi**
```
stream_request\n             # start sending frames
STOP\n                       # stop stream
PING\n                       # keepalive
```

**RPi → PC**
```
OK STREAMING\n               # stream started
PONG\n                       # keepalive reply

[4-byte length][JPEG bytes]  # one frame (repeated continuously)
[4-byte length][JPEG bytes]
...
```

---

## Full Checklist Flow

```
Android          RPi              PC (Checklist.py)     STM32
   |                |                |                     |
   |--OBSTACLE,1,-->|                |                     |
   |--OBSTACLE,2,-->|                |                     |
   |----BEGIN------>|                |                     |
   |                |--OBSTACLES,[]->|                     |
   |                |<--PATH,{...}---|                     |
   |                |--FR90,F20,S\n------------------->    |
   |                |<------------------------------OK\n---|
   |                |--DETECT,1----->|                     |
   |                |<--OBJECT,1,0.95,23                   |
   |                |--FL90,F10,S\n------------------->    |
   |                |<------------------------------OK\n---|
   |                |--STITCH,2----->|                     |
   |<--TARGET,1,23--|                |                     |
```

---

## Message Field Reference

### OBSTACLE (Android → RPi)
| Field | Example | Notes |
|-------|---------|-------|
| id | `2` | Obstacle number |
| x | `50` | x position in mm (RPi divides by 10 → grid unit) |
| y | `160` | y position in mm |
| direction | `NORTH` | Face direction: `NORTH`, `EAST`, `SOUTH`, `WEST`, `SKIP` |

### PATH segments (PC → RPi)
| Field | Example | Notes |
|-------|---------|-------|
| segments | `[["FR90","F20"],["S"]]` | Each inner list = one STM line |
| obstacle_ids | `["1","2"]` | Obstacle to detect after each segment |
| dirs | `[{"d":"NORTH","x":1,"y":1}]` | Robot direction after each move |

### OBJECT (PC → RPi)
| Field | Example | Notes |
|-------|---------|-------|
| obstacle_id | `1` | Which obstacle was photographed |
| confidence | `0.9521` | YOLOv8 confidence score (0–1) |
| image_id | `23` | Detected class ID (see `PC/classes.py`) |
