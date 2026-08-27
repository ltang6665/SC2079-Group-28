package com.mdp26.mdp20.bluetooth;

import android.bluetooth.BluetoothDevice;

public record BluetoothDeviceModel(BluetoothDevice btDevice, String name, String address, boolean hasBond) {
}
