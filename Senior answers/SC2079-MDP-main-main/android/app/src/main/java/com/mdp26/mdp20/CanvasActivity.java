package com.mdp26.mdp20;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.widget.Toolbar;
import androidx.core.text.HtmlCompat;
import com.google.android.material.tabs.TabLayout;
import androidx.constraintlayout.widget.ConstraintLayout;

import android.content.BroadcastReceiver;
import android.content.IntentFilter;
import android.os.Bundle;
import android.util.Log;
import android.widget.Button;
import android.widget.ScrollView;
import android.widget.TextView;
import android.view.View;
import android.widget.AdapterView;
import android.widget.ArrayAdapter;
import android.widget.Spinner;
import android.widget.Toast;
import android.text.InputFilter;
import android.text.Spanned;
import android.widget.EditText;
import android.content.SharedPreferences;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import com.mdp26.mdp20.bluetooth.BluetoothMessage;
import com.mdp26.mdp20.bluetooth.BluetoothMessageParser;
import com.mdp26.mdp20.bluetooth.BluetoothMessageReceiver;
import com.mdp26.mdp20.canvas.CanvasTouchController;
import com.mdp26.mdp20.canvas.CanvasView;
import com.mdp26.mdp20.canvas.GridObstacle;
import com.mdp26.mdp20.canvas.RobotView;

public class CanvasActivity extends AppCompatActivity {
    private TextView receivedMessages;
    private TextView robotStatusDynamic;
    private ScrollView scrollReceivedMessages;
    private Spinner spinnerRobotFacing;
    private EditText inputX;
    private EditText inputY;
    private EditText chatInputBox;
    private String selectedFacing = "NORTH"; 
    private Facing facingDirection;
    private final String TAG = "CanvasActivity";
    private MyApplication myApp;
    private BroadcastReceiver msgReceiver; 
    private CanvasView canvasView;
    private RobotView robotView;
    private CanvasTouchController canvasTouchController;

    private ConstraintLayout layoutMapMode;
    private ConstraintLayout layoutLogMode;
    private TabLayout tabLayout;

    public void logMessage(String direction, String message, String colorHex) {
        if (receivedMessages != null) {
            String htmlText = "<br><font color='" + colorHex + "'><b>[" + direction + "]</b> " + message + "</font>";
            receivedMessages.append(HtmlCompat.fromHtml(htmlText, HtmlCompat.FROM_HTML_MODE_LEGACY));
            scrollReceivedMessages.post(() -> scrollReceivedMessages.fullScroll(View.FOCUS_DOWN));
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        if (receivedMessages != null) {
            outState.putCharSequence("LOGS", receivedMessages.getText());
        }
    }

    @Override
    protected void onRestoreInstanceState(Bundle savedInstanceState) {
        super.onRestoreInstanceState(savedInstanceState);
        if (receivedMessages != null) {
            receivedMessages.setText(savedInstanceState.getCharSequence("LOGS"));
        }
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_canvas);

        Toolbar toolbar = findViewById(R.id.topAppBar);
        setSupportActionBar(toolbar);
        if (getSupportActionBar() != null) {
            getSupportActionBar().setDisplayHomeAsUpEnabled(true);
        }
        toolbar.setNavigationOnClickListener(v -> getOnBackPressedDispatcher().onBackPressed());

        myApp = (MyApplication) getApplication();
        myApp.robot().updatePosition(1, 1).updateFacing(Facing.NORTH);

        canvasTouchController = new CanvasTouchController(this, myApp);

        canvasView = findViewById(R.id.canvasView);
        canvasView.setGrid(myApp.grid());
        canvasView.setOnTouchListener(canvasTouchController);

        robotView = findViewById(R.id.robotView);
        robotView.setRobot(myApp.robot());

        bindUI();

        msgReceiver = new BluetoothMessageReceiver(BluetoothMessageParser.ofDefault(), this::onMsgReceived);
        getApplicationContext().registerReceiver(msgReceiver,
                new IntentFilter(BluetoothMessageReceiver.ACTION_MSG_READ), RECEIVER_NOT_EXPORTED);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        try {
            getApplicationContext().unregisterReceiver(msgReceiver);
        } catch (IllegalArgumentException e) {
            
        }
    }

    private void bindUI() {
        
        inputX = findViewById(R.id.inputX);
        inputY = findViewById(R.id.inputY);
        applyInputFilter(inputX);
        applyInputFilter(inputY);
        inputX.setText(String.valueOf(myApp.robot().getPosition().getXInt()));
        inputY.setText(String.valueOf(myApp.robot().getPosition().getYInt()));
        chatInputBox = findViewById(R.id.chatInputBox);

        receivedMessages = findViewById(R.id.ReceiveMsgTextView);
        robotStatusDynamic = findViewById(R.id.robotStatusDynamic);

        scrollReceivedMessages = findViewById(R.id.ReceiveMsgScrollView);

        spinnerRobotFacing = findViewById(R.id.spinnerRobotFacing);
        setupSpinner();

        Button btnSendData = findViewById(R.id.btnSendData);
        btnSendData.setOnClickListener(view -> sendData());
        Button btnInitializeRobot = findViewById(R.id.btnInitializeRobot);
        btnInitializeRobot.setOnClickListener(view -> initializeRobotFromInput());

        Button btnFastAdd = findViewById(R.id.btnFastAdd);
        if (btnFastAdd != null)
            btnFastAdd.setOnClickListener(view -> showFastAddDialog());

        Button btnSaveMap = findViewById(R.id.btnSaveMap);
        if (btnSaveMap != null)
            btnSaveMap.setOnClickListener(view -> saveMap());
        Button btnLoadMap = findViewById(R.id.btnLoadMap);
        if (btnLoadMap != null)
            btnLoadMap.setOnClickListener(view -> loadMap());
        Button btnClearMap = findViewById(R.id.btnClearMap);
        if (btnClearMap != null)
            btnClearMap.setOnClickListener(view -> {
                String currentStatus = robotStatusDynamic.getText().toString().toUpperCase();
                if (currentStatus.contains("RUNNING") || currentStatus.contains("MOVING")) {
                    Toast.makeText(this, "Cannot clear map while Robot is moving!", Toast.LENGTH_LONG).show();
                } else {
                    if (myApp.btConnection() != null) {
                        String strClear = "CLEAR";
                        myApp.btConnection().sendMessage(strClear);
                        logMessage("SENT", strClear, "#00BCD4");
                    }
                    myApp.grid().clear();
                    canvasView.invalidate();
                    Toast.makeText(this, "Map Cleared", Toast.LENGTH_SHORT).show();
                }
            });

        Button sendbtn = findViewById(R.id.btnSend);
        sendbtn.setOnClickListener(view -> sendChatMessage());
        Button startbtn = findViewById(R.id.btnRobotStart);
        startbtn.setOnClickListener(view -> {
            if (myApp.btConnection() != null)
                showConfirmationDialog();
        });

        findViewById(R.id.btnRobotForward).setOnClickListener(view -> {
            if (myApp.btConnection() != null)
                myApp.btConnection().sendMessage("f"); 
            myApp.robot().moveForward();
            robotView.invalidate();
        });
        findViewById(R.id.btnRobotBackward).setOnClickListener(view -> {
            if (myApp.btConnection() != null)
                myApp.btConnection().sendMessage("r");
            myApp.robot().moveBackward();
            robotView.invalidate();
        });

        findViewById(R.id.btnRobotRight).setOnClickListener(view -> {
            if (myApp.btConnection() != null)
                myApp.btConnection().sendMessage("tr");
            myApp.robot().rotateRight();
            robotView.invalidate();
        });
        findViewById(R.id.btnRobotLeft).setOnClickListener(view -> {
            if (myApp.btConnection() != null)
                myApp.btConnection().sendMessage("tl");
            myApp.robot().rotateLeft();
            robotView.invalidate();
        });

        findViewById(R.id.btnRobotArcRight).setOnClickListener(view -> {
            if (myApp.btConnection() != null)
                myApp.btConnection().sendMessage("fr");
            myApp.robot().turnRight();
            robotView.invalidate();
        });
        findViewById(R.id.btnRobotArcLeft).setOnClickListener(view -> {
            if (myApp.btConnection() != null)
                myApp.btConnection().sendMessage("fl");
            myApp.robot().turnLeft();
            robotView.invalidate();
        });

        layoutMapMode = findViewById(R.id.layoutMapMode);
        layoutLogMode = findViewById(R.id.layoutLogMode);
        tabLayout = findViewById(R.id.tabLayout);

        tabLayout.addOnTabSelectedListener(new TabLayout.OnTabSelectedListener() {
            @Override
            public void onTabSelected(TabLayout.Tab tab) {
                if (tab.getPosition() == 0) {
                    
                    layoutMapMode.setVisibility(View.VISIBLE);
                    layoutLogMode.setVisibility(View.GONE);
                } else {
                    
                    layoutMapMode.setVisibility(View.GONE);
                    layoutLogMode.setVisibility(View.VISIBLE);
                }
            }

            @Override
            public void onTabUnselected(TabLayout.Tab tab) {
            }

            @Override
            public void onTabReselected(TabLayout.Tab tab) {
            }
        });
    }

    private void startRobot() {
        if (myApp.btConnection() != null) {
            myApp.btConnection().sendMessage("BEGIN");
            logMessage("SENT", "BEGIN", "#00BCD4");
        }
        for (GridObstacle obstacle : myApp.grid().getObstacleList()) {
            obstacle.setTarget(null);
        }
        canvasView.invalidate();
    }

    private void showConfirmationDialog() {
        new AlertDialog.Builder(this)
                .setTitle("Confirm Start")
                .setMessage("Are you sure you want to start the robot?")
                .setPositiveButton("Confirm", (dialog, which) -> startRobot())
                .setNegativeButton("Cancel", (dialog, which) -> dialog.dismiss())
                .show();
    }

    private void sendData() {
        if (myApp.btConnection() == null) {
            Toast.makeText(CanvasActivity.this, "Error: No Bluetooth Connection", Toast.LENGTH_SHORT).show();
            return;
        }
        BluetoothMessage msg = BluetoothMessage.ofObstaclesMessage(this.myApp.grid().getObstacleList());
        String msgStr = msg.getAsJsonMessage().getAsJson();
        myApp.btConnection().sendMessage(msgStr);
        logMessage("SENT", msgStr, "#00BCD4");
        Toast.makeText(CanvasActivity.this, "Data sent successfully", Toast.LENGTH_SHORT).show();
    }

    private void saveMap() {
        SharedPreferences store = getSharedPreferences("ObstaclePrefs", MODE_PRIVATE);
        JSONArray obstacleArray = new JSONArray();
        
        myApp.grid().getObstacleList().forEach(obstacle -> {
            try {
                JSONObject jsonObstacle = new JSONObject();
                jsonObstacle.put("id", obstacle.getObstacleId());
                jsonObstacle.put("x", obstacle.getPosition().getXInt());
                jsonObstacle.put("y", obstacle.getPosition().getYInt());
                jsonObstacle.put("facing", obstacle.getFacing().name());
                obstacleArray.put(jsonObstacle);
            } catch (JSONException ex) {
                Log.e(TAG, "Exception during grid serialization", ex);
            }
        });
        
        store.edit().putString("saved_obstacles", obstacleArray.toString()).apply();
        Toast.makeText(this, String.format("Map preserved! (%d obstacles)", obstacleArray.length()), Toast.LENGTH_SHORT).show();
    }

    private void loadMap() {
        String botStatus = robotStatusDynamic.getText().toString().toUpperCase();
        if (botStatus.contains("RUNNING") || botStatus.contains("MOVING")) {
            Toast.makeText(this, "Action blocked: Robot is currently active!", Toast.LENGTH_LONG).show();
            return;
        }

        SharedPreferences store = getSharedPreferences("ObstaclePrefs", MODE_PRIVATE);
        String gridDataStr = store.getString("saved_obstacles", "[]");
        
        try {
            JSONArray obstacleArray = new JSONArray(gridDataStr);

            if (myApp.btConnection() != null) {
                String cmdClear = "CLEAR";
                myApp.btConnection().sendMessage(cmdClear);
                logMessage("SENT", cmdClear, "#00BCD4");
            }
            myApp.grid().clear();

            for (int idx = 0; idx < obstacleArray.length(); idx++) {
                JSONObject parsedObj = obstacleArray.getJSONObject(idx);
                int coordX = parsedObj.getInt("x");
                int coordY = parsedObj.getInt("y");
                Facing dir = convertFacing(parsedObj.getString("facing"));

                GridObstacle gridElement = GridObstacle.of(coordX, coordY, dir);
                myApp.grid().addObstacle(gridElement);

                if (myApp.btConnection() != null) {
                    BluetoothMessage payload = BluetoothMessage.ofObstacleEventMessage(gridElement.getObstacleId(), coordX, coordY, dir, false);
                    String payloadStr = payload.getAsJsonMessage().getAsJson();
                    myApp.btConnection().sendMessage(payloadStr);
                    logMessage("SENT", payloadStr, "#00BCD4");
                }
            }
            canvasView.invalidate();
            Toast.makeText(this, String.format("Map restored! (%d obstacles)", obstacleArray.length()), Toast.LENGTH_SHORT).show();
        } catch (JSONException ex) {
            Log.e(TAG, "Exception during grid deserialization", ex);
            Toast.makeText(this, "Map load failed.", Toast.LENGTH_SHORT).show();
        }
    }

    private void showFastAddDialog() {
        AlertDialog.Builder dialogBuilder = new AlertDialog.Builder(this);
        dialogBuilder.setTitle("Bulk Add Obstacles");

        final EditText textInput = new EditText(this);
        textInput.setHint("Format: X Y DIR (e.g. 1 2 N\n3 4 E)");
        textInput.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        textInput.setMinLines(5);
        textInput.setGravity(android.view.Gravity.TOP | android.view.Gravity.START);

        android.widget.FrameLayout layoutContainer = new android.widget.FrameLayout(this);
        android.widget.FrameLayout.LayoutParams layoutParams = new android.widget.FrameLayout.LayoutParams(
                android.view.ViewGroup.LayoutParams.MATCH_PARENT,
                android.view.ViewGroup.LayoutParams.WRAP_CONTENT);
                
        int marginCalc = (int) (20 * getResources().getDisplayMetrics().density);
        layoutParams.setMargins(marginCalc, marginCalc, marginCalc, marginCalc);
        textInput.setLayoutParams(layoutParams);
        layoutContainer.addView(textInput);

        dialogBuilder.setView(layoutContainer);

        dialogBuilder.setPositiveButton("Add", (dialog, which) -> {
            String rawInputData = textInput.getText().toString();
            processFastAdd(rawInputData);
        });
        dialogBuilder.setNegativeButton("Cancel", (dialog, which) -> dialog.cancel());

        dialogBuilder.show();
    }

    private void processFastAdd(String rawText) {
        String botStatus = robotStatusDynamic.getText().toString().toUpperCase();
        if (botStatus.contains("RUNNING") || botStatus.contains("MOVING")) {
            Toast.makeText(this, "Action blocked: Robot is moving!", Toast.LENGTH_LONG).show();
            return;
        }

        String[] inputLines = rawText.split("\n");
        int additionCount = 0;
        int skipCount = 0;
        
        for (String singleLine : inputLines) {
            String sanitizedLine = singleLine.trim();
            if (sanitizedLine.isEmpty()) continue;
            
            String[] tokens = sanitizedLine.split("[\\s,]+");
            if (tokens.length >= 2) {
                try {
                    int coordX = Integer.parseInt(tokens[0]);
                    int coordY = Integer.parseInt(tokens[1]);
                    Facing designatedFacing = Facing.NORTH;
                    
                    if (tokens.length >= 3) {
                        String fDir = tokens[2].toUpperCase();
                        designatedFacing = switch (fDir.charAt(0)) {
                            case 'N' -> Facing.NORTH;
                            case 'S' -> Facing.SOUTH;
                            case 'E' -> Facing.EAST;
                            case 'W' -> Facing.WEST;
                            default -> convertFacing(fDir);
                        };
                    }
                    
                    if (myApp.grid().isInsideGrid(coordX, coordY)) {
                        if (!myApp.grid().hasObstacle(coordX, coordY)) {
                            GridObstacle placementObs = GridObstacle.of(coordX, coordY, designatedFacing);
                            myApp.grid().addObstacle(placementObs);
                            additionCount++;
                            
                            if (myApp.btConnection() != null) {
                                BluetoothMessage generatedMsg = BluetoothMessage.ofObstacleEventMessage(placementObs.getObstacleId(), coordX, coordY, designatedFacing, false);
                                String generatedStr = generatedMsg.getAsJsonMessage().getAsJson();
                                myApp.btConnection().sendMessage(generatedStr);
                                logMessage("SENT", generatedStr, "#00BCD4");
                            }
                        } else {
                            skipCount++;
                        }
                    }
                } catch (NumberFormatException ex) {
                    Log.e(TAG, "Error parsing details: " + sanitizedLine, ex);
                }
            }
        }
        canvasView.invalidate();
        String summary = String.format("Injected %d obstacles.", additionCount);
        if (skipCount > 0) summary += String.format(" Skipped %d points.", skipCount);
        Toast.makeText(this, summary, Toast.LENGTH_SHORT).show();
    }

    private void applyInputFilter(EditText input) {
        InputFilter minMaxFilter = new InputFilter() {
            @Override
            public CharSequence filter(CharSequence source, int start, int end, Spanned dest, int dstart, int dend) {
                try {
                    int inputVal = Integer.parseInt(dest.toString() + source.toString());
                    if (inputVal >= 1 && inputVal <= 3)
                        return null;
                } catch (NumberFormatException e) {
                    return "";
                }
                return "";
            }
        };
        input.setFilters(new InputFilter[] { minMaxFilter });
    }

    private void setupSpinner() {
        ArrayAdapter<CharSequence> adapter = ArrayAdapter.createFromResource(
                this,
                R.array.robot_facing_options,
                android.R.layout.simple_spinner_item);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        spinnerRobotFacing.setAdapter(adapter);
        spinnerRobotFacing.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                selectedFacing = parent.getItemAtPosition(position).toString();
                Toast.makeText(CanvasActivity.this, "Selected: " + selectedFacing, Toast.LENGTH_SHORT).show();
            }

            @Override
            public void onNothingSelected(AdapterView<?> parent) {
            }
        });
    }

    private void sendChatMessage() {
        String message = chatInputBox.getText().toString().trim();

        if (!message.isEmpty()) {
            myApp.btConnection().sendMessage(message); 
            logMessage("SENT", message, "#00BCD4");
            chatInputBox.setText(""); 
            Toast.makeText(this, "Message sent: " + message, Toast.LENGTH_SHORT).show();
        } else {
            Toast.makeText(this, "Please enter a message", Toast.LENGTH_SHORT).show();
        }
    }

    private void initializeRobotFromInput() {
        if (inputX.getText().toString().isEmpty() || inputY.getText().toString().isEmpty()) {
            Toast.makeText(getApplicationContext(), "Please enter both X and Y values.", Toast.LENGTH_SHORT).show();
            return;
        }

        int x = Integer.parseInt(inputX.getText().toString());
        int y = Integer.parseInt(inputY.getText().toString());
        facingDirection = convertFacing(selectedFacing);

        initializeRobot(x, y, facingDirection);
    }

    private void initializeRobot(int x, int y, Facing facing) {
        myApp.robot().updatePosition(x, y);
        myApp.robot().updateFacing(facing);

        if (myApp.btConnection() != null) {
            BluetoothMessage msg = BluetoothMessage.ofRobotStateMessage(x, y, facing);
            String msgStr = msg.getAsJsonMessage().getAsJson();
            myApp.btConnection().sendMessage(msgStr);
            logMessage("SENT", msgStr, "#00BCD4");
        }

        robotView.invalidate();
    }

    private Facing convertFacing(String facing) {
        switch (facing.toUpperCase()) {
            case "NORTH":
                return Facing.NORTH;
            case "SOUTH":
                return Facing.SOUTH;
            case "EAST":
                return Facing.EAST;
            case "WEST":
                return Facing.WEST;
            default:
                return Facing.NORTH;
        }
    }

    private void onMsgReceived(BluetoothMessage btMsg) {
        if (btMsg instanceof BluetoothMessage.PlainStringMessage m) {
            
            logMessage("RECV", m.rawMsg(), "#4CAF50");
        } else if (btMsg instanceof BluetoothMessage.RobotStatusMessage m) {
            
            robotStatusDynamic.setText(m.status().toUpperCase());
            logMessage("RECV", "[status] " + m.rawMsg(), "#4CAF50");
        } else if (btMsg instanceof BluetoothMessage.TargetFoundMessage m) {
            
            String targetStatus = String.format("TARGET %d AT OBS %d", m.targetId(), m.obstacleId());
            robotStatusDynamic.setText(targetStatus);

            myApp.grid().updateObstacleTarget(m.obstacleId(), m.targetId());
            
            if (m.direction() != -1) {
                myApp.grid().locateObstacleById(m.obstacleId())
                        .ifPresent(obs -> obs.setFacing(Facing.getFacingFromCode(m.direction())));
            }
            canvasView.invalidate();
            logMessage("RECV", "[image-rec] " + m.rawMsg(), "#4CAF50");
        } else if (btMsg instanceof BluetoothMessage.RobotPositionMessage m) {
            
            String dirStr = switch (m.direction()) {
                case 1 -> "N";
                case 2 -> "E";
                case 3 -> "S";
                case 4 -> "W";
                default -> "?";
            };
            robotStatusDynamic.setText(String.format("MOVING TO (%d, %d, %s)", m.x(), m.y(), dirStr));

            myApp.robot().updatePosition(m.x(), m.y()).updateFacing(Facing.getFacingFromCode(m.direction()));
            robotView.invalidate();
            logMessage("RECV", "[location] " + m.rawMsg(), "#4CAF50");
        }
    }

}