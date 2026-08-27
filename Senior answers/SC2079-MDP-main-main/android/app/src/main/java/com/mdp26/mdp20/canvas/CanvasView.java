package com.mdp26.mdp20.canvas;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.util.AttributeSet;
import android.view.View;

import androidx.annotation.NonNull;

import com.mdp26.mdp20.Facing;

public class CanvasView extends View {
    private final String TAG = "CanvasView";
    private int cellSize; 
    private int offsetX, offsetY; 
    private final Paint gridPaint = new Paint();
    private final Paint textPaint = new Paint();
    private final Paint obstacleSelectedPaint = new Paint();
    private final Paint obstaclePaint = new Paint();
    private final Paint idPaint = new Paint();
    private final Paint facingPaint = new Paint();
    private final Paint targetPaint = new Paint();
    private final Paint startRegionPaint = new Paint();
    private final Paint obstacleShadowPaint = new Paint();
    private final Paint obstacleBorderPaint = new Paint();
    private Grid grid;

    public CanvasView(Context context, AttributeSet attrs) {
        super(context, attrs);
        init(context);
    }

    @Override
    public boolean performClick() {
        return super.performClick();
    }

    private void init(Context context) {
        
        gridPaint
                .setColor(androidx.core.content.ContextCompat.getColor(context, com.mdp26.mdp20.R.color.grid_line));
        gridPaint.setStrokeWidth(2);
        gridPaint.setStyle(Paint.Style.STROKE);

        textPaint.setColor(androidx.core.content.ContextCompat.getColor(context, com.mdp26.mdp20.R.color.text_primary));
        textPaint.setTextSize(20); 
        textPaint.setTextAlign(Paint.Align.CENTER);
        textPaint.setTypeface(android.graphics.Typeface.create("sans-serif-medium", android.graphics.Typeface.NORMAL));
        textPaint.setFakeBoldText(true);

        obstaclePaint
                .setColor(androidx.core.content.ContextCompat.getColor(context, com.mdp26.mdp20.R.color.obstacle_body));
        obstaclePaint.setStyle(Paint.Style.FILL);

        obstacleSelectedPaint.setColor(
                androidx.core.content.ContextCompat.getColor(context, com.mdp26.mdp20.R.color.obstacle_selected));
        obstacleSelectedPaint.setStyle(Paint.Style.STROKE);
        obstacleSelectedPaint.setStrokeWidth(4);

        obstacleShadowPaint.setColor(
                androidx.core.content.ContextCompat.getColor(context, com.mdp26.mdp20.R.color.obstacle_shadow));
        obstacleShadowPaint.setStyle(Paint.Style.FILL);

        obstacleBorderPaint.setColor(Color.DKGRAY); 
        obstacleBorderPaint.setStyle(Paint.Style.STROKE);
        obstacleBorderPaint.setStrokeWidth(2);

        idPaint.setColor(androidx.core.content.ContextCompat.getColor(context, com.mdp26.mdp20.R.color.white));
        idPaint.setTextAlign(Paint.Align.CENTER);
        idPaint.setTypeface(android.graphics.Typeface.create("sans-serif", android.graphics.Typeface.BOLD));
        idPaint.setFakeBoldText(false);
        idPaint.setTextSize(16);

        targetPaint.setColor(
                androidx.core.content.ContextCompat.getColor(context, com.mdp26.mdp20.R.color.status_success));
        targetPaint.setTextAlign(Paint.Align.CENTER);
        targetPaint.setTypeface(android.graphics.Typeface.create("sans-serif-black", android.graphics.Typeface.NORMAL));
        targetPaint.setFakeBoldText(true);
        targetPaint.setTextSize(21);

        facingPaint.setColor(
                androidx.core.content.ContextCompat.getColor(context, com.mdp26.mdp20.R.color.obstacle_facing));
        facingPaint.setStyle(Paint.Style.FILL);

        startRegionPaint
                .setColor(androidx.core.content.ContextCompat.getColor(context, com.mdp26.mdp20.R.color.accent));
        startRegionPaint.setStrokeWidth(4);
        startRegionPaint.setStyle(Paint.Style.STROKE);
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
    protected void onDraw(@NonNull Canvas canvas) {
        super.onDraw(canvas);
        drawGrid(canvas);
        drawStartRegion(canvas);
        drawAxisLabels(canvas);
        drawObstacles(canvas);
    }

    private void drawGrid(Canvas canvas) {
        int gridSize = Grid.GRID_SIZE;
        int gridWidth = gridSize * cellSize;
        int gridHeight = gridSize * cellSize;

        for (int i = 0; i <= gridSize; i++) {
            canvas.drawLine(offsetX + i * cellSize, offsetY, offsetX + i * cellSize, offsetY + gridHeight, gridPaint);
        }

        for (int i = 0; i <= gridSize; i++) {
            canvas.drawLine(offsetX, offsetY + i * cellSize, offsetX + gridWidth, offsetY + i * cellSize, gridPaint);
        }
    }

    private void drawStartRegion(Canvas canvas) {
        int left = offsetX;
        int right = offsetX + (4 * cellSize);
        int top = offsetY + ((Grid.GRID_SIZE - 4) * cellSize); 
        int bottom = offsetY + (Grid.GRID_SIZE * cellSize);

        canvas.drawLine(left, bottom, right, bottom, startRegionPaint); 
        canvas.drawLine(left, top, right, top, startRegionPaint); 
        canvas.drawLine(left, top, left, bottom, startRegionPaint); 
        canvas.drawLine(right, top, right, bottom, startRegionPaint); 
    }

    private void drawAxisLabels(Canvas canvas) {
        int gridSize = Grid.GRID_SIZE;

        float halfCell = cellSize / 2f;
        float yLabelOffsetY = cellSize / 4f; 

        for (int x = 0; x < gridSize; x++) {
            
            canvas.drawText(
                    String.valueOf(x),
                    offsetX + (x * cellSize) + halfCell,
                    offsetY + (gridSize * cellSize) + 30,
                    textPaint);
        }

        for (int y = 0; y < gridSize; y++) {
            
            float yPos = offsetY + ((gridSize - 1 - y) * cellSize) + halfCell + yLabelOffsetY;

            canvas.drawText(
                    String.valueOf(y),
                    offsetX - 30,
                    yPos,
                    textPaint);
        }
    }

    private void drawObstacles(Canvas canvas) {
        int id = 1;
        for (GridObstacle gridObstacle : grid.getObstacleList()) {
            int left = offsetX + gridObstacle.getPosition().getXInt() * cellSize;
            int top = offsetY + (Grid.GRID_SIZE - 1 - gridObstacle.getPosition().getYInt()) * cellSize; 
            int right = left + cellSize;
            int bottom = top + cellSize;

            int shadowOffset = cellSize / 10;
            canvas.drawRect(left + shadowOffset, top + shadowOffset, right + shadowOffset, bottom + shadowOffset,
                    obstacleShadowPaint);

            canvas.drawRect(left, top, right, bottom, obstaclePaint);

            if (gridObstacle.isSelected()) {
                canvas.drawRect(left, top, right, bottom, obstacleSelectedPaint);
            }

            float textX = left + (cellSize / 2);
            float textY = top + (cellSize / 2) - ((idPaint.descent() + idPaint.ascent()) / 2);

            if (gridObstacle.getTarget() == null) {
                
                canvas.drawText(String.valueOf(gridObstacle.getObstacleId()), textX, textY, idPaint);
            } else {
                
                canvas.drawText(gridObstacle.getTarget().getTargetStr(), textX, textY, targetPaint);
            }

            drawFacingIndicator(canvas, gridObstacle.getFacing(), left, top, right, bottom);
        }
    }

    private void drawFacingIndicator(Canvas canvas, Facing facing, int left, int top, int right, int bottom) {
        int stripThickness = cellSize / 6; 

        switch (facing) {
            case NORTH:
                canvas.drawRect(left, top, right, top + stripThickness, facingPaint);
                break;
            case EAST:
                canvas.drawRect(right - stripThickness, top, right, bottom, facingPaint);
                break;
            case SOUTH:
                canvas.drawRect(left, bottom - stripThickness, right, bottom, facingPaint);
                break;
            case WEST:
                canvas.drawRect(left, top, left + stripThickness, bottom, facingPaint);
                break;
        }
    }

    public int getOffsetX() {
        return offsetX;
    }

    public int getOffsetY() {
        return offsetY;
    }

    public int getCellSize() {
        return cellSize;
    }

    public void setGrid(Grid grid) {
        this.grid = grid;
        invalidate(); 
    }
}