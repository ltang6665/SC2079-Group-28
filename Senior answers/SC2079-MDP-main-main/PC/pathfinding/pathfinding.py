from pathfinding.algo import MazeSolver
import time
from pathfinding.helper import generateCommands

def Pathfinding(obstacles, robot_x = 1, robot_y = 1, robot_direction = 0, big_turn = None, retrying = False, mode = 0):
    # Internally we pad the grid by 1 cell on every side so the planner can use a
    # "buffer ring" around the nominal arena.
    # from pathfinding.consts import WIDTH, HEIGHT, PADDING
    # robot_x_i = robot_x + PADDING
    # robot_y_i = robot_y + PADDING
    # obstacles_i = []
    # for ob in obstacles:
    #     obstacles_i.append({
    #         **ob,
    #         'x': ob['x'] + PADDING,
    #         'y': ob['y'] + PADDING,
    #     })
    # maze_solver = MazeSolver(WIDTH, HEIGHT, robot_x_i, robot_y_i, robot_direction, big_turn=big_turn, allow_45=False)
    maze_solver = MazeSolver(20, 20, robot_x, robot_y, robot_direction, big_turn=big_turn, allow_45=False)

    # Add each obstacle into the MazeSolver. Each obstacle is defined by its x,y positions, its direction, and its id
    for ob in obstacles:
        maze_solver.addObstacle(ob['x'], ob['y'], ob['d'], ob['id'])

    start = time.time()
    # Get shortest path
    optimal_path, distance = maze_solver.getOptimalOrderDp(retrying=retrying)
    
    commands,time_list = generateCommands(optimal_path, obstacles)

    # Get the starting location and add it to path_results (shift back to external coords)
    # first = optimal_path[0].getDict()
    # first['x'] -= PADDING
    # first['y'] -= PADDING
    # path_results = [first]
    path_results = [optimal_path[0].getDict()]
    # Process each command individually and append the location the robot should be after executing that command to path_results
    i = 0
    for command in commands:
        if command.startswith("SNAP"):
            continue
        if command.startswith("FIN"):
            continue
        elif command.startswith("FW") or command.startswith("FS"):
            i += int(command[2:]) // 10
        elif command.startswith("BW") or command.startswith("BS"):
            i += int(command[2:]) // 10
        else:
            i += 1
        # d = optimal_path[i].getDict()
        # d['x'] -= PADDING
        # d['y'] -= PADDING
        # path_results.append(d)
        path_results.append(optimal_path[i].getDict())
    print(f"Time taken to find shortest path using A* search: {time.time() - start}s")
    print(f"Distance to travel: {distance} units")
    return {
            'distance': distance,
            'path': path_results,
            'commands': commands,
            'time': time_list
        }
