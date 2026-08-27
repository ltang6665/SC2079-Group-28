package com.mdp26.mdp20.canvas;

import android.content.Context;
import android.graphics.Rect;
import android.util.AttributeSet;
import android.view.View;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.Color;

import com.mdp26.mdp20.Facing;
import com.mdp26.mdp20.R;

public class RobotView extends View {
    private static final String TAG = "RobotView";
    private final Paint brushBody = new Paint();
    private final Paint brushShadow = new Paint();
    private final Paint brushFacing = new Paint();
    private Grid grid;
    
    private int cellSize; 
    private int offsetX, offsetY; 
    private Robot robot;

    public RobotView(Context context, AttributeSet attrs) {
        super(context, attrs);
        init();
    }

    private void init() {
        
        brushBody.setColor(androidx.core.content.ContextCompat.getColor(getContext(), R.color.robot_body));
        brushBody.setStyle(Paint.Style.FILL);

        brushShadow.setColor(androidx.core.content.ContextCompat.getColor(getContext(), R.color.robot_shadow));
        brushShadow.setStyle(Paint.Style.FILL);

        brushFacing.setColor(androidx.core.content.ContextCompat.getColor(getContext(), R.color.robot_direction));
        brushFacing.setStyle(Paint.Style.FILL);

    }

    @Override
    protected void onSizeChanged(int w, int h, int oldw, int oldh) {
        super.onSizeChanged(w, h, oldw, oldh);

        int gridSize = Grid.GRID_SIZE; 

        cellSize = Math.min(w, h) / (gridSize + 2);

        offsetX = (w - (gridSize * cellSize)) / 2;
        offsetY = (h - (gridSize * cellSize)) / 2;
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);

        int robotWidth = cellSize * 2; 
        int robotHeight = (int) (cellSize * 2.1); 

        int centerX = offsetX + (robot.getPosition().getXInt() * cellSize) + (cellSize / 2);
        int centerY = offsetY + (Grid.GRID_SIZE - 1 - robot.getPosition().getYInt()) * cellSize + (cellSize / 2);

        int left = centerX - (robotWidth / 2);
        int top = centerY - (robotHeight / 2);
        int right = left + robotWidth;
        int bottom = top + robotHeight;

        int shadowOffset = cellSize / 8;
        float rotationDegree = 0;
        switch (robot.getFacing()) {
            case NORTH: rotationDegree = 0; break;
            case EAST: rotationDegree = 90; break;
            case SOUTH: rotationDegree = 180; break;
            case WEST: rotationDegree = 270; break;
            case SKIP: break;
        }

        canvas.save();
        canvas.rotate(rotationDegree, centerX, centerY);

        drawXWing(canvas, brushShadow, brushShadow, left + shadowOffset, top + shadowOffset, right + shadowOffset, bottom + shadowOffset);

        drawXWing(canvas, brushBody, brushFacing, left, top, right, bottom);

        canvas.restore();
    }

    private void drawXWing(Canvas canvas, Paint bodyPaint, Paint detailPaint, int left, int top, int right, int bottom) {
        float width = right - left;
        float height = bottom - top;
        float cx = left + width / 2;
        float cy = top + height / 2;

        android.graphics.Path path = new android.graphics.Path();
        
        path.moveTo(cx, top + height * 0.05f); 
        path.lineTo(cx + width * 0.12f, top + height * 0.3f);
        path.lineTo(cx + width * 0.12f, bottom - height * 0.05f);
        path.lineTo(cx - width * 0.12f, bottom - height * 0.05f);
        path.lineTo(cx - width * 0.12f, top + height * 0.3f);
        path.close();

        path.moveTo(cx + width * 0.12f, cy - height * 0.1f);
        path.lineTo(right - width * 0.05f, cy + height * 0.1f);
        path.lineTo(right - width * 0.05f, cy + height * 0.3f);
        path.lineTo(cx + width * 0.12f, cy + height * 0.2f);
        path.close();

        path.moveTo(cx - width * 0.12f, cy - height * 0.1f);
        path.lineTo(left + width * 0.05f, cy + height * 0.1f);
        path.lineTo(left + width * 0.05f, cy + height * 0.3f);
        path.lineTo(cx - width * 0.12f, cy + height * 0.2f);
        path.close();

        canvas.drawPath(path, bodyPaint);

        float engineWidth = width * 0.15f;
        canvas.drawRect(right - width * 0.05f - engineWidth, cy + height * 0.15f, right - width * 0.05f, cy + height * 0.35f, bodyPaint);
        canvas.drawRect(left + width * 0.05f, cy + height * 0.15f, left + width * 0.05f + engineWidth, cy + height * 0.35f, bodyPaint);

        canvas.drawOval(new android.graphics.RectF(cx - width * 0.08f, cy - height * 0.15f, cx + width * 0.08f, cy + height * 0.05f), detailPaint);
        
        canvas.drawRect(right - width * 0.08f, cy - height * 0.2f, right - width * 0.06f, cy + height * 0.1f, detailPaint);
        canvas.drawRect(left + width * 0.06f, cy - height * 0.2f, left + width * 0.08f, cy + height * 0.1f, detailPaint);
    }

    public void setRobot(Robot robot) {
        this.robot = robot;
        invalidate(); 
    }
}
