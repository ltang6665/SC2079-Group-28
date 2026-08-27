package com.mdp26.mdp20.canvas;

import android.util.Log;
import android.view.MotionEvent;
import android.view.View;
import android.content.Context;
import android.widget.Toast;

import com.mdp26.mdp20.MyApplication;
import com.mdp26.mdp20.bluetooth.BluetoothMessage;
import com.mdp26.mdp20.CanvasActivity;

import java.util.Optional;

public class CanvasTouchController implements View.OnTouchListener {
    private final static String TAG = "CanvasTouchController";
    private final Grid grid;
    private final MyApplication myApp;
    private final CanvasActivity activity;
    private Optional<GridObstacle> selectedObstacle = Optional.empty();
    private final int SELECTION_RADIUS;
    private static final float SELECTION_RADIUS_DP = 2f;

    private int downX = 0, downY = 0;

    public CanvasTouchController(CanvasActivity activity, MyApplication myApp) {
        this.activity = activity;
        this.myApp = myApp;
        this.grid = myApp.grid();
        this.SELECTION_RADIUS = convertDpToPx(myApp.getApplicationContext(), SELECTION_RADIUS_DP);
    }

    private static int convertDpToPx(Context context, float dp) {
        return (int) (dp * context.getResources().getDisplayMetrics().density);
    }

    @Override
    public boolean onTouch(View v, MotionEvent event) {
        CanvasView canvasView = (CanvasView) v;
        int x = (int) ((event.getX() - canvasView.getOffsetX()) / canvasView.getCellSize());
        int y = (int) ((event.getY() - canvasView.getOffsetY()) / canvasView.getCellSize());
        y = (Grid.GRID_SIZE - 1) - y; 

        switch (event.getAction()) {
            case MotionEvent.ACTION_DOWN:
                downX = x;
                downY = y;
                Log.d(TAG, "Touched down at (" + downX + ", " + downY + ")");
                if (grid.isInsideGrid(downX, downY)) {
                    selectedObstacle = grid.searchObstacleNearby(downX, downY, SELECTION_RADIUS);
                    selectedObstacle.ifPresent(obst -> {
                        Log.d(TAG, "Selected obstacle at " + obst.getPosition());
                        obst.setSelected(true);
                        canvasView.invalidate();
                    });
                }
                break;

            case MotionEvent.ACTION_UP:
                v.performClick();
                Log.d(TAG, "Touched up at (" + x + ", " + y + ")");
                if (selectedObstacle.isPresent()) {
                    GridObstacle obstacle = selectedObstacle.get();
                    obstacle.setSelected(false);
                    int oldX = obstacle.getPosition().getXInt();
                    int oldY = obstacle.getPosition().getYInt();
                    Log.d(TAG, downX + " " + downY + " " + x + " " + y);
                    if (downX == x && downY == y) {
                        obstacle.rotateClockwise();
                        Log.d(TAG, "Rotated obstacle clockwise at " + obstacle.getPosition());
                        canvasView.invalidate(); 
                        rebuildRemoteMap();
                    } else if (!grid.isInsideGrid(x, y)) {
                        grid.removeObstacle(oldX, oldY);
                        Log.d(TAG, "Removed obstacle at (" + oldX + ", " + oldY + ")");
                        canvasView.invalidate(); 
                        rebuildRemoteMap();
                    } else if (!grid.hasObstacle(x, y)) {
                        obstacle.updatePosition(x, y);
                        Log.d(TAG, "Moved obstacle from (" + oldX + ", " + oldY + ") to (" + x + ", " + y + ")");
                        Toast.makeText(myApp, "Moved obst to (" + x + ", " + y + ")", Toast.LENGTH_SHORT).show();
                        canvasView.invalidate(); 
                        rebuildRemoteMap();
                    }
                } else {
                    if (grid.isInsideGrid(x, y) && !grid.hasObstacle(x, y)) {
                        GridObstacle obstacle = GridObstacle.of(x, y);
                        grid.addObstacle(obstacle);
                        Log.d(TAG, "Added new obstacle at (" + x + ", " + y + ")");
                        Toast.makeText(myApp, "Added obst at (" + x + ", " + y + ")", Toast.LENGTH_SHORT).show();
                        canvasView.invalidate(); 
                        rebuildRemoteMap();
                    }
                }
                selectedObstacle = Optional.empty(); 
                break;
    }
        return true;
    }

    private void rebuildRemoteMap() {
        if (myApp.btConnection() == null) return;
        
        String strClear = "CLEAR";
        myApp.btConnection().sendMessage(strClear);
        activity.logMessage("SENT", strClear, "#00BCD4");
        
        for (GridObstacle obs : grid.getObstacleList()) {
            BluetoothMessage msg = BluetoothMessage.ofObstacleEventMessage(
                obs.getObstacleId(), 
                obs.getPosition().getXInt(), 
                obs.getPosition().getYInt(), 
                obs.getFacing(), 
                false
            );
            String msgStr = msg.getAsJsonMessage().getAsJson();
            myApp.btConnection().sendMessage(msgStr);
            activity.logMessage("SENT", msgStr, "#00BCD4");
        }
    }
}
