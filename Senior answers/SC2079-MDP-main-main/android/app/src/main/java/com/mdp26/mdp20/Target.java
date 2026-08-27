package com.mdp26.mdp20;

public class Target {
    private static String[] TARGET_DICTIONARY = new String[]{
            "0",
            "1", "2", "3", "4", "5", "6", "7", "8", "9", 
            "bs", 
            "1", 
            "2", 
            "3", 
            "4", 
            "5", 
            "6", 
            "7", 
            "8", 
            "9", 
            "A",
            "B",
            "C",
            "D",
            "E",
            "F",
            "G",
            "H",
            "S",
            "T",
            "U",
            "V",
            "W",
            "X",
            "Y",
            "Z",
            "up", 
            "dwn", 
            "rgt", 
            "lft", 
            "stp", 
    };

    private final String targetStr;
    private final int id;

    public Target(int id, String targetStr) {
        this.id = id;
        this.targetStr = targetStr;
    }

    public static Target of(int targetId) {
        if (targetId < 0 || targetId >= TARGET_DICTIONARY.length) return new Target(-1, "???");
        return new Target(targetId, TARGET_DICTIONARY[targetId]);
    }

    public String getTargetStr() {
        return targetStr;
    }

    public int getTargetId() {
        return id;
    }
}
