package com.mdp26.mdp20.hyperspace;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.RadialGradient;
import android.graphics.Shader;
import android.util.AttributeSet;
import android.view.View;

import androidx.annotation.Nullable;

import com.mdp26.mdp20.R;

import java.util.ArrayList;
import java.util.List;
import java.util.Random;

public class HyperspaceView extends View {
    private final List<Star> stars = new ArrayList<>();
    private final Random random = new Random();
    private final Paint paint = new Paint();
    private final Paint glowPaint = new Paint();
    private final Paint backgroundPaint = new Paint();
    private final Paint vignettePaint = new Paint();
    private float hyperdriveIntensity = 0.0f; 
    private float centerX, centerY;
    private long lastTime = 0;
    private boolean idleTwinkle = true;
    private long idleLastTime = 0;

    public HyperspaceView(Context context, @Nullable AttributeSet attrs) {
        super(context, attrs);
        paint.setColor(Color.WHITE);
        paint.setAntiAlias(true);
        glowPaint.setAntiAlias(true);
        backgroundPaint.setAntiAlias(true);
        vignettePaint.setAntiAlias(true);
        
        for (int i = 0; i < 200; i++) {
            randomizeStarProperties(new Star());
        }
    }

    @Override
    protected void onSizeChanged(int w, int h, int oldw, int oldh) {
        super.onSizeChanged(w, h, oldw, oldh);
        centerX = w / 2f;
        centerY = h / 2f;
        int bgStart = Color.rgb(3, 6, 16);
        int bgEnd = Color.rgb(2, 2, 8);
        backgroundPaint.setShader(new LinearGradient(
                0, 0, 0, h,
                bgStart,
                bgEnd,
                Shader.TileMode.CLAMP
        ));
        int vignetteCenter = Color.argb(0, 0, 0, 0);
        int vignetteEdge = Color.argb(180, 0, 0, 0);
        vignettePaint.setShader(new RadialGradient(
                centerX, centerY,
                Math.max(w, h) * 0.75f,
                vignetteCenter,
                vignetteEdge,
                Shader.TileMode.CLAMP
        ));
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        
        canvas.drawRect(0, 0, getWidth(), getHeight(), backgroundPaint);

        long now = System.currentTimeMillis();
        float deltaTime = (lastTime == 0) ? 0 : (now - lastTime) / 1000f;
        lastTime = now;

        float speedBase = 0.5f + (hyperdriveIntensity * 30.0f); 

        for (Star star : stars) {
            
            star.z -= speedBase * deltaTime * 500; 

            if (star.z <= 1) {
                randomizeStarProperties(star);
                star.z = 1000;
                star.pz = star.z;
            }

            float k = 128.0f / star.z;
            float px = star.x * k + centerX;
            float py = star.y * k + centerY;

            float pk = 128.0f / star.pz;
            float ppx = star.x * pk + centerX;
            float ppy = star.y * pk + centerY;

            star.pz = star.z;

            float depth = 1 - (star.z / 1000f);
            float size = (star.size + depth * 2.5f);
            float twinkle = 0.75f + (float) Math.sin(now * 0.004f + star.twinklePhase) * 0.25f;
            int alpha = (int) (255 * star.baseAlpha * twinkle * (0.35f + depth));
            if (alpha < 10) alpha = 10;

            if (px >= 0 && px <= getWidth() && py >= 0 && py <= getHeight()) {
                if (hyperdriveIntensity > 0.1f) {
                    float stroke = size * (1.2f + hyperdriveIntensity * 1.6f);
                    paint.setStrokeWidth(stroke);
                    paint.setColor(star.color);
                    paint.setAlpha(alpha);
                    canvas.drawLine(ppx, ppy, px, py, paint);

                    glowPaint.setColor(star.color);
                    glowPaint.setAlpha((int) (alpha * 0.6f));
                    canvas.drawCircle(px, py, size * 1.8f, glowPaint);
                } else {
                    paint.setColor(star.color);
                    paint.setAlpha(alpha);
                    canvas.drawCircle(px, py, size, paint);

                    glowPaint.setColor(star.color);
                    glowPaint.setAlpha((int) (alpha * 0.4f));
                    canvas.drawCircle(px, py, size * 2.2f, glowPaint);
                }
            } else {
                
                randomizeStarProperties(star);
            }
        }

        canvas.drawRect(0, 0, getWidth(), getHeight(), vignettePaint);

        if (hyperdriveIntensity > 0.02f || idleTwinkle) {
            if (hyperdriveIntensity <= 0.02f) {
                if (now - idleLastTime < 50) {
                    return;
                }
                idleLastTime = now;
            }
            postInvalidateOnAnimation(); 
        }
    }

    private void randomizeStarProperties(Star star) {
        star.x = (random.nextFloat() - 0.5f) * getWidth() * 10; 
        star.y = (random.nextFloat() - 0.5f) * getHeight() * 10;
        star.z = 1000; 
        star.pz = star.z;
        star.size = 0.8f + random.nextFloat() * 1.6f;
        star.baseAlpha = 0.45f + random.nextFloat() * 0.55f;
        star.twinklePhase = random.nextFloat() * (float) Math.PI * 2f;
        float hue;
        float roll = random.nextFloat();
        if (roll < 0.15f) {
            hue = 200f + random.nextFloat() * 20f; 
        } else if (roll < 0.30f) {
            hue = 40f + random.nextFloat() * 15f; 
        } else {
            hue = 0f; 
        }
        float sat = (hue == 0f) ? 0f : (0.25f + random.nextFloat() * 0.35f);
        float val = 0.85f + random.nextFloat() * 0.15f;
        star.color = Color.HSVToColor(new float[] { hue, sat, val });
        if (stars.size() < 200) stars.add(star);
    }

    public void setWarpFactor(float factor) {
        this.hyperdriveIntensity = factor;
        invalidate();
    }

    private static class Star {
        float x, y, z, pz;
        float size;
        float baseAlpha;
        float twinklePhase;
        int color;
    }
}
