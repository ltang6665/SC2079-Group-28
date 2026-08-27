package com.mdp26.mdp20.canvas;

import com.mdp26.mdp20.Facing;
import com.mdp26.mdp20.Position;

public class Robot {
    private Facing facing;
    private final Position position;
    private final double turningRadius = 4.5;

    public Robot(int x, int y, Facing facing) {
        this.facing = facing;
        this.position = Position.of(x, y);
    }

    public static Robot ofDefault() {
        return new Robot(1, 1, Facing.NORTH);
    }

    public static Robot of(int x, int y) {
        return new Robot(x, y, Facing.NORTH);
    }

    public static Robot of(int x, int y, Facing facing) {
        return new Robot(x, y, facing);
    }

    public Robot updatePosition(int x, int y) {
        position.setX(x);
        position.setY(y);
        return this;
    }

    public Position getPosition() {
        return this.position;
    }

    public Robot updateFacing(Facing facing) {
        if (!facing.equals(Facing.SKIP))
            this.facing = facing;
        return this;
    }

    public Facing getFacing() {
        return this.facing;
    }

    private boolean isWithinBounds(double x, double y) {
        return x >= 1 && x < Grid.GRID_SIZE - 1 && y >= 1 && y < Grid.GRID_SIZE - 1;
    }

    public void moveForward() {
        int newX = this.position.getXInt();
        int newY = this.position.getYInt();
        switch (this.facing) {
            case NORTH -> newY += 1;
            case EAST -> newX += 1;
            case SOUTH -> newY -= 1;
            case WEST -> newX -= 1;
            default -> {}
        }
        if (isWithinBounds(newX, newY)) {
            this.position.setX(newX);
            this.position.setY(newY);
        }
    }

    public void moveBackward() {
        int newX = this.position.getXInt();
        int newY = this.position.getYInt();
        switch (this.facing) {
            case NORTH -> newY -= 1;
            case EAST -> newX -= 1;
            case SOUTH -> newY += 1;
            case WEST -> newX += 1;
            default -> {}
        }
        if (isWithinBounds(newX, newY)) {
            this.position.setX(newX);
            this.position.setY(newY);
        }
    }

    public void turnRight() {
        double newX = this.position.getXInt();
        double newY = this.position.getYInt();
        Facing newFacing = this.facing;

        switch (this.facing) {
            case NORTH -> { newY += 1; newX += turningRadius; newFacing = Facing.EAST; }
            case EAST -> { newX += 1; newY -= turningRadius; newFacing = Facing.SOUTH; }
            case SOUTH -> { newY -= 1; newX -= turningRadius; newFacing = Facing.WEST; }
            case WEST -> { newX -= 1; newY += turningRadius; newFacing = Facing.NORTH; }
            default -> {}
        }

        if (isWithinBounds(newX, newY)) {
            this.position.setX(newX);
            this.position.setY(newY);
            this.facing = newFacing;
        }
    }

    public void turnLeft() {
        double newX = this.position.getXInt();
        double newY = this.position.getYInt();
        Facing newFacing = this.facing;

        switch (this.facing) {
            case NORTH -> { newY += 1; newX -= turningRadius; newFacing = Facing.WEST; }
            case WEST -> { newX -= 1; newY -= turningRadius; newFacing = Facing.SOUTH; }
            case SOUTH -> { newY -= 1; newX += turningRadius; newFacing = Facing.EAST; }
            case EAST -> { newX += 1; newY += turningRadius; newFacing = Facing.NORTH; }
            default -> {}
        }
        
        if (isWithinBounds(newX, newY)) {
            this.position.setX(newX);
            this.position.setY(newY);
            this.facing = newFacing;
        }
    }

    public void rotateRight() {
        this.facing = switch (this.facing) {
            case NORTH -> Facing.EAST;
            case EAST -> Facing.SOUTH;
            case SOUTH -> Facing.WEST;
            case WEST -> Facing.NORTH;
            default -> this.facing;
        };
    }

    public void rotateLeft() {
        this.facing = switch (this.facing) {
            case NORTH -> Facing.WEST;
            case WEST -> Facing.SOUTH;
            case SOUTH -> Facing.EAST;
            case EAST -> Facing.NORTH;
            default -> this.facing;
        };
    }
}
