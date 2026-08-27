package com.example.android_app.arena

import android.os.Bundle
import android.text.format.DateFormat
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import com.example.android_app.R
import com.example.android_app.bluetooth.BluetoothService
import com.example.android_app.bluetooth.Protocol
import kotlinx.coroutines.launch

class ArenaActivity : AppCompatActivity() {

    private lateinit var arena: ArenaView
    private lateinit var status: TextView
    private lateinit var connectionBadge: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_arena)

        arena = findViewById(R.id.arenaView)
        status = findViewById(R.id.statusText)
        connectionBadge = findViewById(R.id.connectionBadge)

        wireArenaCallbacks()
        wireControls()
        observeService()

        appendStatus(getString(R.string.status_ready))
    }

    private fun wireArenaCallbacks() {
        arena.onObstaclePlaced = { obs ->
            BluetoothService.send(Protocol.obstacle(obs.id, obs.cellX, obs.cellY))
            appendStatus("Placed obstacle ${obs.id} at (${obs.cellX},${obs.cellY})")
        }
        arena.onObstacleMoved = { obs ->
            BluetoothService.send(Protocol.obstacle(obs.id, obs.cellX, obs.cellY))
            appendStatus("Moved obstacle ${obs.id} to (${obs.cellX},${obs.cellY})")
        }
        arena.onObstacleRemoved = { obs ->
            BluetoothService.send(Protocol.obstacleDeleted(obs.id))
            appendStatus("Removed obstacle ${obs.id}")
        }
        arena.onObstacleLongPress = { obs ->
            showFaceDialog(obs)
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
        findViewById<Button>(R.id.btnStart).setOnClickListener {
            if (BluetoothService.send(Protocol.start())) {
                appendStatus("Sent START")
            } else {
                appendStatus("START failed — not connected")
            }
        }
        findViewById<Button>(R.id.btnReset).setOnClickListener {
            arena.reset()
            appendStatus("Arena reset")
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
                    BluetoothService.send(Protocol.face(obs.id, face))
                    appendStatus("Obstacle ${obs.id} face -> ${face.code}")
                } else {
                    appendStatus("Obstacle ${obs.id} face cleared")
                }
            }
            .show()
    }

    private fun observeService() {
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                launch {
                    BluetoothService.state.collect { state ->
                        val name = BluetoothService.connectedDevice.value
                        connectionBadge.text = when (state) {
                            BluetoothService.State.DISCONNECTED ->
                                getString(R.string.status_disconnected)
                            BluetoothService.State.CONNECTING ->
                                getString(R.string.status_connecting)
                            BluetoothService.State.CONNECTED ->
                                getString(R.string.status_connected, name ?: "device")
                            BluetoothService.State.RECONNECTING ->
                                getString(R.string.status_reconnecting)
                        }
                    }
                }
                launch {
                    BluetoothService.messages.collect { line ->
                        handleInbound(line)
                    }
                }
            }
        }
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
                appendStatus("Robot @ (${msg.x},${msg.y}) ${msg.facing.code}")
            }
            is Protocol.Inbound.Unknown -> {
                // Deliberately NOT logged to the visible status — checklist
                // C.4 says the TextView should show selective info only.
            }
        }
    }

    private fun appendStatus(msg: String) {
        val time = DateFormat.format("HH:mm:ss", System.currentTimeMillis())
        val current = status.text?.toString().orEmpty()
        val trimmed = if (current.length > 4000) current.takeLast(2000) else current
        val line = "[$time] $msg"
        status.text = if (trimmed.isEmpty()) line else "$trimmed\n$line"
    }
}
