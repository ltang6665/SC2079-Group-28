package com.mdp26.mdp20.bluetooth;

import android.annotation.SuppressLint;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothManager;
import android.bluetooth.BluetoothServerSocket;
import android.bluetooth.BluetoothSocket;
import android.content.Context;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.widget.Toast;

import java.io.IOException;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReentrantLock;

public class BluetoothInterface {
    private static final String TAG = "BluetoothInterface";
    private static final String BT_NAME = "MDP_GRP_21";
    private static final UUID BT_UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB"); 

    private final Context context; 
    private final BluetoothAdapter bluetoothAdapter; 

    private AcceptThread serverThread = null; 
    private ConnectThread clientThread = null; 
    private BluetoothConnection activeSession = null; 

    private final Lock threadLock; 
    private final Lock connectionLock; 

    public BluetoothInterface(Context context) {
        BluetoothManager btMgr = (BluetoothManager) context.getSystemService(Context.BLUETOOTH_SERVICE);
        this.bluetoothAdapter = btMgr.getAdapter();
        this.context = context;

        threadLock = new ReentrantLock();
        connectionLock = new ReentrantLock();
    }

    void onConnected(BluetoothSocket socket, BluetoothDevice device) {
        threadLock.lock();
        
        if (serverThread != null) {
            serverThread.cancel();
            serverThread = null;
        }
        if (clientThread != null) {
            clientThread.cancel();
            clientThread = null;
        }

        connectionLock.lock();
        try {
            if (activeSession != null)
                activeSession.cancel();
            activeSession = new BluetoothConnection(context, socket, device);
            activeSession.start();
        } finally {
            connectionLock.unlock();
        }

        threadLock.unlock();
    }

    public boolean isBluetoothEnabled() {
        return bluetoothAdapter.isEnabled();
    }

    public BluetoothConnection getBluetoothConnection() {
        return activeSession;
    }

    public void acceptIncomingConnection() {
        threadLock.lock();
        try {
            if (serverThread != null) {
                serverThread.cancel();
            }
            serverThread = new AcceptThread();
            serverThread.start();
        } finally {
            threadLock.unlock();
        }
    }

    public void connectAsClient(BluetoothDevice btDevice) {
        threadLock.lock();
        try {
            if (clientThread != null) {
                clientThread.cancel();
            }
            clientThread = new ConnectThread(btDevice);
            clientThread.start();
        } finally {
            threadLock.unlock();
        }
    }

    @SuppressLint("MissingPermission")
    public void scanForDevices() {
        if (bluetoothAdapter.isDiscovering()) {
            bluetoothAdapter.cancelDiscovery();
        }
        boolean res = bluetoothAdapter.startDiscovery();
        if (!res) {
            Log.e(TAG, "bluetoothAdapter.startDiscovery() was false");
        }
        Toast.makeText(context, "Scanning for devices...", Toast.LENGTH_SHORT).show();
    }

    @SuppressLint("MissingPermission")
    public Set<BluetoothDevice> getBondedDevices() {
        return bluetoothAdapter.getBondedDevices();
    }

    private class AcceptThread extends Thread {
        private final BluetoothServerSocket serverSocket;

        @SuppressLint("MissingPermission")
        public AcceptThread() {
            BluetoothServerSocket tmp = null;
            try {
                tmp = bluetoothAdapter.listenUsingRfcommWithServiceRecord(BT_NAME, BT_UUID);

            } catch (IOException e) {
                Log.e(TAG, "Socket's listen() method failed", e);
            }
            this.serverSocket = tmp;
        }

        @SuppressLint("MissingPermission")
        @Override
        public void run() {
            Log.d(TAG, "AcceptThread: Running.");
            BluetoothSocket socket = null;
            while (true) {
                try {
                    socket = serverSocket.accept();
                } catch (IOException e) {
                    Log.e(TAG, "Socket's accept() method failed", e);
                    break;
                }

                if (socket != null) {
                    Log.d(TAG, "Socket Addr:" + socket.getRemoteDevice().getAddress());
                    Log.d(TAG, "Socket Name:" + socket.getRemoteDevice().getName());
                    onConnected(socket, socket.getRemoteDevice());
                    try {
                        serverSocket.close();
                    } catch (IOException e) {
                        throw new RuntimeException(e);
                    }
                    break;
                }
            }
        }

        public void cancel() {
            try {
                serverSocket.close();
                Log.d(TAG, "AcceptThread: Socket closed.");
            } catch (IOException e) {
                Log.e(TAG, "Could not close the AcceptThread socket", e);
            }
            this.interrupt();
        }
    }

    private class ConnectThread extends Thread {
        private final BluetoothSocket socket;
        private final BluetoothDevice device;

        @SuppressLint("MissingPermission")
        public ConnectThread(BluetoothDevice device) {
            BluetoothSocket tmp = null;
            this.device = device;

            try {
                tmp = device.createRfcommSocketToServiceRecord(BT_UUID);

            } catch (IOException e) {
                Log.e(TAG, "Socket's create() method failed", e);
            }
            this.socket = tmp;
        }

        @SuppressLint("MissingPermission")
        @Override
        public void run() {
            Log.d(TAG, "ConnectThread: Running.");
            
            bluetoothAdapter.cancelDiscovery();

            try {
                socket.connect();
                Log.d(TAG, "Socket Addr:" + socket.getRemoteDevice().getAddress());
                Log.d(TAG, "Socket Name:" + socket.getRemoteDevice().getName());
                onConnected(socket, device);
            } catch (IOException connectException) {
                
                try {
                    Log.e(TAG, "Unable to connect");
                    new Handler(Looper.getMainLooper()).post(() ->
                            Toast.makeText(context, "Connection failed", Toast.LENGTH_SHORT).show()
                    );
                    socket.close();
                } catch (IOException closeException) {
                    Log.e(TAG, "Could not close the client socket", closeException);
                }
            }
        }

        public void cancel() {
            
            this.interrupt();
        }
    }
}
