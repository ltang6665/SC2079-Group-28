import os
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
from algo.algo import MazeSolver
from helper import generateCommands

app = Flask(__name__)
CORS(app)

model = None


@app.route('/status', methods=['GET'])
def checkStatus():
    return jsonify({"result": "ok"})


@app.route('/path', methods=['POST'])
def findPath():
    content = request.json

    obstacles = content['obstacles']
    retry_flag = content['retrying']
    robot_x, robot_y = content['robot_x'], content['robot_y']
    robot_direction = int(content['robot_dir'])

    # Shift external coords into internal padded grid
    # from consts import GRID_WIDTH, GRID_HEIGHT, PADDING
    # robot_x_i = robot_x + PADDING
    # robot_y_i = robot_y + PADDING
    # obstacles_i = []
    # for obstacle in obstacles:
    #     obstacles_i.append({
    #         **obstacle,
    #         'x': obstacle['x'] + PADDING,
    #         'y': obstacle['y'] + PADDING,
    #     })
    # solver = MazeSolver(GRID_WIDTH, GRID_HEIGHT, robot_x_i, robot_y_i, robot_direction, big_turn=None, allow_45=False)
    # for obstacle in obstacles_i:
    #     solver.addObstacle(obstacle['x'], obstacle['y'], obstacle['d'], obstacle['id'])
    solver = MazeSolver(20, 20, robot_x, robot_y, robot_direction, big_turn=None, allow_45=False)

    for obstacle in obstacles:
        solver.addObstacle(obstacle['x'], obstacle['y'], obstacle['d'], obstacle['id'])

    solver.printCaches()

    start_time = time.time()
    best_path, total_distance = solver.getOptimalOrderDp(retry_flag=retry_flag)
    print(f"Time taken: {time.time() - start_time:.3f}s")
    print(f"Total distance: {total_distance} units")

    # command_list, time_list = generate_commands(best_path, obstacles_i)
    command_list, time_list = generateCommands(best_path, obstacles)

    # first = best_path[0].getDict()
    # first['x'] -= PADDING
    # first['y'] -= PADDING
    # path_points = [first]
    path_points = [best_path[0].getDict()]
    index = 0
    for command in command_list:
        if command.startswith(("SNAP", "FIN")):
            continue
        elif command.startswith(("FW", "FS", "BW", "BS")):
            index += int(command[2:]) // 10
        else:
            index += 1
        # d = best_path[index].getDict()
        # d['x'] -= PADDING
        # d['y'] -= PADDING
        # path_points.append(d)
        path_points.append(best_path[index].getDict())

    return jsonify({
        "data": {
            "distance": total_distance,
            "path": path_points,
            "commands": command_list,
            "time": time_list
        },
        "error": None
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
