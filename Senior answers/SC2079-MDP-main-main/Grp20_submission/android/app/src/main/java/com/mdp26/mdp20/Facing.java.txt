package com.mdp26.mdp20;

public enum Facing {
    NORTH(1),
    EAST(2),
    SOUTH(3),
    WEST(4),
    SKIP(0);

    private int assignedId;

    Facing(int numericVal) {
        assignedId = numericVal;
    }

    public int getMappedCode() {
        return assignedId;
    }

    public static Facing getFacingFromCode(int code) {
        return switch (code) {
            case 1 -> NORTH;
            case 2 -> EAST;
            case 3 -> SOUTH;
            case 4 -> WEST;
            default -> NORTH;
        };
    }
}
