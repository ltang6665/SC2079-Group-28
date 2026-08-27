package com.mdp26.mdp20;

import android.app.Application;

import com.mdp26.mdp20.bluetooth.BluetoothConnection;
import com.mdp26.mdp20.bluetooth.BluetoothInterface;
import com.mdp26.mdp20.canvas.Grid;
import com.mdp26.mdp20.canvas.Robot;

public class MyApplication extends Application {
    private BluetoothInterface btLinkManager;
    private Grid appGrid;
    private Robot primaryRobot;

    @Override
    public void onCreate() {
        super.onCreate();
        
        android.content.SharedPreferences prefs = getSharedPreferences("AppPrefs", MODE_PRIVATE);
        boolean isDarkMode = prefs.getBoolean("DarkMode", false);
        androidx.appcompat.app.AppCompatDelegate.setDefaultNightMode(
            isDarkMode ? androidx.appcompat.app.AppCompatDelegate.MODE_NIGHT_YES 
                       : androidx.appcompat.app.AppCompatDelegate.MODE_NIGHT_NO
        );
        
        btLinkManager = new BluetoothInterface(this);
        appGrid = new Grid();
        primaryRobot = Robot.ofDefault();
    }

    public BluetoothInterface btInterface() {
        return btLinkManager;
    }

    public BluetoothConnection btConnection() {
        return btLinkManager.getBluetoothConnection();
    }

    public Grid grid() {
        return appGrid;
    }

    public Robot robot() {
        return primaryRobot;
    }
}