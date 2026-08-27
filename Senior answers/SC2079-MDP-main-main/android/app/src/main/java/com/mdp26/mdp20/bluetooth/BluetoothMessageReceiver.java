package com.mdp26.mdp20.bluetooth;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

import java.util.Objects;
import java.util.function.Consumer;

public class BluetoothMessageReceiver extends BroadcastReceiver {

    private BluetoothMessageParser messageDecoder;
    private Consumer<BluetoothMessage> messageAction;
    public BluetoothMessageReceiver(BluetoothMessageParser parser, Consumer<BluetoothMessage> msgConsumer) {
        this.messageDecoder = parser;
        this.messageAction = msgConsumer;
    }
    private final static String TAG = "BluetoothMessageReceiver";
    public final static String ACTION_MSG_READ = BluetoothConnection.ACTION_MSG_READ; 
    public final static String EXTRA_MSG_READ = BluetoothConnection.EXTRA_MSG_READ; 
    @Override
    public void onReceive(Context context, Intent intent) {
        if (!Objects.equals(intent.getAction(), ACTION_MSG_READ)) {
            return;
        }
        String msg = intent.getStringExtra(EXTRA_MSG_READ);
        Log.d(TAG, "Received msg: " + msg);
        BluetoothMessage btMsg = messageDecoder.apply(msg);
        Log.d(TAG, "Parsed msg: " + btMsg);
        messageAction.accept(btMsg);
    }
}
