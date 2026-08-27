package com.mdp26.mdp20;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.annotation.NonNull;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.Toolbar;
import androidx.appcompat.widget.SwitchCompat;
import android.widget.LinearLayout;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.location.LocationManager;
import android.media.MediaPlayer;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.util.Log;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import com.mdp26.mdp20.bluetooth.BluetoothConnection;
import com.mdp26.mdp20.bluetooth.BluetoothDeviceAdapter;
import com.mdp26.mdp20.bluetooth.BluetoothInfoReceiver;
import com.mdp26.mdp20.bluetooth.BluetoothMessage;
import com.mdp26.mdp20.bluetooth.BluetoothMessageParser;
import com.mdp26.mdp20.bluetooth.BluetoothMessageReceiver;

import java.util.ArrayList;

public class BluetoothActivity extends AppCompatActivity {

    private static final String TAG = "BluetoothActivity";
    private static final int BLUETOOTH_PERMISSIONS_REQUEST_CODE = 96;
    private static final int DISCOVERABLE_DURATION = 300; 
    private MyApplication myApp; 
    private BroadcastReceiver infoReceiver; 
    private BroadcastReceiver msgReceiver; 
    private BluetoothDeviceAdapter bluetoothDeviceAdapter; 

    private ActivityResultLauncher<Intent> requestEnableBluetooth;
    private ActivityResultLauncher<Intent> requestDiscoverable;

    private TextView receivedMsgView;
    private LinearLayout connectedPanel;
    private TextView connectedText;
    private View indicatorCircle;
    private SwitchCompat discoverSwitch;
    private View saberBlade;
    private android.animation.ValueAnimator saberAnimator;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_bluetooth);

        Toolbar toolbar = findViewById(R.id.topAppBar);
        setSupportActionBar(toolbar);

        myApp = (MyApplication) getApplication();

        String[] permissions = new String[] {
                Manifest.permission.BLUETOOTH_SCAN,
                Manifest.permission.BLUETOOTH_CONNECT,
                Manifest.permission.BLUETOOTH_ADVERTISE,
                Manifest.permission.ACCESS_FINE_LOCATION, 
                Manifest.permission.ACCESS_COARSE_LOCATION, 
        };
        requestPermissions(permissions, BLUETOOTH_PERMISSIONS_REQUEST_CODE);

        bindUI();

        requestEnableBluetooth = registerForActivityResult(
                new ActivityResultContracts.StartActivityForResult(),
                result -> {
                    if (result.getResultCode() == Activity.RESULT_OK) {
                        Log.d(TAG, "Bluetooth enabled.");
                        bootBluetoothService();
                    }
                });

        requestDiscoverable = registerForActivityResult(
                new ActivityResultContracts.StartActivityForResult(),
                result -> {
                    
                    if (result.getResultCode() == DISCOVERABLE_DURATION
                            || result.getResultCode() == Activity.RESULT_OK) {
                        Log.d(TAG, "Bluetooth Discovery on for " + DISCOVERABLE_DURATION + "s");
                        
                        if (discoverSwitch != null)
                            discoverSwitch.setChecked(true);

                        animateLightsaber(true);

                        new android.os.Handler(android.os.Looper.getMainLooper()).postDelayed(() -> {
                            if (discoverSwitch != null) {
                                discoverSwitch.setChecked(false);
                                animateLightsaber(false); 
                                Toast.makeText(this, "Discoverable mode disabled", Toast.LENGTH_SHORT).show();
                            }
                        }, DISCOVERABLE_DURATION * 1000L);
                    } else {
                        
                        Log.d(TAG, "Bluetooth Discovery cancelled/failed");
                        if (discoverSwitch != null)
                            discoverSwitch.setChecked(false);
                        animateLightsaber(false); 
                    }
                });

        infoReceiver = new BluetoothInfoReceiver(this::onBluetoothInfoReceived);
        for (IntentFilter intentFilter : BluetoothInfoReceiver.DEFAULT_FILTERS) {
            
            getApplicationContext().registerReceiver(infoReceiver, intentFilter, RECEIVER_EXPORTED);
        }

        msgReceiver = new BluetoothMessageReceiver(BluetoothMessageParser.ofDefault(), this::onMsgReceived);
        getApplicationContext().registerReceiver(msgReceiver,
                new IntentFilter(BluetoothMessageReceiver.ACTION_MSG_READ), RECEIVER_NOT_EXPORTED);

        LocationManager locationManager = (LocationManager) getSystemService(Context.LOCATION_SERVICE);
        boolean isGpsEnabled = locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER);
        if (!isGpsEnabled) {
            Log.d(TAG, "GPS / Location is not on, won't be able to discover non-paired devices.");
            Toast.makeText(this, "Turn on Location to Scan for devices.", Toast.LENGTH_SHORT).show();
        }
    }

    private void bindUI() {
        
        RecyclerView recyclerView = findViewById(R.id.btDeviceList);
        recyclerView.setLayoutManager(new LinearLayoutManager(this));
        bluetoothDeviceAdapter = new BluetoothDeviceAdapter(this, new ArrayList<>(), device -> {
            Toast.makeText(this, "Connecting to " + device.name(), Toast.LENGTH_SHORT).show();
            myApp.btInterface().connectAsClient(device.btDevice());
        });
        recyclerView.setAdapter(bluetoothDeviceAdapter);
        findViewById(R.id.btnScan).setOnClickListener(view -> reloadDiscoveredDevices());

        discoverSwitch = findViewById(R.id.switchDiscoverable);
        discoverSwitch.setOnCheckedChangeListener((buttonView, isChecked) -> {
            
            if (buttonView.isPressed() && isChecked) {
                enableDeviceDiscovery();
            } else if (buttonView.isPressed() && !isChecked) {
                
                animateLightsaber(false);
            }
        });

        android.widget.ImageButton themeToggle = findViewById(R.id.btnThemeToggle);
        themeToggle.setOnClickListener(v -> toggleTheme());

        Button canvasButton = findViewById(R.id.btnCanvas);
        canvasButton.setVisibility(View.VISIBLE); 
        canvasButton.setOnClickListener(view -> startActivity(new Intent(this, CanvasActivity.class)));

        findViewById(R.id.btnBigRed).setOnClickListener(v -> {
            startActivity(new Intent(BluetoothActivity.this, HyperspaceActivity.class));
        });

        connectedPanel = findViewById(R.id.statusLayout);
        indicatorCircle = findViewById(R.id.indicatorCircle);
        connectedPanel.setVisibility(View.VISIBLE); 
        receivedMsgView = findViewById(R.id.textReceivedMsg);
        receivedMsgView.setText("Received Messages: ");
        connectedText = findViewById(R.id.textConnectedStatus);

        updateConnectionUI(myApp.btConnection() != null, null);

        saberBlade = findViewById(R.id.saberBlade);
    }

    private void animateLightsaber(boolean isExtending) {
        if (saberBlade == null) return;

        if (saberAnimator != null && saberAnimator.isRunning()) {
            saberAnimator.cancel();
        }

        saberBlade.post(() -> {
            View parentContainer = (View) saberBlade.getParent();
            if (parentContainer == null) return;

            int boundWidth = parentContainer.getWidth();
            int hiltSize = findViewById(R.id.saberHandle).getWidth();
            int sidePadding = parentContainer.getPaddingStart() + parentContainer.getPaddingEnd();

            int computedLength = isExtending ? (boundWidth - hiltSize - sidePadding) : 0;
            computedLength = Math.max(computedLength, 0);

            int startWidth = saberBlade.getWidth();
            if (startWidth == computedLength) return;

            saberAnimator = android.animation.ValueAnimator.ofInt(startWidth, computedLength);
            saberAnimator.setDuration(450); 
            saberAnimator.setInterpolator(new android.view.animation.OvershootInterpolator(0.8f)); 
            saberAnimator.addUpdateListener(anim -> {
                int frameValue = (int) anim.getAnimatedValue();
                LinearLayout.LayoutParams lp = (LinearLayout.LayoutParams) saberBlade.getLayoutParams();
                lp.width = frameValue;
                saberBlade.setLayoutParams(lp);
            });
            saberAnimator.start();
        });
    }

    private void updateConnectionUI(boolean isConnected, String deviceName) {
        if (indicatorCircle != null) {
            indicatorCircle.setBackgroundTintList(android.content.res.ColorStateList.valueOf(
                    androidx.core.content.ContextCompat.getColor(this,
                            isConnected ? R.color.status_success : R.color.neon_red)));
        }
        if (connectedText != null) {
            connectedText.setTextColor(androidx.core.content.ContextCompat.getColor(this,
                    isConnected ? R.color.status_success : R.color.neon_red));
            if (isConnected) {
                connectedText.setText(deviceName != null ? "Connected to " + deviceName : "CONNECTED");
            } else {
                connectedText.setText("DISCONNECTED");
            }
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        getApplicationContext().unregisterReceiver(infoReceiver);
        getApplicationContext().unregisterReceiver(msgReceiver);
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions,
            @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == BLUETOOTH_PERMISSIONS_REQUEST_CODE) {
            boolean allPermissionsGranted = true;
            for (int result : grantResults) {
                if (result != PackageManager.PERMISSION_GRANTED) {
                    allPermissionsGranted = false;
                    break;
                }
            }
            if (allPermissionsGranted) {
                
                if (!myApp.btInterface().isBluetoothEnabled()) {
                    Toast.makeText(this, "This app requires Bluetooth to function.", Toast.LENGTH_SHORT).show();
                    Intent enableBtIntent = new Intent(BluetoothAdapter.ACTION_REQUEST_ENABLE);
                    requestEnableBluetooth.launch(enableBtIntent);
                } else {
                    
                    bootBluetoothService();
                }
            } else {
                
                showPermissionDeniedDialog();
            }
        }
    }

    private void enableDeviceDiscovery() {
        Intent discoverableIntent = new Intent(BluetoothAdapter.ACTION_REQUEST_DISCOVERABLE);
        discoverableIntent.putExtra(BluetoothAdapter.EXTRA_DISCOVERABLE_DURATION, DISCOVERABLE_DURATION);
        requestDiscoverable.launch(discoverableIntent);
        myApp.btInterface().acceptIncomingConnection();
    }

    private void reloadDiscoveredDevices() {
        
        bluetoothDeviceAdapter.initPairedDevices(myApp.btInterface().getBondedDevices());
        myApp.btInterface().scanForDevices();
    }

    private void bootBluetoothService() {
        if (myApp.btInterface().isBluetoothEnabled()) {
            bluetoothDeviceAdapter.initPairedDevices(myApp.btInterface().getBondedDevices());
        }
    }

    private void showPermissionDeniedDialog() {
        new AlertDialog.Builder(this)
                .setTitle("Bluetooth Access Revoked")
                .setMessage("Bluetooth and Location permissions are strictly required for establishing connections. Fix this in the App Settings.")
                .setPositiveButton("Goto Settings", (dialog, which) -> {
                    Intent navIntent = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS);
                    navIntent.setData(Uri.fromParts("package", getPackageName(), null));
                    startActivity(navIntent);
                })
                .setNegativeButton("Ignore", null)
                .show();
    }

    @SuppressLint("MissingPermission")
    private void onBluetoothInfoReceived(Intent bcastIntent, String actionOrigin) {
        Log.d(TAG, "Parsing Broadcast: " + actionOrigin);
        
        if (actionOrigin.equals(BluetoothDevice.ACTION_FOUND)) {
            BluetoothDevice newlyFound = bcastIntent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE, BluetoothDevice.class);
            if (newlyFound != null) {
                Log.d(TAG, "Spotted BT node -> " + newlyFound.getName() + " [" + newlyFound.getAddress() + "]");
                bluetoothDeviceAdapter.addDiscoveredDevice(newlyFound);
            }
        } else if (actionOrigin.equals(BluetoothConnection.ACTION_CONNECTED)) {
            boolean isLinkActive = bcastIntent.getBooleanExtra(BluetoothConnection.EXTRA_CONNECTED, false);
            BluetoothDevice peerDevice = bcastIntent.getParcelableExtra(BluetoothConnection.EXTRA_DEVICE, BluetoothDevice.class);
            
            if (peerDevice != null) {
                Log.i(TAG, "Link established with " + peerDevice.getName() + ": " + isLinkActive);
                if (!isLinkActive) {
                    Toast.makeText(this, "Dropped Connection... Re-arming in 3s...", Toast.LENGTH_SHORT).show();
                    new android.os.Handler(android.os.Looper.getMainLooper()).postDelayed(() -> {
                        myApp.btInterface().connectAsClient(peerDevice);
                    }, 3000);
                } else {
                    if (discoverSwitch != null && discoverSwitch.isChecked()) {
                        discoverSwitch.setChecked(false);
                        animateLightsaber(false);
                    }
                }
                updateConnectionUI(isLinkActive, peerDevice.getName());
                reloadDiscoveredDevices();
            }
        }
    }

    private void onMsgReceived(BluetoothMessage btMsg) {
        if (btMsg instanceof BluetoothMessage.PlainStringMessage m) {
            receivedMsgView.append(m.rawMsg() + "\n");
        } else if (btMsg instanceof BluetoothMessage.TargetFoundMessage m) {
            receivedMsgView.append("[image-rec] " + m.rawMsg() + "\n"); 
        } else if (btMsg instanceof BluetoothMessage.RobotPositionMessage m) {
            receivedMsgView.append("[location] " + m.rawMsg() + "\n"); 
        }
    }

    private void toggleTheme() {
        android.content.SharedPreferences prefs = getSharedPreferences("AppPrefs", MODE_PRIVATE);
        boolean currentMode = prefs.getBoolean("DarkMode", false);
        boolean newMode = !currentMode;

        prefs.edit().putBoolean("DarkMode", newMode).apply();

        androidx.appcompat.app.AppCompatDelegate.setDefaultNightMode(
                newMode ? androidx.appcompat.app.AppCompatDelegate.MODE_NIGHT_YES
                        : androidx.appcompat.app.AppCompatDelegate.MODE_NIGHT_NO);
    }
}
