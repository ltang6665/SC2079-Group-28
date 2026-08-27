package com.mdp26.mdp20.bluetooth;

import org.json.JSONObject;

public interface JsonMessage {
    
    public static final String PATTERN_STRING = "{\"cat\":\"%s\", \"value\": \"%s\"}";
    public static final String PATTERN_OBJECT = "{\"cat\":\"%s\", \"value\": %s}";

    default String getFormattedStr(String category, String value) {
        return String.format(JsonMessage.PATTERN_STRING, category, value);
    }
    default String getFormattedObj(String category, JSONObject obj) {
        return String.format(JsonMessage.PATTERN_OBJECT, category, obj);
    }
    public String getAsJson();
}