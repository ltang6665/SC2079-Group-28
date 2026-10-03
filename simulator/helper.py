from consts import GRID_WIDTH, GRID_HEIGHT, Direction, MOVE_DIRECTIONS


def generateCommandTimes(command_list):
    time_list = []
    for command in command_list:
        if command.startswith(("FW", "BW")):
            steps = int(command[2:])
            time_list.append(steps / 10 * 3)
        elif command.startswith(("FR45", "FL45", "BR45", "BL45")):
            time_list.append(4)
        elif command.startswith(("FR90", "FL90", "BR90", "BL90")):
            time_list.append(8)
        elif command.startswith(("SNAP", "FIN")):
            time_list.append(0)
        else:
            raise Exception(f"Unknown command: {command}")
    return time_list


def generateCommands(states, obstacles):
    obstacle_map = {item['id']: item for item in obstacles}
    command_list = []

    for index in range(1, len(states)):
        previous_state = states[index - 1]
        current_state = states[index]

        dx = current_state.x - previous_state.x
        dy = current_state.y - previous_state.y
        old_direction = int(previous_state.direction)
        new_direction = int(current_state.direction)
        direction_diff = (new_direction - old_direction) % 8

        if current_state.direction == previous_state.direction:
            expected_dx, expected_dy, _ = MOVE_DIRECTIONS[int(current_state.direction)]
            if (dx, dy) == (expected_dx, expected_dy):
                command_list.append("FW10")
            elif (dx, dy) == (-expected_dx, -expected_dy):
                command_list.append("BW10")
            else:
                raise Exception(f"Unexpected straight move ({dx},{dy})")

        elif direction_diff == 1:
            expected_dx, expected_dy, _ = MOVE_DIRECTIONS[int(current_state.direction)]
            if expected_dx * dx > 0 or expected_dy * dy > 0:
                command_list.append("FR45")
            else:
                command_list.append("BL45")

        elif direction_diff == 7:
            expected_dx, expected_dy, _ = MOVE_DIRECTIONS[int(current_state.direction)]
            if expected_dx * dx > 0 or expected_dy * dy > 0:
                command_list.append("FL45")
            else:
                command_list.append("BR45")

        elif direction_diff == 2:
            expected_dx, expected_dy, _ = MOVE_DIRECTIONS[int(current_state.direction)]
            if expected_dx * dx > 0 or expected_dy * dy > 0:
                command_list.append("FR90")
            else:
                command_list.append("BL90")

        elif direction_diff == 6:
            expected_dx, expected_dy, _ = MOVE_DIRECTIONS[int(current_state.direction)]
            if expected_dx * dx > 0 or expected_dy * dy > 0:
                command_list.append("FL90")
            else:
                command_list.append("BR90")

        elif direction_diff == 4:
            command_list.extend(["FR90", "FR90"])

        else:
            raise Exception(f"Invalid turn diff: {direction_diff}")

        if current_state.screenshot_id != -1:
            obstacle = obstacle_map[current_state.screenshot_id]
            robot = current_state

            if obstacle['d'] == Direction.WEST and robot.direction == Direction.EAST:
                if obstacle['y'] > robot.y:
                    command_list.append(f"SNAP{current_state.screenshot_id}_L")
                elif obstacle['y'] == robot.y:
                    command_list.append(f"SNAP{current_state.screenshot_id}_C")
                else:
                    command_list.append(f"SNAP{current_state.screenshot_id}_R")

            elif obstacle['d'] == Direction.EAST and robot.direction == Direction.WEST:
                if obstacle['y'] > robot.y:
                    command_list.append(f"SNAP{current_state.screenshot_id}_R")
                elif obstacle['y'] == robot.y:
                    command_list.append(f"SNAP{current_state.screenshot_id}_C")
                else:
                    command_list.append(f"SNAP{current_state.screenshot_id}_L")

            elif obstacle['d'] == Direction.NORTH and robot.direction == Direction.SOUTH:
                if obstacle['x'] > robot.x:
                    command_list.append(f"SNAP{current_state.screenshot_id}_L")
                elif obstacle['x'] == robot.x:
                    command_list.append(f"SNAP{current_state.screenshot_id}_C")
                else:
                    command_list.append(f"SNAP{current_state.screenshot_id}_R")

            elif obstacle['d'] == Direction.SOUTH and robot.direction == Direction.NORTH:
                if obstacle['x'] > robot.x:
                    command_list.append(f"SNAP{current_state.screenshot_id}_R")
                elif obstacle['x'] == robot.x:
                    command_list.append(f"SNAP{current_state.screenshot_id}_C")
                else:
                    command_list.append(f"SNAP{current_state.screenshot_id}_L")

    command_list.append("FIN")

    compressed_commands = [command_list[0]]
    for index in range(1, len(command_list)):
        prev_command = compressed_commands[-1]
        curr_command = command_list[index]

        if curr_command.startswith("FW") and prev_command.startswith("FW"):
            steps = int(prev_command[2:])
            if steps != 180:
                compressed_commands[-1] = f"FW{steps + 10}"
                continue
        elif curr_command.startswith("BW") and prev_command.startswith("BW"):
            steps = int(prev_command[2:])
            if steps != 180:
                compressed_commands[-1] = f"BW{steps + 10}"
                continue
        compressed_commands.append(curr_command)

    time_list = generateCommandTimes(compressed_commands)
    return compressed_commands, time_list


def withinBounds(x, y):
    return 0 < x < GRID_WIDTH - 1 and 0 < y < GRID_HEIGHT - 1
