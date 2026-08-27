package com.example.android_app.bluetooth

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothSocket
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStream
import java.util.UUID

/**
 * Process-wide Bluetooth RFCOMM connection.
 *
 * Checklist:
 *   C.1  bi-directional text over RFCOMM (send / messages)
 *   C.8  automatic reconnect after temporary disconnect (auto-retry loop
 *        whenever a device address is remembered)
 *
 * All I/O happens on Dispatchers.IO. Callers observe [state] and [messages]
 * from the main thread.
 */
object BluetoothService {

    private const val TAG = "BluetoothService"
    // Standard SPP UUID used by RPi rfcomm channels
    private val SPP_UUID: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
    private const val RECONNECT_DELAY_MS = 2500L

    enum class State { DISCONNECTED, CONNECTING, CONNECTED, RECONNECTING }

    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var readerJob: Job? = null
    private var reconnectJob: Job? = null

    private var socket: BluetoothSocket? = null
    private var output: OutputStream? = null

    private var pendingDeviceAddress: String? = null

    private val _state = MutableStateFlow(State.DISCONNECTED)
    val state: StateFlow<State> = _state.asStateFlow()

    private val _connectedDevice = MutableStateFlow<String?>(null)
    val connectedDevice: StateFlow<String?> = _connectedDevice.asStateFlow()

    // Every line received from the remote peer, in order.
    private val _messages = MutableSharedFlow<String>(
        replay = 0,
        extraBufferCapacity = 256
    )
    val messages: SharedFlow<String> = _messages.asSharedFlow()

    /**
     * Connect to [device]. Any current connection is closed first.
     * Remembers the address so we can auto-reconnect on disconnect (C.8).
     */
    @SuppressLint("MissingPermission")
    fun connect(device: BluetoothDevice) {
        pendingDeviceAddress = device.address
        reconnectJob?.cancel()
        reconnectJob = null
        scope.launch { doConnect(device) }
    }

    @SuppressLint("MissingPermission")
    private suspend fun doConnect(device: BluetoothDevice) = withContext(Dispatchers.IO) {
        closeSocket()
        _state.value = State.CONNECTING
        try {
            // Cancel discovery before creating a socket — required by the SDK
            // for reliable connection setup.
            BluetoothAdapter.getDefaultAdapter()?.cancelDiscovery()
            val sock = device.createRfcommSocketToServiceRecord(SPP_UUID)
            sock.connect()
            socket = sock
            output = sock.outputStream
            _connectedDevice.value = safeName(device)
            _state.value = State.CONNECTED
            startReader(sock)
        } catch (t: Throwable) {
            Log.w(TAG, "connect failed: ${t.message}")
            closeSocket()
            scheduleReconnect()
        }
    }

    private fun startReader(sock: BluetoothSocket) {
        readerJob?.cancel()
        readerJob = scope.launch(Dispatchers.IO) {
            val reader = BufferedReader(InputStreamReader(sock.inputStream))
            try {
                while (isActive) {
                    val line = reader.readLine() ?: break
                    if (line.isNotEmpty()) {
                        _messages.emit(line)
                    }
                }
            } catch (t: Throwable) {
                Log.w(TAG, "reader ended: ${t.message}")
            } finally {
                // Only trigger a drop if we're still the active reader.
                // If a new connect superseded us, `socket` no longer points at
                // our sock and the new flow owns lifecycle from here on.
                if (socket === sock) {
                    onSocketDropped()
                }
            }
        }
    }

    private fun onSocketDropped() {
        closeSocket()
        if (pendingDeviceAddress != null) {
            scheduleReconnect()
        } else {
            _state.value = State.DISCONNECTED
        }
    }

    @SuppressLint("MissingPermission")
    private fun scheduleReconnect() {
        val address = pendingDeviceAddress ?: run {
            _state.value = State.DISCONNECTED
            return
        }
        if (reconnectJob?.isActive == true) return
        _state.value = State.RECONNECTING
        reconnectJob = scope.launch {
            while (isActive && _state.value != State.CONNECTED) {
                delay(RECONNECT_DELAY_MS)
                val adapter = BluetoothAdapter.getDefaultAdapter() ?: return@launch
                val device = try {
                    adapter.getRemoteDevice(address)
                } catch (t: Throwable) {
                    Log.w(TAG, "getRemoteDevice failed: ${t.message}")
                    null
                } ?: continue
                doConnect(device)
            }
        }
    }

    /**
     * Send a line of text. A trailing '\n' is added if absent.
     * Returns false on write failure — the connection is then flipped into
     * RECONNECTING and the caller can log to the status view.
     */
    fun send(text: String): Boolean {
        val payload = if (text.endsWith("\n")) text else "$text\n"
        val out = output ?: return false
        return try {
            out.write(payload.toByteArray(Charsets.UTF_8))
            out.flush()
            true
        } catch (t: Throwable) {
            Log.w(TAG, "send failed: ${t.message}")
            onSocketDropped()
            false
        }
    }

    fun disconnect() {
        pendingDeviceAddress = null
        reconnectJob?.cancel()
        reconnectJob = null
        readerJob?.cancel()
        readerJob = null
        closeSocket()
        _state.value = State.DISCONNECTED
    }

    private fun closeSocket() {
        try { output?.close() } catch (_: Throwable) {}
        try { socket?.close() } catch (_: Throwable) {}
        output = null
        socket = null
        _connectedDevice.value = null
    }

    @SuppressLint("MissingPermission")
    private fun safeName(device: BluetoothDevice): String = try {
        device.name ?: device.address
    } catch (_: SecurityException) {
        device.address
    }

    fun shutdown() {
        disconnect()
        scope.cancel()
    }
}
