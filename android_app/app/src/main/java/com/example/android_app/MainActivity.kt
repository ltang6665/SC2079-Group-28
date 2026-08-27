package com.example.android_app

import android.os.Bundle
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat

// import features
import android.widget.TextView
import android.widget.Button
import android.content.Intent

// import sub-packages
import com.example.android_app.bluetooth.BluetoothActivity

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContentView(R.layout.activity_main)
        val welcomeText = findViewById<TextView>(R.id.welcomeTextView)
        val startBtn = findViewById<Button>(R.id.startButton)
        val connectBtn = findViewById<Button>(R.id.connectBluetoothButton)
        //set app intro page to have fade in animation
        welcomeText.animate()
            .alpha(1f)
            .setDuration(1500)
            .withEndAction {
                //fade in app options after intro
                connectBtn.animate().alpha(1f).setDuration(800).start()
                startBtn.animate().alpha(1f).setDuration(800).start()
            }
            .start()

        // on click of 'Connect to Device', navigate to new page
        connectBtn.setOnClickListener {
            val intent = Intent(this, BluetoothActivity::class.java)
            startActivity(intent)
        }

        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.main)) { v, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom)
            insets
        }
    }
}