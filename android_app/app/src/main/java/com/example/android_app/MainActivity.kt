package com.example.android_app

import android.os.Bundle
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat

import android.widget.TextView
import android.widget.Button

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContentView(R.layout.activity_main)
        val welcomeText = findViewById<TextView>(R.id.welcomeTextView)
        val startButton = findViewById<Button>(R.id.startButton)
        //set app intro page to have fade in animation
        welcomeText.animate()
            .alpha(1f)
            .setDuration(1500)
            .withEndAction {
                // 2. Fade in app options ater intro appears
                startButton.animate()
                    .alpha(1f)
                    .setDuration(800)
                    .start()
            }
            .start()
        ViewCompat.setOnApplyWindowInsetsListener(findViewById(R.id.main)) { v, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom)
            insets
        }
    }
}