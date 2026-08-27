package com.example.android_app

import android.content.Intent
import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.example.android_app.arena.ArenaActivity
import com.example.android_app.bluetooth.BluetoothActivity

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContentView(R.layout.activity_main)

        val welcomeText = findViewById<TextView>(R.id.welcomeTextView)
        val startBtn = findViewById<Button>(R.id.startButton)
        val connectBtn = findViewById<Button>(R.id.connectBluetoothButton)

        welcomeText.animate()
            .alpha(1f)
            .setDuration(1500)
            .withEndAction {
                connectBtn.animate().alpha(1f).setDuration(800).start()
                startBtn.animate().alpha(1f).setDuration(800).start()
            }
            .start()

        connectBtn.setOnClickListener {
            startActivity(Intent(this, BluetoothActivity::class.java))
        }

        startBtn.setOnClickListener {
            startActivity(Intent(this, ArenaActivity::class.java))
        }

        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.main)) { v, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom)
            insets
        }
    }
}
