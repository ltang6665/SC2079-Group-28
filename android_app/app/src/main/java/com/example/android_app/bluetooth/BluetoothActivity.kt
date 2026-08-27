package com.example.android_app.bluetooth

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.example.android_app.R
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.launch

class BluetoothActivity : AppCompatActivity() {

    private lateinit var pairedAdapter: DeviceListAdapter
    private lateinit var discoveredAdapter: DeviceListAdapter
    private lateinit var statusView: TextView
    private lateinit var inboundLog: TextView
    private lateinit var sendField: EditText

    private val bluetoothAdapter: BluetoothAdapter? by lazy {
        (getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager)?.adapter
    }

    private val discoveryReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            when (intent?.action) {
                BluetoothDevice.ACTION_FOUND -> {
                    val device: BluetoothDevice? =
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                            intent.getParcelableExtra(
                                BluetoothDevice.EXTRA_DEVICE,
                                BluetoothDevice::class.java,
                            )
                        } else {
                            @Suppress("DEPRECATION")
                            intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE)
                        }
                    device?.let { discoveredAdapter.addIfMissing(it) }
                }
                BluetoothAdapter.ACTION_DISCOVERY_FINISHED -> {
                    findViewById<Button>(R.id.btnScan).isEnabled = true
                }
            }
        }
    }

    private val enableBtLauncher =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) {
            /* nothing — we re-check on scan button press */
        }

    private enum class PendingAction { NONE, LOAD_PAIRED, START_SCAN }
    private var pendingAction: PendingAction = PendingAction.NONE

    private val permissionsLauncher =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { grants ->
            val allGranted = grants.values.all { it }
            val action = pendingAction
            pendingAction = PendingAction.NONE
            if (!allGranted) {
                toast("Bluetooth permissions required")
                return@registerForActivityResult
            }
            when (action) {
                PendingAction.LOAD_PAIRED -> loadPairedDevices()
                PendingAction.START_SCAN -> startDiscovery()
                PendingAction.NONE -> Unit
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_bluetooth)

        statusView = findViewById(R.id.statusView)
        inboundLog = findViewById(R.id.inboundLog)
        sendField = findViewById(R.id.sendField)

        pairedAdapter = DeviceListAdapter(::onDeviceSelected)
        discoveredAdapter = DeviceListAdapter(::onDeviceSelected)

        findViewById<RecyclerView>(R.id.pairedList).apply {
            layoutManager = LinearLayoutManager(this@BluetoothActivity)
            adapter = pairedAdapter
        }
        findViewById<RecyclerView>(R.id.discoveredList).apply {
            layoutManager = LinearLayoutManager(this@BluetoothActivity)
            adapter = discoveredAdapter
        }

        findViewById<Button>(R.id.btnScan).setOnClickListener { onScanClicked() }
        findViewById<Button>(R.id.btnDisconnect).setOnClickListener {
            BluetoothService.disconnect()
        }
        findViewById<Button>(R.id.btnStopConnection).setOnClickListener {
            BluetoothService.stopConnection()
        }
        findViewById<Button>(R.id.btnSend).setOnClickListener {
            val text = sendField.text.toString().trim()
            if (text.isEmpty()) return@setOnClickListener
            if (BluetoothService.send(text)) {
                sendField.text.clear()
            } else {
                toast("Not connected")
            }
        }

        registerReceiver(discoveryReceiver, IntentFilter().apply {
            addAction(BluetoothDevice.ACTION_FOUND)
            addAction(BluetoothAdapter.ACTION_DISCOVERY_FINISHED)
        })

        observeService()
        loadPairedDevices()
    }

    override fun onDestroy() {
        super.onDestroy()
        try {
            unregisterReceiver(discoveryReceiver)
        } catch (_: IllegalArgumentException) {}
        cancelDiscovery()
    }

    private fun observeService() {
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) {
                launch {
                    BluetoothService.state.onEach { state ->
                        val name = BluetoothService.connectedDevice.value
                        statusView.text = when (state) {
                            BluetoothService.State.DISCONNECTED ->
                                getString(R.string.status_disconnected)
                            BluetoothService.State.CONNECTING ->
                                getString(R.string.status_connecting)
                            BluetoothService.State.CONNECTED ->
                                getString(R.string.status_connected, name ?: "device")
                            BluetoothService.State.RECONNECTING ->
                                getString(R.string.status_reconnecting)
                        }
                    }.launchIn(this)
                }
                launch {
                    BluetoothService.messages.onEach { line ->
                        appendInbound(line)
                    }.launchIn(this)
                }
            }
        }
    }

    private fun appendInbound(line: String) {
        val current = inboundLog.text?.toString().orEmpty()
        val trimmed = if (current.length > 4000) current.takeLast(2000) else current
        inboundLog.text = if (trimmed.isEmpty()) line else "$trimmed\n$line"
    }

    private fun onDeviceSelected(device: BluetoothDevice) {
        cancelDiscovery()
        BluetoothService.connect(device)
    }

    private fun onScanClicked() {
        if (!requireBtEnabled()) return
        if (!hasScanPermissions()) {
            pendingAction = PendingAction.START_SCAN
            permissionsLauncher.launch(neededScanPermissions())
            return
        }
        startDiscovery()
    }

    @SuppressLint("MissingPermission")
    private fun startDiscovery() {
        val adapter = bluetoothAdapter ?: run {
            toast("No Bluetooth adapter")
            return
        }
        discoveredAdapter.submit(emptyList())
        findViewById<Button>(R.id.btnScan).isEnabled = false
        adapter.cancelDiscovery()
        adapter.startDiscovery()
    }

    @SuppressLint("MissingPermission")
    private fun cancelDiscovery() {
        bluetoothAdapter?.cancelDiscovery()
    }

    @SuppressLint("MissingPermission")
    private fun loadPairedDevices() {
        if (!hasConnectPermission()) {
            pendingAction = PendingAction.LOAD_PAIRED
            permissionsLauncher.launch(neededScanPermissions())
            return
        }
        val adapter = bluetoothAdapter ?: return
        pairedAdapter.submit(adapter.bondedDevices.toList())
    }

    private fun requireBtEnabled(): Boolean {
        val adapter = bluetoothAdapter ?: run {
            toast("No Bluetooth adapter")
            return false
        }
        if (!adapter.isEnabled) {
            enableBtLauncher.launch(Intent(BluetoothAdapter.ACTION_REQUEST_ENABLE))
            return false
        }
        return true
    }

    private fun hasScanPermissions(): Boolean = neededScanPermissions().all { perm ->
        ContextCompat.checkSelfPermission(this, perm) == PackageManager.PERMISSION_GRANTED
    }

    private fun hasConnectPermission(): Boolean =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            ContextCompat.checkSelfPermission(this, Manifest.permission.BLUETOOTH_CONNECT) ==
                    PackageManager.PERMISSION_GRANTED
        } else true

    private fun neededScanPermissions(): Array<String> =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            arrayOf(
                Manifest.permission.BLUETOOTH_SCAN,
                Manifest.permission.BLUETOOTH_CONNECT,
            )
        } else {
            arrayOf(
                Manifest.permission.ACCESS_FINE_LOCATION,
                Manifest.permission.ACCESS_COARSE_LOCATION,
            )
        }

    private fun toast(msg: String) {
        Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
    }
}