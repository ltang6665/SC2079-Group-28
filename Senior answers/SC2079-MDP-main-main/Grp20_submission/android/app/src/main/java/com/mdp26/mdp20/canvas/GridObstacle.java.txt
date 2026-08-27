package com.mdp26.mdp20.canvas;

import com.mdp26.mdp20.Facing;
import com.mdp26.mdp20.Position;
import com.mdp26.mdp20.Target;

import java.util.Objects;

public class GridObstacle {
    private int obstacleId;
    private Facing currentDirection;
    private Target assignedTarget;
    private final Position gridPosition;

    private boolean isFocused;

    public GridObstacle(int x, int y, Facing direction) {
        this.obstacleId = 1;
        this.currentDirection = direction;
        this.assignedTarget = null;
        this.gridPosition = Position.of(x, y);
        this.isFocused = false;
    }

    public static GridObstacle of(int x, int y) {
        return new GridObstacle(x, y, Facing.NORTH);
    }

    public static GridObstacle of(int x, int y, Facing direction) {
        return new GridObstacle(x, y, direction);
    }

    public void setObstacleId(int identifier) {
        this.obstacleId = identifier;
    }

    public int getObstacleId() {
        return obstacleId;
    }

    public Facing getFacing() {
        return currentDirection;
    }

    public void setFacing(Facing direction) {
        this.currentDirection = direction;
    }

    public Target getTarget() {
        return assignedTarget;
    }

    public void setTarget(Target assignment) {
        this.assignedTarget = assignment;
    }

    public Position getPosition() {
        return gridPosition;
    }

    public void updatePosition(int nx, int ny) {
        gridPosition.setX(nx);
        gridPosition.setY(ny);
    }

    public void rotateClockwise() {
        this.currentDirection = switch (this.currentDirection) {
            case NORTH -> Facing.EAST;
            case EAST -> Facing.SOUTH;
            case SOUTH -> Facing.WEST;
            case WEST -> Facing.NORTH;
            default -> Facing.NORTH;
        };
    }

    public boolean isSelected() {
        return isFocused;
    }

    public void setSelected(boolean state) {
        this.isFocused = state;
    }

    @Override
    public String toString() {
        return String.format("Obstacle[ID=%d, Dir=%s, Tgt=%s, Pos=%s]", obstacleId, currentDirection, assignedTarget, gridPosition);
    }

    @Override
    public boolean equals(Object obj) {
        if (this == obj) return true;
        if (!(obj instanceof GridObstacle)) return false;
        GridObstacle other = (GridObstacle) obj;
        return obstacleId == other.obstacleId;
    }

    @Override
    public int hashCode() {
        return Objects.hash(obstacleId, currentDirection, assignedTarget, gridPosition);
    }
}
