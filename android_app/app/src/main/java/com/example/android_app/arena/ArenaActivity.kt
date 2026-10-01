package com.example.android_app.arena

import android.os.Bundle
import android.text.format.DateFormat
import android.util.Log
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import android.view.View
import android.widget.ScrollView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.example.android_app.R
import com.example.android_app.bluetooth.BluetoothService
import com.example.android_app.bluetooth.Protocol
import com.example.android_app.others.setupConnectionStatusBar
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class ArenaActivity : AppCompatActivity() {

    private lateinit var arena: ArenaView
    private lateinit var status: TextView
    private lateinit var statusScroll: ScrollView // for auto scrolling of status log
    private lateinit var btnCalculate: Button
    private lateinit var btnStart: Button

    var compiledObstacles = mutableListOf<Obstacle>()

    // Calculate/Start state. PATHREADY carries no id, so only one CALCULATE
    // is allowed in flight at a time to know which calculation it answers.
    private var calcInFlight = false  // CALCULATE sent, PATHREADY not received yet
    private var awaitingPath = false  // in-flight result is still wanted (no edits/reset since)
    private var pathArmed = false     // latest path is ready and matches the arena
    // BEGIN sent. The RPi then ignores CALCULATE and a second BEGIN would restart
    // it from segment 1, so both buttons stay locked until the link drops
    // (restarting task1.py drops it). If the link only blipped, the RPi still
    // ignores CALCULATE, so no PATHREADY comes back and Start can't re-arm.
    private var runStarted = false
    private var calcTimeoutJob: Job? = null

    companion object {
        private const val TAG = "ArenaActivity12345"
        // Give up waiting for PATHREADY after this long (should exceed the PC's slowest path calculation)
        private const val CALC_TIMEOUT_MS = 30_000L
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_arena)
        setupConnectionStatusBar()

        arena = findViewById(R.id.arenaView)
        status = findViewById(R.id.statusText)
        statusScroll = findViewById(R.id.statusScroll)
        btnCalculate = findViewById(R.id.btnCalculate)
        btnStart = findViewById(R.id.btnStart)

        wireArenaCallbacks()
        wireControls()
        updateRunButtons()
        observeMessages()
        observeConnection()

        appendStatus(getString(R.string.status_ready))
    }

    private fun wireArenaCallbacks() {
        arena.onObstaclePlaced = { obs ->
            Log.d(TAG, "Callback [onObstaclePlaced]")
            // BluetoothService.send(Protocol.obstacle(obs.id, obs.cellX, obs.cellY))
            appendStatus("Placed obstacle ${obs.id} at (${obs.cellX},${obs.cellY})")
            invalidatePath()
        }

        /*arena.onObstacleMoved = { obs ->
            BluetoothService.send(Protocol.obstacle(obs.id, obs.cellX, obs.cellY))
            appendStatus("Moved obstacle ${obs.id} to (${obs.cellX},${obs.cellY})")
        }*/
        arena.onObstacleDropped = { obs ->
            Log.d(TAG, "Callback [onObstacleDropped]")
            // BluetoothService.send(Protocol.obstacle(obs.id, obs.cellX, obs.cellY))
            addToCompiled(obs, "dropped")
            appendStatus("Dropped obstacle ${obs.id} at (${obs.cellX},${obs.cellY})")
            invalidatePath()
        }
        arena.onObstacleRemoved = { obs ->
            Log.d(TAG, "Callback [onObstacleRemoved]")
            // BluetoothService.send(Protocol.obstacleDeleted(obs.id, obs.cellX, obs.cellY))
            addToCompiled(obs, "remove")
            appendStatus("Removed obstacle ${obs.id}")
            invalidatePath()
        }
        arena.onObstacleLongPress = { obs ->
            Log.d(TAG, "Callback [onObstacleLongPress]")
            showFaceDialog(obs)
        }

        // new btn to send compiled list of obstacles
    }

    private fun addToCompiled(obs: Obstacle, instruction: String) {
        if (instruction == "longPress" || instruction == "dropped") {
            // add or update obstacle in compiled list
            compiledObstacles.removeAll { it.id == obs.id }
            compiledObstacles.add(obs)

            /* if order of obstacles matter:
                val index = compiledObstacles.indexOfFirst { it.id == obs.id }
                if (index >= 0) compiledObstacles[index] = obs else compiledObstacles.add(obs)
             */
        } else if (instruction == "remove") {
            // remove obstacle from list
            compiledObstacles.removeAll { it.id == obs.id }
        }
    }

    private fun wireControls() {
        findViewById<Button>(R.id.btnForward).setOnClickListener {
            sendMove(Protocol.MoveCmd.FORWARD, "Forward")
        }
        findViewById<Button>(R.id.btnBackward).setOnClickListener {
            sendMove(Protocol.MoveCmd.BACKWARD, "Backward")
        }
        findViewById<Button>(R.id.btnLeft).setOnClickListener {
            sendMove(Protocol.MoveCmd.LEFT, "Turn left")
        }
        findViewById<Button>(R.id.btnRight).setOnClickListener {
            sendMove(Protocol.MoveCmd.RIGHT, "Turn right")
        }
        findViewById<Button>(R.id.btnStop).setOnClickListener {
            sendMove(Protocol.MoveCmd.STOP, "Stop")
        }
        // Calculate: send the obstacle list, then ask the RPi to compute a path.
        // The RPi replies PATHREADY when done (see handleInbound).
        btnCalculate.setOnClickListener {
            // isEnabled alone doesn't stop a queued double tap
            if (calcInFlight || runStarted) return@setOnClickListener
            // The old path is being replaced, so Start waits for the new PATHREADY
            pathArmed = false
            // all{} stops at the first failed send (i.e. not connected)
            val sent = compiledObstacles.all { obs -> sendObstacle(obs) } &&
                    BluetoothService.send(Protocol.calc())

            if (sent) {
                Log.d(TAG, "Obstacles sent (${compiledObstacles.size}): " +
                        compiledObstacles.joinToString { "id=${it.id} (${it.cellX},${it.cellY}) face=${it.face}" })
                calcInFlight = true
                awaitingPath = true
                startCalcTimeout()
                appendStatus("Sent ${compiledObstacles.size} obstacle(s), calculating path...")
            } else {
                awaitingPath = false
                appendStatus("CALCULATE failed — not connected")
            }
            updateRunButtons()
        }
        // Start: tell the RPi to run the calculated path
        btnStart.setOnClickListener {
            // isEnabled alone doesn't stop a queued double tap
            if (!pathArmed || runStarted) return@setOnClickListener
            if (BluetoothService.send(Protocol.start())) {
                runStarted = true
                pathArmed = false
                appendStatus("Sent START — for another run, restart task1.py and reconnect")
            } else {
                appendStatus("START failed — not connected")
            }
            updateRunButtons()
        }
        findViewById<Button>(R.id.btnReset).setOnClickListener {
            arena.reset()
            compiledObstacles.clear()
            // An in-flight calculation still answers later, so calcInFlight stays set
            awaitingPath = false
            pathArmed = false
            updateRunButtons()

            if (BluetoothService.send(Protocol.reset())) {
                appendStatus("Arena reset")
            } else {
                appendStatus("RESET failed - not connected")
            }
        }
    }

    private fun sendObstacle(obs: Obstacle): Boolean {
        val face = obs.face
        return if (face != null) {
            BluetoothService.send(Protocol.face(obs.id, obs.cellX, obs.cellY, face))
        } else {
            BluetoothService.send(Protocol.obstacle(obs.id, obs.cellX, obs.cellY))
        }
    }

    private fun updateRunButtons() {
        btnCalculate.isEnabled = !calcInFlight && !runStarted
        btnStart.isEnabled = pathArmed && !runStarted
    }

    private fun recalcHint(): String =
        if (calcInFlight) "press Calculate again once the current calculation finishes"
        else "press Calculate again"

    /** Obstacles changed since the last Calculate, so the RPi's path is stale. */
    private fun invalidatePath() {
        if (awaitingPath || pathArmed) {
            awaitingPath = false
            pathArmed = false
            updateRunButtons()
            appendStatus("Obstacles changed — ${recalcHint()}")
        }
    }

    /**
     * Link dropped. The RPi re-accepts the tablet on the same task1.py process, so a
     * calculation in flight can still answer later: calcInFlight is kept (PATHREADY or
     * the timeout clears it). A path armed before the drop isn't trusted anymore.
     */
    private fun onLinkLost() {
        if (awaitingPath || pathArmed || runStarted) {
            val wasStarted = runStarted
            awaitingPath = false
            pathArmed = false
            runStarted = false
            updateRunButtons()
            if (wasStarted) {
                appendStatus("Connection lost after START — restart task1.py before the next Calculate")
            } else {
                appendStatus("Connection lost — after reconnecting, ${recalcHint()}")
            }
        }
    }

    /** Release the Calculate lock if PATHREADY never comes (e.g. PC down, run already started). */
    private fun startCalcTimeout() {
        calcTimeoutJob?.cancel()
        calcTimeoutJob = lifecycleScope.launch {
            delay(CALC_TIMEOUT_MS)
            if (calcInFlight) {
                calcInFlight = false
                awaitingPath = false
                updateRunButtons()
                appendStatus("No path from RPi after ${CALC_TIMEOUT_MS / 1000}s — check task1.py/PC " +
                        "(restart task1.py if a run already started), then press Calculate")
            }
        }
    }

    private fun sendMove(cmd: Protocol.MoveCmd, label: String) {
        if (BluetoothService.send(Protocol.move(cmd))) {
            appendStatus(label)
            // Local optimistic pose update so students can demo without hardware:
            when (cmd) {
                Protocol.MoveCmd.LEFT ->
                    arena.setRobot(arena.robot.cellX, arena.robot.cellY, arena.robot.facing.turnLeft())
                Protocol.MoveCmd.RIGHT ->
                    arena.setRobot(arena.robot.cellX, arena.robot.cellY, arena.robot.facing.turnRight())
                else -> Unit
            }
        } else {
            appendStatus("$label failed — not connected")
        }
    }

    private fun showFaceDialog(obs: Obstacle) {
        val labels = arrayOf(
            getString(R.string.face_north),
            getString(R.string.face_east),
            getString(R.string.face_south),
            getString(R.string.face_west),
            getString(R.string.face_none),
        )
        AlertDialog.Builder(this)
            .setTitle(getString(R.string.label_face_dialog, obs.id))
            .setItems(labels) { _, which ->
                val face = when (which) {
                    0 -> Facing.NORTH
                    1 -> Facing.EAST
                    2 -> Facing.SOUTH
                    3 -> Facing.WEST
                    else -> null
                }
                arena.setObstacleFace(obs.id, face)
                if (face != null) {
                    // BluetoothService.send(Protocol.obstacle(obs.id, obs.cellX, obs.cellY))
                    // BluetoothService.send(Protocol.face(obs.id, obs.cellX, obs.cellY, face))
                    addToCompiled(obs, "longPress")
                    appendStatus("Obstacle ${obs.id} face -> ${face.value}")
                    Log.d(TAG, "Protocol.face(obs.id, face")
                } else {
                    appendStatus("Obstacle ${obs.id} face cleared")
                }
                invalidatePath()
            }
            .show()
    }

    private fun handleInbound(line: String) {
        when (val msg = Protocol.parse(line)) {
            is Protocol.Inbound.Target -> {
                arena.setTargetId(msg.obstacleId, msg.targetId)
                appendStatus("Obstacle ${msg.obstacleId} -> target ${msg.targetId}")
            }
            is Protocol.Inbound.Robot -> {
                arena.setRobot(msg.x, msg.y, msg.facing)
                // C.4 note: selective log — pose updates are important events,
                // not every raw stream byte.
                appendStatus("Robot @ (${msg.x},${msg.y}) ${msg.facing.value}")
            }
            is Protocol.Inbound.Ready -> {
                calcInFlight = false
                calcTimeoutJob?.cancel()
                if (awaitingPath && !runStarted) {
                    pathArmed = true
                    appendStatus("Path calculation ready! Press Start to run")
                } else {
                    // e.g. obstacles were edited or Reset pressed while calculating
                    appendStatus("Path ready for outdated obstacles — press Calculate again")
                }
                awaitingPath = false
                updateRunButtons()
            }
            is Protocol.Inbound.Unknown -> {
                // Deliberately NOT logged to the visible status — checklist
                // C.4 says the TextView should show selective info only.

                appendStatus("RPi sent ${msg}")
            }
        }
    }

    private fun appendStatus(msg: String) {
        val time = DateFormat.format("HH:mm:ss", System.currentTimeMillis())
        val current = status.text?.toString().orEmpty()
        val trimmed = if (current.length > 4000) current.takeLast(2000) else current
        val line = "[$time] $msg"
        status.text = if (trimmed.isEmpty()) line else "$trimmed\n$line"

        statusScroll.post {
            statusScroll.smoothScrollTo(0, status.bottom)
        }
    }

    private fun observeMessages() {
        lifecycleScope.launch {
            // CREATED (not STARTED) so a PATHREADY arriving while the app is in the
            // background isn't dropped (messages has no replay) and Start can't get stuck
            repeatOnLifecycle(Lifecycle.State.CREATED) {
                BluetoothService.messages.collect { line ->
                    handleInbound(line)
                }
            }
        }
    }

    private fun observeConnection() {
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.CREATED) {
                BluetoothService.state.collect { state ->
                    if (state != BluetoothService.State.CONNECTED) onLinkLost()
                }
            }
        }
    }
}