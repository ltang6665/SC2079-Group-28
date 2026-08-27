import React from "react";
import { useState, useEffect } from "react";
import QueryAPI from "./QueryAPI";

const Direction = {
  NORTH: 0,
  NORTHEAST: 1,
  EAST: 2,
  SOUTHEAST: 3,
  SOUTH: 4,
  SOUTHWEST: 5,
  WEST: 6,
  NORTHWEST: 7,
  SKIP: 8,
};

const ObDirection = {
  NORTH: 0,
  EAST: 2,
  SOUTH: 4,
  WEST: 6,
  SKIP: 8,
};

const DirectionToString = {
  0: "Up",
  1: "Up-Right",
  2: "Right",
  3: "Down-Right",
  4: "Down",
  5: "Down-Left",
  6: "Left",
  7: "Up-Left",
  8: "None",
};

const transformCoord = (x, y) => {
  // Change the coordinate system from (0, 0) at top left to (0, 0) at bottom left
  return { x: 19 - y, y: x };
};



export default function Simulator() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [robotState, setRobotState] = useState({
    x: 1,
    y: 1,
    d: Direction.NORTH,
    s: -1,
  });
  const [robotX, setRobotX] = useState(1);
  const [robotY, setRobotY] = useState(1);
  const [robotDir, setRobotDir] = useState(0);
  const [obstacles, setObstacles] = useState([]);
  const [obXInput, setObXInput] = useState(0);
  const [obYInput, setObYInput] = useState(0);
  const [directionInput, setDirectionInput] = useState(ObDirection.NORTH);
  const [isComputing, setIsComputing] = useState(false);
  const [path, setPath] = useState([]);
  const [commands, setCommands] = useState([]);
  const [commandTimes, setCommandTimes] = useState([]);
  const [page, setPage] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const [startTime, setStartTime] = useState(null);
  const [trail, setTrail] = useState([]);
  const [timeLimit, setTimeLimit] = useState(0);
  const [timeLimitInput, setTimeLimitInput] = useState(0);
  const [message, setMessage] = useState(null);
  const [calcTime, setCalcTime] = useState(null);


  const [savedTrails, setSavedTrails] = useState([]);
  const [trailName, setTrailName] = useState("");
  const [activeTrail, setActiveTrail] = useState(null);
  const [dragItem, setDragItem] = useState(null);


  // --- Trail Save/Recall Functions ---
  function saveCurrentTrail(name) {
    const snapshot = {
      name: name || `Trail ${savedTrails.length + 1}`,
      obstacles: obstacles.map((o) => ({ ...o })),
      trail: trail.map((t) => ({ ...t })),
      path: path.map((p) => ({ ...p })),
      commands: commands.slice(),                // commands for display
      commandTimes: commandTimes.slice(),        // times for step timing
      robot: { ...robotState }
    };
    setSavedTrails([...savedTrails, snapshot]);
  }

  function recallTrail(snapshot) {
    setActiveTrail(snapshot);
    setPath(snapshot.path || []);
    setCommands(snapshot.commands || []);
    setCommandTimes(snapshot.commandTimes || []);
    if (snapshot.robot) setRobotState(snapshot.robot);
    setPage(0);  // reset to start of run
    setTrail([]);
}


  function showCurrentRun() {
    setActiveTrail(null);
  }

  const generateNewID = () => {
    while (true) {
      let new_id = Math.floor(Math.random() * 10) + 1; // just try to generate an id;
      let ok = true;
      for (const ob of obstacles) {
        if (ob.id === new_id) {
          ok = false;
          break;
        }
      }
      if (ok) {
        return new_id;
      }
    }
  };

  const generateRobotCells = () => {
    const robotCells = [];
    let markerX = 0;
    let markerY = 0;

    if (robotState.d === Direction.NORTH) {
      markerY++;
    } else if (robotState.d === Direction.NORTHEAST) {
      markerX++;
      markerY++;
    } else if (robotState.d === Direction.EAST) {
      markerX++;
    } else if (robotState.d === Direction.SOUTHEAST) {
      markerX++;
      markerY--;
    } else if (robotState.d === Direction.SOUTH) {
      markerY--;
    } else if (robotState.d === Direction.SOUTHWEST) {
      markerX--;
      markerY--;
    } else if (robotState.d === Direction.WEST) {
      markerX--;
    } else if (robotState.d === Direction.NORTHWEST) {
      markerX--;
      markerY++;
    }


    // Go from i = -1 to i = 1
    for (let i = -1; i < 2; i++) {
      // Go from j = -1 to j = 1
      for (let j = -1; j < 2; j++) {
        // Transform the coordinates to our coordinate system where (0, 0) is at the bottom left
        const coord = transformCoord(robotState.x + i, robotState.y + j);
        // If the cell is the marker cell, add the robot state to the cell
        if (markerX === i && markerY === j) {
          robotCells.push({
            x: coord.x,
            y: coord.y,
            d: robotState.d,
            s: robotState.s,
          });
        } else {
          robotCells.push({
            x: coord.x,
            y: coord.y,
            d: null,
            s: -1,
          });
        }
      }
    }

    return robotCells;
  };

  const onChangeX = (event) => {
    // If the input is an integer and is in the range [0, 19], set ObXInput to the input
    if (Number.isInteger(Number(event.target.value))) {
      const nb = Number(event.target.value);
      if (0 <= nb && nb < 20) {
        setObXInput(nb);
        return;
      }
    }
    // If the input is not an integer or is not in the range [0, 19], set the input to 0
    setObXInput(0);
  };

  const onChangeY = (event) => {
    // If the input is an integer and is in the range [0, 19], set ObYInput to the input
    if (Number.isInteger(Number(event.target.value))) {
      const nb = Number(event.target.value);
      if (0 <= nb && nb <= 19) {
        setObYInput(nb);
        return;
      }
    }
    // If the input is not an integer or is not in the range [0, 19], set the input to 0
    setObYInput(0);
  };

  const onChangeRobotX = (event) => {
    // If the input is an integer and is in the range [1, 18], set RobotX to the input
    if (Number.isInteger(Number(event.target.value))) {
      const nb = Number(event.target.value);
      if (1 <= nb && nb < 19) {
        setRobotX(nb);
        return;
      }
    }
    // If the input is not an integer or is not in the range [1, 18], set the input to 1
    setRobotX(1);
  };

  const onChangeRobotY = (event) => {
    // If the input is an integer and is in the range [1, 18], set RobotY to the input
    if (Number.isInteger(Number(event.target.value))) {
      const nb = Number(event.target.value);
      if (1 <= nb && nb < 19) {
        setRobotY(nb);
        return;
      }
    }
    // If the input is not an integer or is not in the range [1, 18], set the input to 1
    setRobotY(1);
  };

  const onClickObstacle = () => {
    // If the input is not valid, return
    if (!obXInput && !obYInput) return;
    // Create a new array of obstacles
    const newObstacles = [...obstacles];
    // Add the new obstacle to the array
    newObstacles.push({
      x: obXInput,
      y: obYInput,
      d: directionInput,
      id: generateNewID(),
    });
    // Set the obstacles to the new array
    setObstacles(newObstacles);
  };

  const clearComputedResults = () => {
    setPath([]);
    setCommands([]);
    setCommandTimes([]);
    setPage(0);
    setIsRunning(false);
    setStartTime(null);
    setTrail([]);
    setMessage(null);
    setActiveTrail(null);
  };

  const onDragStartObstacle = (ob) => {
    if (isComputing) return;
    setDragItem({ type: "obstacle", id: ob.id });
  };

  const onDragStartRobot = () => {
    if (isComputing) return;
    setDragItem({ type: "robot" });
  };

  const onDragOverCell = (event) => {
    event.preventDefault();
  };

  const onDropCell = (event, row, col) => {
    event.preventDefault();
    if (!dragItem || isComputing) return;

    // Inverse of transformCoord(x,y) => {x:19-y, y:x}
    const targetX = col;
    const targetY = 19 - row;

    if (dragItem.type === "obstacle") {
      // Obstacles stay in [0,19]
      if (targetX < 0 || targetX > 19 || targetY < 0 || targetY > 19) {
        setDragItem(null);
        return;
      }

      // Avoid overlapping another obstacle
      const occupied = obstacles.some(
        (ob) => ob.id !== dragItem.id && ob.x === targetX && ob.y === targetY
      );
      if (occupied) {
        setDragItem(null);
        return;
      }

      setObstacles((prev) =>
        prev.map((ob) =>
          ob.id === dragItem.id ? { ...ob, x: targetX, y: targetY } : ob
        )
      );
      clearComputedResults();
    } else if (dragItem.type === "robot") {
      // Robot center stays in [1,18] so 3x3 footprint remains in board
      if (targetX < 1 || targetX > 18 || targetY < 1 || targetY > 18) {
        setDragItem(null);
        return;
      }

      setRobotX(targetX);
      setRobotY(targetY);
      setRobotState((prev) => ({ ...prev, x: targetX, y: targetY, s: -1 }));
      clearComputedResults();
    }

    setDragItem(null);
  };

  const cycleObstacleDirection = (obstacleId) => {
    if (isComputing) return;
    const order = [Direction.NORTH, Direction.EAST, Direction.SOUTH, Direction.WEST];
    setObstacles((prev) =>
      prev.map((ob) => {
        if (ob.id !== obstacleId) return ob;
        const idx = order.indexOf(ob.d);
        const next = idx === -1 ? Direction.NORTH : order[(idx + 1) % order.length];
        return { ...ob, d: next };
      })
    );
    clearComputedResults();
  };

  const cycleRobotDirection = () => {
    if (isComputing) return;
    const order = [Direction.NORTH, Direction.EAST, Direction.SOUTH, Direction.WEST];
    const idx = order.indexOf(Number(robotDir));
    const next = idx === -1 ? Direction.NORTH : order[(idx + 1) % order.length];
    setRobotDir(next);
    setRobotState((prev) => ({ ...prev, d: next }));
    clearComputedResults();
  };

  const addObstacleAtCell = (row, col) => {
    if (isComputing) return;
    const x = col;
    const y = 19 - row;
    // Don't place on top of existing obstacle
    if (obstacles.some((ob) => ob.x === x && ob.y === y)) return;
    setObstacles((prev) => [
      ...prev,
      { x, y, d: directionInput, id: generateNewID() },
    ]);
    clearComputedResults();
  };

  const onClickRobot = () => {
    // Set the robot state to the input
    setRobotState({ x: robotX, y: robotY, d: robotDir, s: -1 });
  };

  const onDirectionInputChange = (event) => {
    // Set the direction input to the input
    setDirectionInput(Number(event.target.value));
  };

  const onRobotDirectionInputChange = (event) => {
    // Set the robot direction to the input
    setRobotDir(event.target.value);
  };

  const onRemoveObstacle = (ob) => {
    // If the path is not empty or the algorithm is computing, return
    if (path.length > 0 || isComputing) return;
    // Create a new array of obstacles
    const newObstacles = [];
    // Add all the obstacles except the one to remove to the new array
    for (const o of obstacles) {
      if (o.x === ob.x && o.y === ob.y) continue;
      newObstacles.push(o);
    }
    // Set the obstacles to the new array
    setObstacles(newObstacles);
  };

  const compute = () => {
    // Set computing to true, act like a lock
    setIsComputing(true);
    setMessage(null);
    setCalcTime(null);
    const computeStart = Date.now();

    // Call the query function from the API
    QueryAPI.query(obstacles, robotX, robotY, robotDir, (resp, err) => {
      // QueryAPI uses a { data, error } envelope
      const envelope = resp || {};
      const payload = envelope.data;
      const envelopeErr = envelope.error || err;

      if (!payload) {
        const msg = envelopeErr
          ? `Pathfinding request failed: ${String(envelopeErr)}`
          : "Pathfinding request failed: empty response.";
        setMessage(msg);
        setIsComputing(false);
        return;
      }

      // If the data is valid, set the path
      setPath(payload.path || []);

      // Set the commands and times, filtering out SNAP commands
      const commands = [];
      const times = [];
      const cmdList = payload.commands || [];
      const timeList = payload.time || [];
      for (let i = 0; i < cmdList.length; i++) {
        if (!cmdList[i].startsWith("SNAP")) {
          commands.push(cmdList[i]);
          times.push(timeList[i]);
        }
      }
      setCommands(commands);
      setCommandTimes(times);

      // Set computing to false, release the lock
      setCalcTime(((Date.now() - computeStart) / 1000).toFixed(2));
      setIsComputing(false);
    });
  };

  const onResetAll = () => {
    // Reset all the states
    setRobotX(1);
    setRobotDir(0);
    setRobotY(1);
    setRobotState({ x: 1, y: 1, d: Direction.NORTH, s: -1 });
    setPath([]);
    setCommands([]);
    setCommandTimes([]);
    setPage(0);
    setObstacles([]);
    setIsRunning(false);
    setStartTime(null);
    setTrail([]);
    setActiveTrail(null);
    setMessage(null);
  };

  const onReset = () => {
    // Reset all the states
    setRobotX(1);
    setRobotDir(0);
    setRobotY(1);
    setRobotState({ x: 1, y: 1, d: Direction.NORTH, s: -1 });
    setPath([]);
    setCommands([]);
    setCommandTimes([]);
    setPage(0);
    setMessage(null);
  };
  
  const renderObstacleCell = (foundOb, i, j, extraClass = "") => (
  <td
    key={`ob-${foundOb.id}-${i}-${j}`}
    draggable={!isComputing}
    onDragStart={() => onDragStartObstacle(foundOb)}
    onDragOver={onDragOverCell}
    onDrop={(e) => onDropCell(e, i, j)}
    onClick={() => cycleObstacleDirection(foundOb.id)}
    className={`relative group border-2 border-gray-400 w-5 h-5 md:w-8 md:h-8 bg-black ${extraClass}`}
  >
    <div className="absolute left-1/2 top-0 z-20 -translate-x-1/2 -translate-y-full mb-1 hidden group-hover:block pointer-events-none">
      <div className="whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-xs text-white shadow-lg">
        ({foundOb.x}, {foundOb.y})
      </div>
    </div>
  </td>
);

  const renderGrid = () => {
    // Initialize the empty rows array
    const rows = [];

    const obstaclesToRender = activeTrail ? activeTrail.obstacles : obstacles;
    const trailToRender = trail;


    const baseStyle = {
      width: 25,
      height: 25,
      borderStyle: "solid",
      borderTopWidth: 1,
      borderBottomWidth: 1,
      borderLeftWidth: 1,
      borderRightWidth: 1,
      padding: 0,
    };

    // Generate robot cells
    const robotCells = generateRobotCells();

    // Generate the grid
    for (let i = 0; i < 20; i++) {
      const cells = [
        // Header cells
        <td key={i} className="w-5 h-5 md:w-8 md:h-8">
          <span className="text-white font-bold text-[0.6rem] md:text-base ">
            {19 - i}
          </span>
        </td>,
      ];

      for (let j = 0; j < 20; j++) {
        let foundOb = null;
        let foundRobotCell = null;

        // check obstacles
        for (const ob of obstaclesToRender) {
          const transformed = transformCoord(ob.x, ob.y);
          if (transformed.x === i && transformed.y === j) {
            foundOb = ob;
            break;
          }
        }

        // check robot
        if (!foundOb) {
          for (const cell of robotCells) {
            if (cell.x === i && cell.y === j) {
              foundRobotCell = cell;
              break;
            }
          }
        }

        // check trail
        let foundTrail = trailToRender.find(
          (t) =>
            transformCoord(t.x, t.y).x === i &&
            transformCoord(t.x, t.y).y === j
        );

        // --- PRIORITY ORDER ---
        // 1. Robot (always on top of trail)
        if (foundRobotCell) {
          if (foundRobotCell.d !== null) {
            cells.push(
              <td
                draggable={!isComputing}
                onDragStart={onDragStartRobot}
                onDragOver={onDragOverCell}
                onDrop={(e) => onDropCell(e, i, j)}
                onClick={cycleRobotDirection}
                className={`border-2 border-gray-400 w-5 h-5 md:w-8 md:h-8 ${
                  foundRobotCell.s != -1 ? "bg-rose-500" : "bg-cyan-400"
                }`}
              />
            );
          } else {
            cells.push(
              <td
                draggable={!isComputing}
                onDragStart={onDragStartRobot}
                onDragOver={onDragOverCell}
                onDrop={(e) => onDropCell(e, i, j)}
                onClick={cycleRobotDirection}
                className="bg-green-600 border-2 border-gray-400 w-5 h-5 md:w-8 md:h-8"
              />
            );
          }
        }
        // 2. Obstacle
        else if (foundOb) {
          if (foundOb.d === Direction.WEST) {
            cells.push(
              <td
                draggable={!isComputing}
                onDragStart={() => onDragStartObstacle(foundOb)}
                onDragOver={onDragOverCell}
                onDrop={(e) => onDropCell(e, i, j)}
                onClick={() => cycleObstacleDirection(foundOb.id)}
                className="border-2 border-gray-400 border-l-4 border-l-red-500 w-5 h-5 md:w-8 md:h-8 bg-black"
              />
            );
          } else if (foundOb.d === Direction.EAST) {
            cells.push(
              <td
                draggable={!isComputing}
                onDragStart={() => onDragStartObstacle(foundOb)}
                onDragOver={onDragOverCell}
                onDrop={(e) => onDropCell(e, i, j)}
                onClick={() => cycleObstacleDirection(foundOb.id)}
                className="border-2 border-gray-400 border-r-4 border-r-red-500 w-5 h-5 md:w-8 md:h-8 bg-black"
              />
            );
          } else if (foundOb.d === Direction.NORTH) {
            cells.push(
              <td
                draggable={!isComputing}
                onDragStart={() => onDragStartObstacle(foundOb)}
                onDragOver={onDragOverCell}
                onDrop={(e) => onDropCell(e, i, j)}
                onClick={() => cycleObstacleDirection(foundOb.id)}
                className="border-2 border-gray-400 border-t-4 border-t-red-500 w-5 h-5 md:w-8 md:h-8 bg-black"
              />
            );
          } else if (foundOb.d === Direction.SOUTH) {
            cells.push(
              <td
                draggable={!isComputing}
                onDragStart={() => onDragStartObstacle(foundOb)}
                onDragOver={onDragOverCell}
                onDrop={(e) => onDropCell(e, i, j)}
                onClick={() => cycleObstacleDirection(foundOb.id)}
                className="border-2 border-gray-400 border-b-4 border-b-red-500 w-5 h-5 md:w-8 md:h-8 bg-black"
              />
            );
          } else if (foundOb.d === Direction.SKIP) {
            cells.push(
              <td
                draggable={!isComputing}
                onDragStart={() => onDragStartObstacle(foundOb)}
                onDragOver={onDragOverCell}
                onDrop={(e) => onDropCell(e, i, j)}
                onClick={() => cycleObstacleDirection(foundOb.id)}
                className="border-2 border-gray-400 w-5 h-5 md:w-8 md:h-8 bg-black"
              />
            );
          }
        }
        // 3. Trail
        else if (foundTrail) {
          cells.push(
            <td
              onDragOver={onDragOverCell}
              onDrop={(e) => onDropCell(e, i, j)}
              onClick={() => addObstacleAtCell(i, j)}
              className="bg-yellow-300 border-2 border-gray-400 w-5 h-5 md:w-8 md:h-8 cursor-pointer"
            />
          );
        }
        // 4. Empty cell
        else {
          cells.push(
            <td
              onDragOver={onDragOverCell}
              onDrop={(e) => onDropCell(e, i, j)}
              onClick={() => addObstacleAtCell(i, j)}
              className="border-2 border-gray-400 w-5 h-5 md:w-8 md:h-8 cursor-pointer"
            />
          );
        }
      }

      rows.push(<tr key={19 - i}>{cells}</tr>);
    }

    const yAxis = [<td key={0} />];
    for (let i = 0; i < 20; i++) {
      yAxis.push(
        <td className="w-5 h-5 md:w-8 md:h-8">
          <span className="text-white font-bold text-[0.6rem] md:text-base ">
            {i}
          </span>
        </td>
      );
    }
    rows.push(<tr key={20}>{yAxis}</tr>);
    return rows;
  };

useEffect(() => {
  if (page >= path.length) return;

  const current = path[page];
  const prev = page > 0 ? path[page - 1] : current;

  // update robot position
  setRobotState(current);

  let newTrail = [];

  // Rebuild trail from start up to current step
  for (let i = 1; i <= page; i++) {
    const from = path[i - 1];
    const to = path[i];

    // use path directly (already center)
    const centerFrom = { x: from.x, y: from.y };
    const centerTo = { x: to.x, y: to.y };

    const dx = centerTo.x - centerFrom.x;
    const dy = centerTo.y - centerFrom.y;

      // horizontal move
      if (dy === 0 && dx !== 0) {
        const step = dx > 0 ? 1 : -1;
        for (let x = centerFrom.x; x !== centerTo.x + step; x += step) {
          newTrail.push({ x, y: centerFrom.y });
        }
      }
      // vertical move
      else if (dx === 0 && dy !== 0) {
        const step = dy > 0 ? 1 : -1;
        for (let y = centerFrom.y; y !== centerTo.y + step; y += step) {
          newTrail.push({ x: centerFrom.x, y });
        }
      }
      // turn (L-shape)
      // diagonal move (perfect 45°)
      else if (dx !== 0 && dy !== 0 && Math.abs(dx) === Math.abs(dy)) {
        const stepX = dx > 0 ? 1 : -1;
        const stepY = dy > 0 ? 1 : -1;
        let x = centerFrom.x;
        let y = centerFrom.y;
        while (x !== centerTo.x + stepX && y !== centerTo.y + stepY) {
          newTrail.push({ x, y });
          x += stepX;
          y += stepY;
        }
      }
      // fallback for non-45° moves (draw like an L-shape)
      else if (dx !== 0 && dy !== 0) {
        const stepX = dx > 0 ? 1 : -1;
        for (let x = centerFrom.x; x !== centerTo.x + stepX; x += stepX) {
          newTrail.push({ x, y: centerFrom.y });
        }
        const stepY = dy > 0 ? 1 : -1;
        for (let y = centerFrom.y; y !== centerTo.y + stepY; y += stepY) {
          newTrail.push({ x: centerTo.x, y });
        }
      }
      // else if (dx !== 0 && dy !== 0) {
      //   const stepX = dx > 0 ? 1 : -1;
      //   for (let x = centerFrom.x; x !== centerTo.x + stepX; x += stepX) {
      //     newTrail.push({ x, y: centerFrom.y });
      //   }
      //   const stepY = dy > 0 ? 1 : -1;
      //   for (let y = centerFrom.y; y !== centerTo.y + stepY; y += stepY) {
      //     newTrail.push({ x: centerTo.x, y });
      //   }
      // }

    }

    setTrail(newTrail);
  }, [page, path]);

  useEffect(() => {
    let interval;
    if (isRunning && page < path.length - 1) {
      const nextStepCumulativeTime = getCumulativeTime(page + 1);
      if (timeLimit > 0 && nextStepCumulativeTime > timeLimit) {
       setIsRunning(false);
       setMessage(`Time limit of ${timeLimit}s will be exceeded. The robot has stopped.`);
        return;
      }
      interval = setInterval(() => {
        setPage((prev) => prev + 1);   // auto advance steps
      }, 500); // adjust ms per step
    } else if (isRunning && page === path.length - 1) {
      setIsRunning(false);
    }
    return () => clearInterval(interval);
  }, [isRunning, page, path, startTime]);


  // Function to calculate cumulative time up to a given step
  const getCumulativeTime = (stepIndex) => {
    // Return 0 for the first step
    if (stepIndex <= 0) {
        return 0;
    }
    let totalTime = 0;
    // Sum times for all previous commands
    for (let i = 0; i < stepIndex && i < commandTimes.length; i++) {
      totalTime += commandTimes[i];
    }
    return totalTime;
  };

  // Handler for time limit input
  const onChangeTimeLimit = (event) => {
    const value = Number(event.target.value);
    if (!isNaN(value) && value >= 0) {
      setTimeLimitInput(value);
    }
  };

  const onClickTimeLimit = () => {
    setTimeLimit(timeLimitInput);
    setMessage(`Time limit set to ${timeLimitInput}s.`);
  };


  return (
      <div className="flex flex-row h-screen bg-base-100 text-base-content overflow-hidden">
      {/* LEFT SETTINGS PANEL */}
      <div
        className={`relative h-full bg-base-100 shadow-xl overflow-y-auto transition-all duration-300 ease-in-out ${
          isSidebarOpen ? "w-[480px] p-6" : "w-16 p-2"
        }`}
      >
        {/* Toggle button */}
        <button
          onClick={() => setIsSidebarOpen((prev) => !prev)}
          className="btn btn-sm absolute top-4 right-2 z-10"
        >
          {isSidebarOpen ? "<" : ">"}
        </button>

        {isSidebarOpen ? (
          <>
            <h2 className="text-2xl font-bold text-teal-600 mb-4">
              MDP Group 20 Algo Simulator
            </h2>

            {/* Robot Position */}
            <div className="p-4 rounded-lg bg-base-200 shadow">
              <h3 className="font-semibold mb-2">Robot Position</h3>
              <div className="form-control">
                <label className="input-group input-group-horizontal">
                  <span className="bg-base-300 p-2">X</span>
                  <input
                    onChange={onChangeRobotX}
                    type="number"
                    placeholder="1"
                    min="1"
                    max="18"
                    className="input input-bordered text-white w-20"
                  />
                  <span className="bg-base-300 p-2">Y</span>
                  <input
                    onChange={onChangeRobotY}
                    type="number"
                    placeholder="1"
                    min="1"
                    max="18"
                    className="input input-bordered text-white w-20"
                  />
                  <span className="bg-base-300 p-2">D</span>
                  <select
                    onChange={onRobotDirectionInputChange}
                    value={robotDir}
                    className="select text-white py-2 pl-2 pr-6"
                  >
                    <option value={ObDirection.NORTH}>Up</option>
                    <option value={ObDirection.SOUTH}>Down</option>
                    <option value={ObDirection.WEST}>Left</option>
                    <option value={ObDirection.EAST}>Right</option>
                    <option value={Direction.NORTHEAST}>Up-Right</option>
                    <option value={Direction.SOUTHEAST}>Down-Right</option>
                    <option value={Direction.SOUTHWEST}>Down-Left</option>
                    <option value={Direction.NORTHWEST}>Up-Left</option>
                  </select>
                  <button className="btn bg-teal-600 text-white p-2" onClick={onClickRobot}>
                    Set
                  </button>
                </label>
              </div>
            </div>

            {/* Add Obstacles */}
            <div className="p-4 rounded-lg bg-base-200 shadow">
              <h3 className="font-semibold mb-2">Add Obstacles</h3>
              <div className="form-control">
                <label className="input-group input-group-horizontal">
                  <span className="bg-base-300 p-2">X</span>
                  <input
                    onChange={onChangeX}
                    type="number"
                    placeholder="1"
                    min="0"
                    max="19"
                    className="input input-bordered text-white w-20"
                  />
                  <span className="bg-base-300 p-2">Y</span>
                  <input
                    onChange={onChangeY}
                    type="number"
                    placeholder="1"
                    min="0"
                    max="19"
                    className="input input-bordered text-white w-20"
                  />
                  <span className="bg-base-300 p-2">D</span>
                  <select
                    onChange={onDirectionInputChange}
                    value={directionInput}
                    className="select text-white py-2 pl-2 pr-6"
                  >
                    <option value={ObDirection.NORTH}>Up</option>
                    <option value={ObDirection.SOUTH}>Down</option>
                    <option value={ObDirection.WEST}>Left</option>
                    <option value={ObDirection.EAST}>Right</option>
                    <option value={ObDirection.SKIP}>None</option>
                  </select>
                  <button className="btn bg-teal-600 text-white p-2" onClick={onClickObstacle}>
                    Add
                  </button>
                </label>
              </div>
            </div>

            {/* Time Limit Input */}
            <div className="p-4 rounded-lg bg-base-200 shadow">
              <h3 className="font-semibold mb-2">Time Limit (s)</h3>
              <div className="form-control">
                <label className="input-group input-group-horizontal">
                  <input
                    onChange={onChangeTimeLimit}
                    type="number"
                    placeholder="0"
                    min="0"
                    className="input input-bordered text-white w-full"
                  />
                  <button className="btn bg-teal-600 text-white p-2" onClick={onClickTimeLimit}>
                    Set
                  </button>
                </label>
              </div>
            </div>

            {/* Buttons */}
            <div className="flex space-x-2">
              <button className="btn bg-gray-700 text-white border-none" onClick={onResetAll}>
                Reset All
              </button>
              <button className="btn bg-indigo-600 text-white border-none" onClick={onReset}>
                Reset Robot
              </button>
              <button className="btn bg-violet-600 text-white border-none" onClick={compute}>
                Submit
              </button>
              <button
                className="btn bg-green-600 text-white border-none"
                onClick={() => {
                  if (path.length > 0) {
                    setIsRunning(true);
                    setStartTime(Date.now());
                    setPage(0);
                    setMessage(null);
                  }
                }}
              >
                Start
              </button>
            </div>

            {/* Obstacles List */}
            <div className="p-4 rounded-lg bg-base-200 shadow">
              <h3 className="font-semibold mb-2">Obstacles</h3>
              <div className="grid grid-cols-2 gap-2">
                {obstacles.map((ob) => (
                  <div
                    key={ob.id}
                    className="bg-base-100 border rounded p-2 text-sm flex justify-between items-center"
                  >
                    <div>
                      <div>X: {ob.x}</div>
                      <div>Y: {ob.y}</div>
                      <div>D: {DirectionToString[ob.d]}</div>
                    </div>
                    <button
                      className="text-red-500 font-bold"
                      onClick={() => onRemoveObstacle(ob)}
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Saved Trails Section */}
            <div className="p-4 rounded-lg bg-base-200 shadow">
              <h3 className="font-semibold mb-2">Saved Trails</h3>
              <div className="flex gap-2 mb-2">
                <input
                  type="text"
                  placeholder="Trail name..."
                  value={trailName}
                  onChange={(e) => setTrailName(e.target.value)}
                  className="input input-bordered text-white flex-1"
                />
                <button
                  className="btn bg-teal-600 text-white"
                  onClick={() => {
                    saveCurrentTrail(trailName);
                    setTrailName("");
                  }}
                >
                  Save
                </button>
              </div>
              <ul className="space-y-2">
                {savedTrails.map((t, idx) => (
                  <li key={idx} className="flex justify-between items-center">
                    <button
                      className="btn btn-sm bg-gray-200 text-gray-800"
                      onClick={() => recallTrail(t)}
                    >
                      {t.name}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </>
        ) : (
          <div className="mt-12 flex flex-col items-center gap-3">
            <span className="text-md font-bold [writing-mode:vertical-rl] rotate-180 text-teal-600">
              Controls
            </span>
          </div>
        )}
      </div>

      {/* RIGHT GRID PANEL */}
      <div className="flex-1 flex flex-col items-center justify-center p-6 min-w-0">
        {/* keep your existing right panel exactly the same */}
        {path.length > 0 && (
          <div className="flex flex-row items-center mb-4">
            <button
              className="btn btn-circle"
              disabled={page === 0}
              onClick={() => setPage(page - 1)}
            >
              &lt;
            </button>
            <span className="mx-4">
              Step: {page + 1} / {path.length} – {commands[page]}
              {commands[page] && commandTimes.length > page && ` (Time: ${getCumulativeTime(page)}s)`}
            </span>
            <button
              className="btn btn-circle"
              disabled={page === path.length - 1}
              onClick={() => setPage(page + 1)}
            >
              &gt;
            </button>
          </div>
        )}

        {isComputing && (
          <div className="mb-2 text-lg font-semibold text-yellow-600">
            Computing...
          </div>
        )}
        {!isComputing && calcTime !== null && (
          <div className="mb-2 text-sm font-semibold text-teal-700">
            A* search took {calcTime}s
          </div>
        )}
        {isRunning && (
          <div className="mb-2 text-lg font-semibold text-gray-700">
            Running...
          </div>
        )}
        {message && (
          <div className="mb-4 text-center text-red-500 font-bold">
            {message}
          </div>
        )}

        <table className="border-collapse">
          <tbody>{renderGrid()}</tbody>
        </table>

        {commands.length > 0 && (
          <div className="mt-4 w-full max-w-3xl bg-base-100 border rounded p-3 shadow">
            <div className="font-semibold mb-2">Generated Commands</div>
            <div className="text-sm break-words">{commands.join(", ")}</div>
          </div>
        )}
      </div>
    </div>
  );
}