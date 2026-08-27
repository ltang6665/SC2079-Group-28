package com.mdp26.mdp20.bluetooth;

import android.util.Log;

import java.util.function.Function;

public interface BluetoothMessageParser extends Function<String, BluetoothMessage> {

    public static final String TAG = "BluetoothMessageParser";

    BluetoothMessageParser DEFAULT = msg -> {
        
        String[] params;
        if (msg.contains(",")) params = msg.split(",");
        else params = msg.split(";");

        if (params.length > 1) {
            String command = params[0].toUpperCase().trim(); 
            BluetoothMessage ret;
            
            switch (command) {
                case "INFO" -> ret = BluetoothMessage.ofPlainStringMessage("[info] " + params[1]);
                case "ERROR" -> ret = BluetoothMessage.ofPlainStringMessage("[error] " + params[1]);
                case "MODE" -> ret = BluetoothMessage.ofPlainStringMessage("[mode] " + params[1]);
                case "STATUS" -> ret = BluetoothMessage.ofRobotStatusMessage(msg, params[1]);
                case "ROBOT", "LOCATION" -> {
                    
                    if(params.length >= 3) {
                        try {
                            int x = Integer.parseInt(params[1].trim());
                            int y = Integer.parseInt(params[2].trim());
                            int dir = 1; 
                            
                            if (params.length >= 4) {
                                try {
                                    dir = Integer.parseInt(params[3].trim());
                                } catch (NumberFormatException e) {
                                    dir = decodeDirection(params[3].trim());
                                }
                            }
                            ret = BluetoothMessage.ofRobotPositionMessage(msg, x, y, dir);
                        } catch (Exception e) {
                             ret = BluetoothMessage.ofPlainStringMessage(msg);
                        }
                    } else {
                         ret = BluetoothMessage.ofPlainStringMessage(msg);
                    }
                }
                case "TARGET", "IMAGE-REC" -> {
                    
                    int[] intParams = extractIntegerArguments(params, 2);
                    if (params.length > 3) {
                         
                         int dir = -1;
                         try {
                              dir = Integer.parseInt(params[3].trim());
                         } catch (NumberFormatException e) {
                              dir = decodeDirection(params[3].trim());
                         }
                         ret = BluetoothMessage.ofTargetFoundMessage(msg, intParams[0], intParams[1], dir);
                    } else {
                         ret = BluetoothMessage.ofTargetFoundMessage(msg, intParams[0], intParams[1]);
                    }
                }
                default -> ret = BluetoothMessage.ofPlainStringMessage(msg);
            }
            ;
            return ret;
        }
        return BluetoothMessage.ofPlainStringMessage(msg);
    };

    public static int[] extractIntegerArguments(String[] params, int expectedSize) {
        int[] ret = new int[expectedSize];
        
        if (params.length <= expectedSize) {
            Log.e(TAG, String.format("Error in params, expected %d but size was %d", expectedSize, params.length));
            return ret;
        }
        
        for (int i = 0; i < expectedSize; ++i) {
            try {
                ret[i] = Integer.parseInt(params[i + 1].trim());
            } catch (NumberFormatException e) {
                ret[i] = 0; 
                Log.e(TAG, "Error in parsing " + params[i + 1]);
            }
        }
        return ret;
    }

    public static BluetoothMessageParser ofDefault() {
        return DEFAULT;
    }

    private static int decodeDirection(String dStr) {
        return switch(dStr.toUpperCase()) {
            case "N", "NORTH" -> 1;
            case "E", "EAST" -> 2;
            case "S", "SOUTH" -> 3;
            case "W", "WEST" -> 4;
            default -> 1;
        };
    }
}
