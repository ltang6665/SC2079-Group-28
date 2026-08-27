package com.mdp26.mdp20.canvas;

import android.util.Log;

import com.mdp26.mdp20.Target;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

public class Grid {

    private static final String TAG = "GridSystem";
    public static final int GRID_SIZE = 20;
    
    private static int nextIdentifier = 1;
    
    private final List<GridObstacle> obstacles;

    public Grid() {
        this.obstacles = new ArrayList<>();
    }

    public boolean addObstacle(GridObstacle obstacle) {
        obstacles.add(obstacle);
        obstacle.setObstacleId(nextIdentifier++);
        Log.d(TAG, "Obstacle registered: " + obstacle);
        return true;
    }

    public boolean removeObstacle(int x, int y) {
        Optional<GridObstacle> target = locateObstacleAt(x, y);
        if (target.isPresent()) {
            obstacles.remove(target.get());
            Log.d(TAG, "Obstacle unregistered: " + target.get());
            return true;
        }
        return false;
    }

    public Optional<GridObstacle> locateObstacleAt(int x, int y) {
        return obstacles.stream()
                .filter(obs -> obs.getPosition().getXInt() == x && obs.getPosition().getYInt() == y)
                .findFirst();
    }

    public Optional<GridObstacle> searchObstacleNearby(int touchX, int touchY, int selectionRadius) {
        GridObstacle closest = null;
        double shortestDistance = selectionRadius; 

        for (GridObstacle obs : obstacles) {
            int ox = obs.getPosition().getXInt();
            int oy = obs.getPosition().getYInt();
            
            double dist = Math.hypot(touchX - ox, touchY - oy);

            if (dist < shortestDistance) {
                shortestDistance = dist;
                closest = obs;
            }
        }
        return Optional.ofNullable(closest);
    }

    public Optional<GridObstacle> locateObstacleById(int targetId) {
        return obstacles.stream()
                .filter(obs -> obs.getObstacleId() == targetId)
                .findFirst();
    }

    public boolean hasObstacle(int x, int y) {
        return locateObstacleAt(x, y).isPresent();
    }

    public List<GridObstacle> getObstacleList() {
        return obstacles;
    }

    public void updateObstacleTarget(int x, int y, int targetId) {
        locateObstacleAt(x, y).ifPresent(obs -> obs.setTarget(Target.of(targetId)));
    }

    public void updateObstacleTarget(int obstacleId, int targetId) {
        locateObstacleById(obstacleId).ifPresent(obs -> obs.setTarget(Target.of(targetId)));
    }

    public boolean isInsideGrid(int x, int y) {
        return x >= 0 && x < GRID_SIZE && y >= 0 && y < GRID_SIZE;
    }

    public void clear() {
        obstacles.clear();
        nextIdentifier = 1;
    }
}
