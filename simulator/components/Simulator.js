"use client";

import React, { useState, useEffect } from "react";
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
  return { x: 19 - y, y: x };
};

const getArrow = (dir) => {
  switch (dir) {
    case Direction.NORTH: return "↑";
    case Direction.EAST: return "→";
    case Direction.SOUTH: return "↓";
    case Direction.WEST: return "←";
    case Direction.NORTHEAST: return "↗";
    case Direction.SOUTHEAST: return "↘";
    case Direction.SOUTHWEST: return "↙";
    case Direction.NORTHWEST: return "↖";
    default: return "";
  }
};

const validateObstacle = (x, y, d) => {
  if (d === ObDirection.NORTH && y > 15) return `Obstacle at (${x}, ${y}) facing Up needs 3 cells of clearance. It is too close to the top wall.`;
  if (d === ObDirection.SOUTH && y < 4) return `Obstacle at (${x}, ${y}) facing Down needs 3 cells of clearance. It is too close to the bottom wall.`;
  if (d === ObDirection.EAST && x > 15) return `Obstacle at (${x}, ${y}) facing Right needs 3 cells of clearance. It is too close to the right wall.`;
  if (d === ObDirection.WEST && x < 4) return `Obstacle at (${x}, ${y}) facing Left needs 3 cells of clearance. It is too close to the left wall.`;
  return null;
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
  const [obIdInput, setObIdInput] = useState(1);
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

  function saveCurrentTrail(name) {
    const snapshot = {
      name: name || `Trail ${savedTrails.length + 1}`,
      obstacles: obstacles.map((o) => ({ ...o })),
      trail: trail.map((t) => ({ ...t })),
      path: path.map((p) => ({ ...p })),
      commands: commands.slice(),
      commandTimes: commandTimes.slice(),
      robot: { x: robotX, y: robotY, d: robotDir, s: -1 } // Uses typed origin, not current state
    };
    setSavedTrails([...savedTrails, snapshot]);
  }

  function recallTrail(snapshot) {
    setActiveTrail(snapshot);
    setObstacles(snapshot.obstacles ? snapshot.obstacles.map((o) => ({ ...o })) : []);
    setPath(snapshot.path || []);
    setCommands(snapshot.commands || []);
    setCommandTimes(snapshot.commandTimes || []);
    
    if (snapshot.robot) {
      setRobotState({ ...snapshot.robot });
      setRobotX(snapshot.robot.x);
      setRobotY(snapshot.robot.y);
      setRobotDir(snapshot.robot.d);
    }
    
    setPage(0);
    setTrail([]);
    setMessage(null);
  }


  const generateRobotCells = () => {
    const robotCells = [];
    let markerX = 0;
    let markerY = 0;

    if (robotState.d === Direction.NORTH) markerY++;
    else if (robotState.d === Direction.NORTHEAST) { markerX++; markerY++; }
    else if (robotState.d === Direction.EAST) markerX++;
    else if (robotState.d === Direction.SOUTHEAST) { markerX++; markerY--; }
    else if (robotState.d === Direction.SOUTH) markerY--;
    else if (robotState.d === Direction.SOUTHWEST) { markerX--; markerY--; }
    else if (robotState.d === Direction.WEST) markerX--;
    else if (robotState.d === Direction.NORTHWEST) { markerX--; markerY++; }

    for (let i = -1; i < 2; i++) {
      for (let j = -1; j < 2; j++) {
        const coord = transformCoord(robotState.x + i, robotState.y + j);
        if (markerX === i && markerY === j) {
          robotCells.push({ x: coord.x, y: coord.y, d: robotState.d, s: robotState.s });
        } else {
          robotCells.push({ x: coord.x, y: coord.y, d: null, s: -1 });
        }
      }
    }
    return robotCells;
  };

  const onChangeX = (event) => {
    if (Number.isInteger(Number(event.target.value))) {
      const nb = Number(event.target.value);
      if (0 <= nb && nb < 20) { setObXInput(nb); return; }
    }
    setObXInput(0);
  };

  const onChangeY = (event) => {
    if (Number.isInteger(Number(event.target.value))) {
      const nb = Number(event.target.value);
      if (0 <= nb && nb <= 19) { setObYInput(nb); return; }
    }
    setObYInput(0);
  };

  const onChangeId = (event) => {
    const value = Number(event.target.value);

    if (Number.isInteger(value) && value >= 1) {
      setObIdInput(value);
    } else {
      setObIdInput(1);
    }
  };

  const onChangeRobotX = (event) => {
    if (Number.isInteger(Number(event.target.value))) {
      const nb = Number(event.target.value);
      if (1 <= nb && nb < 19) { setRobotX(nb); return; }
    }
    setRobotX(1);
  };

  const onChangeRobotY = (event) => {
    if (Number.isInteger(Number(event.target.value))) {
      const nb = Number(event.target.value);
      if (1 <= nb && nb < 19) { setRobotY(nb); return; }
    }
    setRobotY(1);
  };

  const onClickObstacle = () => {
    if (!obXInput && !obYInput) return;

    if (obstacles.some((ob) => ob.id === obIdInput)) {
      setMessage(`Obstacle ID ${obIdInput} is already in use.`);
      return;
    }
    const err = validateObstacle(obXInput, obYInput, directionInput);
    if (err) {
      setMessage(err);
      return;
    }
    setMessage(null);
    setActiveTrail(null); // Frees the UI from saved state locking
    const newObstacles = [...obstacles];
    newObstacles.push({
      x: obXInput,
      y: obYInput,
      d: directionInput,
      id: obIdInput,
    });
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

    const targetX = col;
    const targetY = 19 - row;

    if (dragItem.type === "obstacle") {
      if (targetX < 0 || targetX > 19 || targetY < 0 || targetY > 19) {
        setDragItem(null);
        return;
      }
      const occupied = obstacles.some((ob) => ob.id !== dragItem.id && ob.x === targetX && ob.y === targetY);
      if (occupied) { setDragItem(null); return; }

      const draggedOb = obstacles.find((ob) => ob.id === dragItem.id);
      const err = validateObstacle(targetX, targetY, draggedOb.d);
      if (err) {
        setMessage(err);
        setDragItem(null);
        return;
      }

      setMessage(null);
      setActiveTrail(null);
      setObstacles((prev) =>
        prev.map((ob) => ob.id === dragItem.id ? { ...ob, x: targetX, y: targetY } : ob)
      );
      clearComputedResults();
    } else if (dragItem.type === "robot") {
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
    
    setObstacles((prev) => {
      let hasError = false;
      const nextObs = prev.map((ob) => {
        if (ob.id !== obstacleId) return ob;
        const idx = order.indexOf(ob.d);
        const nextDir = idx === -1 ? Direction.NORTH : order[(idx + 1) % order.length];
        
        const err = validateObstacle(ob.x, ob.y, nextDir);
        if (err) {
          setMessage(err);
          hasError = true;
          return ob;
        }
        return { ...ob, d: nextDir };
      });
      
      if (!hasError) {
        setMessage(null);
        setActiveTrail(null);
        clearComputedResults();
      }
      return nextObs;
    });
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
    if (obstacles.some((ob) => ob.x === x && ob.y === y)) return;

    const err = validateObstacle(x, y, directionInput);
    if (err) {
      setMessage(err);
      return;
    }

    setMessage(null);
    setActiveTrail(null);
    setObstacles((prev) => [
      ...prev,
      { x, y, d: directionInput, id: obIdInput },
    ]);
    clearComputedResults();
  };

  const onClickRobot = () => {
    setRobotState({ x: robotX, y: robotY, d: robotDir, s: -1 });
  };

  const onDirectionInputChange = (event) => {
    setDirectionInput(Number(event.target.value));
  };

  const onRobotDirectionInputChange = (event) => {
    setRobotDir(event.target.value);
  };

  const onRemoveObstacle = (ob) => {
    if (isComputing) return;
    const newObstacles = obstacles.filter((o) => o.id !== ob.id);
    setActiveTrail(null);
    setObstacles(newObstacles);
    clearComputedResults();
  };

  const compute = () => {
    for (const ob of obstacles) {
      const err = validateObstacle(ob.x, ob.y, ob.d);
      if (err) {
        setMessage(err);
        return;
      }
    }

    setActiveTrail(null);
    setIsComputing(true);
    setMessage(null);
    setCalcTime(null);
    const computeStart = Date.now();

    QueryAPI.query(obstacles, robotX, robotY, robotDir, (resp, err) => {
      const envelope = resp || {};
      const payload = envelope.data;
      const envelopeErr = envelope.error || err;

      if (!payload) {
        const msg = envelopeErr
          ? `Pathfinding failed: ${String(envelopeErr)}`
          : "Pathfinding failed: empty response.";
        setMessage(msg);
        setIsComputing(false);
        return;
      }

      const cmdList = payload.commands || [];
      const timeList = payload.time || [];
      let tempPath = payload.path || [];

      if (tempPath.length > 0) {
        while (tempPath.length < cmdList.length) {
          tempPath.push({ ...tempPath[tempPath.length - 1] });
        }
      }

      setPath(tempPath);
      setCommands(cmdList);
      setCommandTimes(timeList);
      setCalcTime(((Date.now() - computeStart) / 1000).toFixed(2));
      setIsComputing(false);
    });
  };

  const onResetAll = () => {
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

  const renderGrid = () => {
    const rows = [];
    const obstaclesToRender = activeTrail ? activeTrail.obstacles : obstacles;
    const trailToRender = trail;
    const robotCells = generateRobotCells();

    const squareCell = "aspect-square p-0 m-0 leading-none text-center align-middle relative";

    for (let i = 0; i < 20; i++) {
      const cells = [
        <td key={i} className={squareCell}>
          <span className="text-base-content/40 font-bold text-[8px] md:text-[9px]">
            {19 - i}
          </span>
        </td>,
      ];

      for (let j = 0; j < 20; j++) {
        let foundOb = null;
        let foundRobotCell = null;

        for (const ob of obstaclesToRender) {
          const transformed = transformCoord(ob.x, ob.y);
          if (transformed.x === i && transformed.y === j) {
            foundOb = ob;
            break;
          }
        }

        if (!foundOb) {
          for (const cell of robotCells) {
            if (cell.x === i && cell.y === j) {
              foundRobotCell = cell;
              break;
            }
          }
        }

        let foundTrail = trailToRender.find(
          (t) => transformCoord(t.x, t.y).x === i && transformCoord(t.x, t.y).y === j
        );

        if (foundRobotCell) {
          if (foundRobotCell.d !== null) {
            cells.push(
              <td
                key={`${i}-${j}`}
                draggable={!isComputing}
                onDragStart={onDragStartRobot}
                onDragOver={onDragOverCell}
                onDrop={(e) => onDropCell(e, i, j)}
                onClick={cycleRobotDirection}
                className={`${squareCell} border border-base-300/50 font-black text-[10px] md:text-sm shadow-inner ${
                  foundRobotCell.s !== -1 ? "bg-rose-500 text-white" : "bg-primary text-primary-content"
                }`}
              >
                {getArrow(foundRobotCell.d)}
              </td>
            );
          } else {
            cells.push(
              <td
                key={`${i}-${j}`}
                draggable={!isComputing}
                onDragStart={onDragStartRobot}
                onDragOver={onDragOverCell}
                onDrop={(e) => onDropCell(e, i, j)}
                onClick={cycleRobotDirection}
                className={`${squareCell} bg-accent/60 border border-accent/20`}
              />
            );
          }
        } else if (foundOb) {
          let obBorder = "border-2 border-neutral-600";
          if (foundOb.d === Direction.WEST) obBorder = "border-2 border-neutral-600 border-l-[5px] border-l-red-500";
          else if (foundOb.d === Direction.EAST) obBorder = "border-2 border-neutral-600 border-r-[5px] border-r-red-500";
          else if (foundOb.d === Direction.NORTH) obBorder = "border-2 border-neutral-600 border-t-[5px] border-t-red-500";
          else if (foundOb.d === Direction.SOUTH) obBorder = "border-2 border-neutral-600 border-b-[5px] border-b-red-500";

          cells.push(
            <td
              key={`${i}-${j}`}
              draggable={!isComputing}
              onDragStart={() => onDragStartObstacle(foundOb)}
              onDragOver={onDragOverCell}
              onDrop={(e) => onDropCell(e, i, j)}
              onClick={() => cycleObstacleDirection(foundOb.id)}
              className={`bg-black cursor-pointer shadow-md group ${squareCell} ${obBorder}`}
            >
              <span className="text-[9px] font-black select-none pointer-events-none text-white drop-shadow">
                {foundOb.id}
              </span>
              <div className="absolute left-1/2 top-0 z-30 -translate-x-1/2 -translate-y-full hidden group-hover:block pointer-events-none">
                <div className="whitespace-nowrap rounded bg-neutral-900 border border-neutral-700 px-1 py-0.5 text-[8px] text-white shadow-xl">
                  ID:{foundOb.id} ({foundOb.x}, {foundOb.y})
                </div>
              </div>
            </td>
          );
        } else if (foundTrail) {
          cells.push(
            <td
              key={`${i}-${j}`}
              onDragOver={onDragOverCell}
              onDrop={(e) => onDropCell(e, i, j)}
              onClick={() => addObstacleAtCell(i, j)}
              className={`${squareCell} border border-base-300/40 cursor-pointer hover:bg-base-200 transition-colors`}
            >
              <div className="inline-block align-middle w-1.5 h-1.5 md:w-2 md:h-2 rounded-full bg-warning opacity-90 shadow-[0_0_4px_currentColor]"></div>
            </td>
          );
        } else {
          cells.push(
            <td
              key={`${i}-${j}`}
              onDragOver={onDragOverCell}
              onDrop={(e) => onDropCell(e, i, j)}
              onClick={() => addObstacleAtCell(i, j)}
              className={`${squareCell} border border-base-300/40 cursor-pointer hover:bg-base-200 transition-colors duration-150`}
            />
          );
        }
      }
      rows.push(<tr key={19 - i}>{cells}</tr>);
    }

    const yAxis = [<td key={0} className={squareCell} />];
    for (let i = 0; i < 20; i++) {
      yAxis.push(
        <td key={`y-${i}`} className={squareCell}>
          <span className="text-base-content/40 font-bold text-[8px] md:text-[9px]">
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
    setRobotState(current);

    let newTrail = [];
    for (let i = 1; i <= page; i++) {
      const from = path[i - 1];
      const to = path[i];

      const centerFrom = { x: from.x, y: from.y };
      const centerTo = { x: to.x, y: to.y };

      const dx = centerTo.x - centerFrom.x;
      const dy = centerTo.y - centerFrom.y;

      if (dy === 0 && dx !== 0) {
        const step = dx > 0 ? 1 : -1;
        for (let x = centerFrom.x; x !== centerTo.x + step; x += step) {
          newTrail.push({ x, y: centerFrom.y });
        }
      } else if (dx === 0 && dy !== 0) {
        const step = dy > 0 ? 1 : -1;
        for (let y = centerFrom.y; y !== centerTo.y + step; y += step) {
          newTrail.push({ x: centerFrom.x, y });
        }
      } else if (dx !== 0 && dy !== 0 && Math.abs(dx) === Math.abs(dy)) {
        const stepX = dx > 0 ? 1 : -1;
        const stepY = dy > 0 ? 1 : -1;
        let x = centerFrom.x;
        let y = centerFrom.y;
        while (x !== centerTo.x + stepX && y !== centerTo.y + stepY) {
          newTrail.push({ x, y });
          x += stepX;
          y += stepY;
        }
      } else if (dx !== 0 && dy !== 0) {
        // FRIEND'S LOGIC: Always draw Horizontal first, then Vertical.
        const stepX = dx > 0 ? 1 : -1;
        for (let x = centerFrom.x; x !== centerTo.x + stepX; x += stepX) {
          newTrail.push({ x, y: centerFrom.y });
        }
        const stepY = dy > 0 ? 1 : -1;
        for (let y = centerFrom.y; y !== centerTo.y + stepY; y += stepY) {
          newTrail.push({ x: centerTo.x, y });
        }
      }
    }
    setTrail(newTrail);
  }, [page, path]);

  useEffect(() => {
    let interval;
    if (isRunning && page < path.length - 1) {
      const nextStepCumulativeTime = getCumulativeTime(page + 1);
      if (timeLimit > 0 && nextStepCumulativeTime > timeLimit) {
        setIsRunning(false);
        setMessage(`Time limit of ${timeLimit}s exceeded. Stopped.`);
        return;
      }
      interval = setInterval(() => {
        setPage((prev) => prev + 1);
      }, 500);
    } else if (isRunning && page === path.length - 1) {
      setIsRunning(false);
    }
    return () => clearInterval(interval);
  }, [isRunning, page, path, startTime]);

  const getCumulativeTime = (stepIndex) => {
    if (stepIndex <= 0) return 0;
    let totalTime = 0;
    for (let i = 0; i < stepIndex && i < commandTimes.length; i++) {
      totalTime += commandTimes[i];
    }
    return totalTime;
  };

  const onChangeTimeLimit = (event) => {
    const value = Number(event.target.value);
    if (!isNaN(value) && value >= 0) setTimeLimitInput(value);
  };

  const onClickTimeLimit = () => {
    setTimeLimit(timeLimitInput);
    setMessage(`Time limit set to ${timeLimitInput}s.`);
  };

  return (
    <div className="flex flex-row h-screen bg-base-200 text-base-content overflow-hidden">
      
      {/* LEFT SETTINGS PANEL */}
      <div
        className={`relative h-full bg-base-100 shadow-xl overflow-y-auto transition-all duration-300 ease-in-out flex-shrink-0 z-10 border-r border-base-300 ${
          isSidebarOpen ? "w-full sm:w-[240px] md:w-[260px] lg:w-[280px] p-2 md:p-3" : "w-0 sm:w-10 p-0 sm:p-1 overflow-hidden"
        }`}
      >
        <button
          onClick={() => setIsSidebarOpen((prev) => !prev)}
          className="btn btn-xs btn-circle absolute top-2 right-1 z-20 shadow w-5 h-5 min-h-0 text-[10px]"
        >
          {isSidebarOpen ? "❮" : "❯"}
        </button>

        {isSidebarOpen ? (
          <div className="flex flex-col gap-1.5 h-full">
            <h2 className="text-lg font-extrabold text-primary mb-0.5 tracking-tight">
              MDP Group 28
            </h2>

            {/* Robot Position Card */}
            <div className="card bg-base-200 shadow-sm border border-base-300 rounded-lg">
              <div className="card-body p-2">
                <h3 className="card-title text-[9px] uppercase font-bold tracking-wider text-base-content/60 m-0">Robot Position</h3>
                <div className="grid grid-cols-3 gap-1">
                  <div className="form-control">
                    <label className="label py-0"><span className="label-text text-[9px]">X</span></label>
                    <input type="number" onChange={onChangeRobotX} value={robotX} min="1" max="18" className="input input-bordered w-full px-1 h-6 min-h-0 text-[10px]" />
                  </div>
                  <div className="form-control">
                    <label className="label py-0"><span className="label-text text-[9px]">Y</span></label>
                    <input type="number" onChange={onChangeRobotY} value={robotY} min="1" max="18" className="input input-bordered w-full px-1 h-6 min-h-0 text-[10px]" />
                  </div>
                  <div className="form-control">
                    <label className="label py-0"><span className="label-text text-[9px]">Dir</span></label>
                    <select onChange={onRobotDirectionInputChange} value={robotDir} className="select select-bordered w-full px-0.5 h-6 min-h-0 text-[10px]">
                      <option value={ObDirection.NORTH}>Up</option>
                      <option value={ObDirection.SOUTH}>Down</option>
                      <option value={ObDirection.WEST}>Left</option>
                      <option value={ObDirection.EAST}>Right</option>
                      <option value={Direction.NORTHEAST}>↗</option>
                      <option value={Direction.SOUTHEAST}>↘</option>
                      <option value={Direction.SOUTHWEST}>↙</option>
                      <option value={Direction.NORTHWEST}>↖</option>
                    </select>
                  </div>
                </div>
                <button className="btn btn-xs btn-neutral mt-1 w-full h-6 min-h-0 text-[10px]" onClick={onClickRobot}>Set Robot</button>
              </div>
            </div>

            {/* Add Obstacles Card */}
            <div className="card bg-base-200 shadow-sm border border-base-300 rounded-lg">
              <div className="card-body p-2">
                <h3 className="card-title text-[9px] uppercase font-bold tracking-wider text-base-content/60 m-0">Add Obstacle</h3>
                <div className="grid grid-cols-4 gap-1">
                  <div className="form-control">
                    <label className="label py-0">
                      <span className="label-text text-[9px]">ID</span>
                    </label>
                    <input
                      type="number"
                      onChange={onChangeId}
                      value={obIdInput}
                      min="1"
                      className="input input-bordered w-full px-1 h-6 min-h-0 text-[10px]"
                    />
                  </div>

                  <div className="form-control">
                    <label className="label py-0">
                      <span className="label-text text-[9px]">X</span>
                    </label>
                    <input
                      type="number"
                      onChange={onChangeX}
                      min="0"
                      max="19"
                      className="input input-bordered w-full px-1 h-6 min-h-0 text-[10px]"
                    />
                  </div>

                  <div className="form-control">
                    <label className="label py-0">
                      <span className="label-text text-[9px]">Y</span>
                    </label>
                    <input
                      type="number"
                      onChange={onChangeY}
                      min="0"
                      max="19"
                      className="input input-bordered w-full px-1 h-6 min-h-0 text-[10px]"
                    />
                  </div>

                  <div className="form-control">
                    <label className="label py-0">
                      <span className="label-text text-[9px]">Dir</span>
                    </label>
                    <select
                      onChange={onDirectionInputChange}
                      value={directionInput}
                      className="select select-bordered w-full px-0.5 h-6 min-h-0 text-[10px]"
                    >
                      <option value={ObDirection.NORTH}>Up</option>
                      <option value={ObDirection.SOUTH}>Down</option>
                      <option value={ObDirection.WEST}>Left</option>
                      <option value={ObDirection.EAST}>Right</option>
                      <option value={ObDirection.SKIP}>None</option>
                    </select>
                  </div>
                </div>
                <button className="btn btn-xs btn-secondary mt-1 w-full h-6 min-h-0 text-[10px]" onClick={onClickObstacle}>Add Obstacle</button>
              </div>
            </div>

            {/* Time Limit Card */}
            <div className="card bg-base-200 shadow-sm border border-base-300 rounded-lg">
              <div className="card-body p-2 flex flex-row items-center justify-between gap-2">
                <h3 className="card-title text-[9px] uppercase font-bold tracking-wider text-base-content/60 m-0 whitespace-nowrap">Time Limit</h3>
                <div className="flex gap-1 flex-1">
                  <input
                    onChange={onChangeTimeLimit}
                    type="number"
                    placeholder="0"
                    min="0"
                    className="input input-bordered w-full px-1 h-6 min-h-0 text-[10px]"
                  />
                  <button className="btn btn-xs btn-neutral h-6 min-h-0 text-[9px]" onClick={onClickTimeLimit}>
                    Set
                  </button>
                </div>
              </div>
            </div>

            {/* Control Buttons */}
            <div className="flex flex-wrap gap-1 mt-0.5">
              <button className="btn btn-xs btn-outline flex-1 h-6 min-h-0 text-[9px]" onClick={onResetAll}>Reset All</button>
              <button className="btn btn-xs btn-outline flex-1 h-6 min-h-0 text-[9px]" onClick={onReset}>Reset Robot</button>
            </div>
            <div className="flex flex-wrap gap-1">
              <button className="btn btn-xs btn-primary flex-1 shadow-md font-bold h-7 min-h-0 text-[10px]" onClick={compute} disabled={isComputing}>
                {isComputing ? <span className="loading loading-spinner w-3 h-3"></span> : "Calculate"}
              </button>
              <button 
                className="btn btn-xs btn-accent flex-1 shadow-md font-bold text-accent-content h-7 min-h-0 text-[10px]" 
                disabled={path.length === 0 || isRunning}
                onClick={() => {
                  if (path.length > 0) {
                    setIsRunning(true);
                    setStartTime(Date.now());
                    setPage(0);
                    setMessage(null);
                  }
                }}
              >
                Play Route
              </button>
            </div>

            {/* Current Obstacles List */}
            <div className="card bg-base-200 shadow-sm border border-base-300 flex-1 min-h-0 mt-0.5 rounded-lg">
              <div className="card-body p-2 overflow-y-auto">
                <h3 className="card-title text-[9px] uppercase font-bold tracking-wider text-base-content/60 sticky top-0 bg-base-200 pb-1 z-10 m-0">Current Obstacles</h3>
                <div className="grid grid-cols-2 gap-1 mt-0.5">
                  {obstacles.map((ob) => (
                    <div key={ob.id} className="bg-base-100 border border-base-300 rounded p-1 flex justify-between items-center shadow-sm">
                      <div className="leading-tight">
                        <div className="font-mono text-[9px] text-base-content/70">ID:{ob.id} ({ob.x},{ob.y})</div>
                        <div className="font-semibold text-[9px] text-primary">{DirectionToString[ob.d]}</div>
                      </div>
                      <button className="btn btn-xs btn-error btn-square h-4 w-4 min-h-0 text-[8px] opacity-70 hover:opacity-100" onClick={() => onRemoveObstacle(ob)}>✕</button>
                    </div>
                  ))}
                  {obstacles.length === 0 && <span className="text-[9px] text-base-content/50 col-span-2">No obstacles added.</span>}
                </div>
              </div>
            </div>

          </div>
        ) : (
          <div className="mt-10 flex flex-col items-center">
            <span className="text-[10px] font-bold tracking-widest uppercase [writing-mode:vertical-rl] rotate-180 text-base-content/50">
              Dashboard
            </span>
          </div>
        )}
      </div>

      {/* CENTER MAIN PANEL - THE ARENA GRID */}
      <div className="flex-1 flex flex-col items-center justify-center p-2 md:p-4 min-w-0 overflow-y-auto bg-base-300/30">
        <div className="w-full max-w-[65vh] aspect-square flex-shrink-0 bg-base-100 p-1 md:p-2 rounded-xl shadow-lg border border-base-300">
          <table className="border-collapse w-full h-full table-fixed">
            <tbody>{renderGrid()}</tbody>
          </table>
        </div>
      </div>

      {/* RIGHT SIDEBAR - RESULTS, COMMANDS & SAVED TRAILS */}
      <div className="w-[220px] md:w-[250px] lg:w-[270px] h-full bg-base-100 shadow-xl border-l border-base-300 p-2 md:p-3 flex flex-col gap-2 overflow-y-auto flex-shrink-0 z-10 hidden sm:flex">
        
        <h2 className="text-sm font-extrabold text-primary mb-0.5 tracking-tight uppercase border-b border-base-300 pb-1">
          Results Log
        </h2>

        {/* Status Alerts Area */}
        <div className="w-full flex flex-col gap-1 min-h-[1.75rem]">
          {isComputing && (
            <div className="alert alert-warning shadow-sm py-1 px-2 rounded-md w-full h-7 min-h-0 flex items-center justify-center">
              <span className="loading loading-spinner w-3 h-3"></span>
              <span className="font-semibold text-[10px]">Computing...</span>
            </div>
          )}
          {!isComputing && calcTime !== null && !message && (
            <div className="alert alert-success shadow-sm py-1 px-2 rounded-md text-success-content font-bold text-[10px] bg-success/90 w-full h-7 min-h-0 flex items-center justify-center">
              ✅ Found in {calcTime}s
            </div>
          )}
          {message && (
            <div className="alert alert-error shadow-sm py-1 px-2 rounded-md w-full min-h-7 flex items-center justify-center text-center">
              <span className="font-semibold text-[10px] leading-tight">{message}</span>
            </div>
          )}
        </div>

        {/* Playback Area */}
        {path.length > 0 && (
          <div className="card bg-base-200 shadow-sm border border-base-300 rounded-lg">
            <div className="card-body p-2">
              <h3 className="card-title text-[9px] uppercase font-bold tracking-wider text-base-content/60 m-0">Playback Timeline</h3>
              
              <div className="flex justify-between items-center w-full text-[9px] font-bold mb-1 mt-1 text-base-content/50 uppercase tracking-widest">
                <span>Start</span>
                <span className="badge badge-primary h-4 text-[9px] px-1.5 badge-outline font-bold">Step {page + 1} of {path.length}</span>
                <span>Finish</span>
              </div>
              <input 
                type="range" 
                min={0} 
                max={path.length - 1} 
                value={page} 
                className="range range-primary range-xs w-full" 
                onChange={(e) => {
                  setIsRunning(false);
                  setPage(Number(e.target.value));
                }}
              />
              <div className="mt-1 text-center text-[10px] font-bold">
                {commands[page] ? (
                  <span className="text-secondary text-xs">{commands[page]} <span className="text-base-content/40 text-[9px] ml-1 font-medium">({getCumulativeTime(page)}s)</span></span>
                ) : (
                  <span className="text-base-content/50">Position Selected</span>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Command Sequence Area (Crisp White Text) */}
        {commands.length > 0 && (
          <div className="card bg-base-200 shadow-sm border border-base-300 rounded-lg min-h-[120px] flex-1">
            <div className="card-body p-2 flex flex-col h-full">
              <h3 className="card-title text-[9px] uppercase font-bold tracking-wider text-base-content/60 m-0 mb-1">
                Command Sequence
              </h3>
              <div className="text-[11px] font-mono text-white leading-relaxed break-words bg-neutral-900 p-2 rounded border border-neutral-700 overflow-y-auto flex-1 select-text">
                {commands.join(", ")}
              </div>
            </div>
          </div>
        )}

        {/* Saved Trails Card */}
        <div className="card bg-base-200 shadow-sm border border-base-300 rounded-lg mt-auto">
          <div className="card-body p-2">
            <h3 className="card-title text-[9px] uppercase font-bold tracking-wider text-base-content/60 m-0">Saved Trails</h3>
            <div className="flex gap-1 mt-1">
              <input
                type="text"
                placeholder="Name..."
                value={trailName}
                onChange={(e) => setTrailName(e.target.value)}
                className="input input-bordered w-full px-1 h-6 min-h-0 text-[10px]"
              />
              <button
                className="btn btn-xs btn-primary h-6 min-h-0 text-[9px]"
                onClick={() => {
                  saveCurrentTrail(trailName);
                  setTrailName("");
                }}
              >
                Save
              </button>
            </div>
            {savedTrails.length > 0 && (
              <ul className="space-y-1 mt-1 max-h-24 overflow-y-auto">
                {savedTrails.map((t, idx) => (
                  <li key={idx}>
                    <button
                      className="btn btn-xs bg-base-100 border-base-300 hover:bg-base-300 text-base-content w-full h-5 min-h-0 text-[9px] justify-start px-1.5"
                      onClick={() => recallTrail(t)}
                    >
                      {t.name}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

      </div>

    </div>
  );
}