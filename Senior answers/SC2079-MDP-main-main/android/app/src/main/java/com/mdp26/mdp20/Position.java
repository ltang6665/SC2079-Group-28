package com.mdp26.mdp20;

import java.util.Objects;

public class Position {
    private double horiz;
    private double vert;

    public Position(double xVal, double yVal) {
        this.horiz = xVal;
        this.vert = yVal;
    }

    public Position(int xVal, int yVal) {
        this.horiz = xVal;
        this.vert = yVal;
    }

    public static Position of(double x, double y) {
        return new Position(x, y);
    }

    public double getX() {
        return horiz;
    }

    public int getXInt() {
        return (int) horiz;
    }

    public void setX(double xVal) {
        this.horiz = xVal;
    }

    public double getY() {
        return vert;
    }

    public int getYInt() {
        return (int) vert;
    }

    public void setY(double yVal) {
        this.vert = yVal;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        Position position = (Position) o;
        return Double.compare(position.horiz, horiz) == 0 && Double.compare(position.vert, vert) == 0;
    }

    @Override
    public int hashCode() {
        return Objects.hash(horiz, vert);
    }

    @Override
    public String toString() {
        return "Position{" + horiz +
                "," + vert +
                '}';
    }
}
