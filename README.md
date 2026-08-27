# SC2079-Group-28

NTU MDP (Multi-disciplinary Design Project) — Group 28.

## Part C — Android Remote Controller

The Android tablet module lives in [`android_app/`](./android_app). All 10
checklist items (C.1–C.10) from the MDP assessment brief are covered.

### Build

Open `android_app/` in **Android Studio Ladybug (or newer)**. Sync Gradle,
then run on a real tablet (or emulator if you only need to demo the UI —
Bluetooth needs a real device).

- Gradle 8.10.2 · AGP 8.7.3 · Kotlin 2.0.21
- `compileSdk = 35`, `minSdk = 24`, `targetSdk = 34`

### Checklist coverage → source map

| Item | What the spec asks                                        | File(s)                                                                                   | Demo path |
|------|-----------------------------------------------------------|-------------------------------------------------------------------------------------------|-----------|
| C.1  | Bi-directional text over RFCOMM                            | `bluetooth/BluetoothService.kt` (send, messages flow)                                    | Bluetooth screen → connect → type in send box → confirm inbound log fills |
| C.2  | Scan/select/connect to a Bluetooth device                  | `bluetooth/BluetoothActivity.kt`, `DeviceListAdapter.kt`                                 | Bluetooth screen → tap **Scan** → tap a device in either list |
| C.3  | Labelled buttons for robot movement (no text-command box) | `arena/ArenaActivity.kt` (`wireControls`), dpad in `res/layout/activity_arena.xml`       | Arena screen → tap ▲ ▼ ◀ ▶ ■ — sends `ROBOT_MOVE,<F/B/L/R/S>` |
| C.4  | Selective status TextView                                  | `arena/ArenaActivity.kt` (`appendStatus`, `handleInbound`)                                | Arena screen → status pane on right — only parsed events, not raw byte stream |
| C.5  | 2D arena, numbered obstacles, robot with facing            | `arena/ArenaView.kt` (draw pipeline)                                                     | Arena screen — 20×20 grid, start-zone highlighted, robot triangle points to facing |
| C.6  | Touch-place / drag-move / drag-off-map delete              | `arena/ArenaView.kt` (`onTouchEvent`), callbacks wired in `ArenaActivity.wireArenaCallbacks` | Tap empty cell → obstacle appears (auto-numbered); drag it; drag outside grid → removed; each event sends `OBSTACLE,...` / `OBSTACLE_DEL,...` |
| C.7  | Interactive face annotation on obstacles                   | `ArenaView.onObstacleLongPress` → `ArenaActivity.showFaceDialog`                          | Long-press an obstacle → pick N/E/S/W → coloured strip appears on that side, `FACE,<num>,<dir>` sent |
| C.8  | Robust auto-reconnect after disconnect                     | `bluetooth/BluetoothService.kt` (`scheduleReconnect`, RECONNECTING state)                 | While connected, disable RPi Bluetooth briefly → app shows "Reconnecting…" then reconnects automatically |
| C.9  | Display Target ID from `TARGET,<obs>,<id>`                 | `bluetooth/Protocol.kt` (`parse`), `arena/ArenaView.setTargetId`                          | With connection established, RPi sends `TARGET,4,11` → obstacle 4 relabels to `11` and switches colour |
| C.10 | Update robot pose from `ROBOT,<x>,<y>,<dir>`               | `bluetooth/Protocol.kt` (`parse`), `arena/ArenaView.setRobot`                            | RPi sends `ROBOT,5,7,E` → robot moves to (5,7) facing East |

### Wire protocol

Inbound (from RPi, exactly as specified by the checklist):

```
TARGET,<obstacle_num>,<target_id>
ROBOT,<x>,<y>,<N|S|E|W>
```

Outbound (Group 28 convention — RPi/Algo team should decode these):

```
OBSTACLE,<num>,<x>,<y>          # placed or moved
OBSTACLE_DEL,<num>              # dragged off the arena
FACE,<num>,<N|S|E|W>            # target face annotated
ROBOT_MOVE,<F|B|L|R|S>          # manual dpad
START                           # user pressed Start
```

All lines are `\n`-terminated UTF-8.

### Local unit tests

`ProtocolTest.kt` covers the parser and formatter. Run under Android Studio
with **Right-click `app/src/test` → Run Tests**, or from CLI once the
Android SDK is set up:

```bash
cd android_app
./gradlew :app:testDebugUnitTest
```

### Runtime layout

- `MainActivity` — landing screen with Connect / Start buttons
- `BluetoothActivity` — device scan + connect + send/receive test panel
- `ArenaActivity` — the working screen: 20×20 arena + dpad + status log
- `BluetoothService` — process-wide singleton holding the RFCOMM socket
  and exposing state / messages as coroutine `Flow`s
