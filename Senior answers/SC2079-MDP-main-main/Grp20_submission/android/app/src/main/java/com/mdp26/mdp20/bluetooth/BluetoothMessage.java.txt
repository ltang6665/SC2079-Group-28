package com.mdp26.mdp20.bluetooth;

import android.util.Log;

import com.mdp26.mdp20.Facing;
import com.mdp26.mdp20.Position;
import com.mdp26.mdp20.canvas.GridObstacle;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.List;
import java.util.Locale;

public sealed interface BluetoothMessage permits BluetoothMessage.CustomMessage, BluetoothMessage.ObstaclesMessage, BluetoothMessage.PlainStringMessage, BluetoothMessage.RobotMoveMessage, BluetoothMessage.RobotPositionMessage, BluetoothMessage.RobotStartMessage, BluetoothMessage.RobotStatusMessage, BluetoothMessage.TargetFoundMessage, BluetoothMessage.RobotStateMessage, BluetoothMessage.ObstacleEventMessage {
    
    public static final String TAG = "BluetoothMessage";

    default public JsonMessage getAsJsonMessage() {
        if (this instanceof JsonMessage)
            return (JsonMessage) this;
        return null;
    }

    public record RobotStatusMessage(String rawMsg, String status) implements BluetoothMessage {}
    public static BluetoothMessage ofRobotStatusMessage(String rawMsg, String status) {
        return new RobotStatusMessage(rawMsg, status);
    }

    public record TargetFoundMessage(String rawMsg, int obstacleId, int targetId, int direction) implements BluetoothMessage {}
    public static BluetoothMessage ofTargetFoundMessage(String rawMsg, int obstacleId, int targetId) {
        return new TargetFoundMessage(rawMsg, obstacleId, targetId, -1);
    }
    public static BluetoothMessage ofTargetFoundMessage(String rawMsg, int obstacleId, int targetId, int direction) {
        return new TargetFoundMessage(rawMsg, obstacleId, targetId, direction);
    }

    public record RobotPositionMessage(String rawMsg, int x, int y, int direction) implements BluetoothMessage {}
    public static BluetoothMessage ofRobotPositionMessage(String rawMsg, int x, int y, int direction) {
        return new RobotPositionMessage(rawMsg, x, y, direction);
    }

    public record PlainStringMessage(String rawMsg) implements BluetoothMessage {}
    public static BluetoothMessage ofPlainStringMessage(String rawMsg) {
        return new PlainStringMessage(rawMsg);
    }

    public record RobotMoveMessage(RobotMoveCommand cmd) implements BluetoothMessage, JsonMessage {
        @Override
        public String getAsJson() {
            return getFormattedStr("manual", cmd.value());
        }
    }
    public static BluetoothMessage ofRobotMoveMessage(RobotMoveCommand cmd) {
        return new RobotMoveMessage(cmd);
    }
    public record RobotStartMessage() implements BluetoothMessage, JsonMessage {
        @Override
        public String getAsJson() {
            return getFormattedStr("control", "start");
        }
    }
    public static BluetoothMessage ofRobotStartMessage() {
        return new RobotStartMessage();
    }

    public record RobotStateMessage(int x, int y, Facing direction) implements BluetoothMessage, JsonMessage {
        @Override
        public String getAsJson() {
            int valX = (x - 2) * 5;
            int valY = (y - 1) * 5;
            return String.format(Locale.ENGLISH, "ROBOT,%d,%d,%s", valX, valY, direction.name());
        }
    }
    public static BluetoothMessage ofRobotStateMessage(int x, int y, Facing direction) {
        return new RobotStateMessage(x, y, direction);
    }

    public record ObstacleEventMessage(int id, int x, int y, Facing face, boolean isRemove) implements BluetoothMessage, JsonMessage {
        @Override
        public String getAsJson() {
            int cmX = x * 10;
            
            int cmY = y * 10;
            
            if (isRemove) {
                return String.format(Locale.ENGLISH, "OBSTACLE,%d,%d,%d,-1", id, cmX, cmY);
            } else {
                return String.format(Locale.ENGLISH, "OBSTACLE,%d,%d,%d,%s", id, cmX, cmY, face.name());
            }
        }
    }
    public static BluetoothMessage ofObstacleEventMessage(int id, int x, int y, Facing face, boolean isRemove) {
        return new ObstacleEventMessage(id, x, y, face, isRemove);
    }

    public record ObstaclesMessage(List<GridObstacle> obstacleList) implements BluetoothMessage, JsonMessage {
        @Override
        public String getAsJson() {
            
            return "PATH";
        }
    }
    public static BluetoothMessage ofObstaclesMessage(List<GridObstacle> obstacleList) {
        return new ObstaclesMessage(obstacleList);
    }

    public abstract non-sealed class CustomMessage implements BluetoothMessage {}

}
