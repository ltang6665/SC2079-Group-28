from pathfinding.consts import WIDTH, HEIGHT, Direction, MOVE_DIRECTION


def isValid(center_x: int, center_y: int):
    """Checks if given position is within bounds"""
    return center_x > 0 and center_y > 0 and center_x < WIDTH - 1 and center_y < HEIGHT - 1


# def command_generator(states, obstacles):
#     """
#     This function takes in a list of states and generates a list of commands for the robot to follow
    
#     Inputs
#     ------
#     states: list of State objects
#     obstacles: list of obstacles, each obstacle is a dictionary with keys "x", "y", "d", and "id"

#     Returns
#     -------
#     commands: list of commands for the robot to follow
#     """

#     # Convert the list of obstacles into a dictionary with key as the obstacle id and value as the obstacle
#     obstacles_dict = {ob['id']: ob for ob in obstacles}
    
#     # Initialize commands list
#     commands = []

#     # Iterate through each state in the list of states
#     for i in range(1, len(states)):
#         steps = "00"

#         # If previous state and current state are the same direction,
#         if states[i].direction == states[i - 1].direction:
#             # Forward - Must be (east facing AND x value increased) OR (north facing AND y value increased)
#             if (states[i].x > states[i - 1].x and states[i].direction == Direction.EAST) or (states[i].y > states[i - 1].y and states[i].direction == Direction.NORTH):
#                 commands.append("FW10")
#             # Forward - Must be (west facing AND x value decreased) OR (south facing AND y value decreased)
#             elif (states[i].x < states[i-1].x and states[i].direction == Direction.WEST) or (
#                     states[i].y < states[i-1].y and states[i].direction == Direction.SOUTH):
#                 commands.append("FW10")
#             # Backward - All other cases where the previous and current state is the same direction
#             else:
#                 commands.append("BW10")

#             # If any of these states has a valid screenshot ID, then add a SNAP command as well to take a picture
#             if states[i].screenshot_id != -1:
#                 # NORTH = 0
#                 # EAST = 2
#                 # SOUTH = 4
#                 # WEST = 6

#                 current_ob_dict = obstacles_dict[states[i].screenshot_id] # {'x': 9, 'y': 10, 'd': 6, 'id': 9}
#                 current_robot_position = states[i] # {'x': 1, 'y': 8, 'd': <Direction.NORTH: 0>, 's': -1}

#                 # Obstacle facing WEST, robot facing EAST
#                 if current_ob_dict['d'] == 6 and current_robot_position.direction == 2:
#                     if current_ob_dict['y'] > current_robot_position.y:
#                         commands.append(f"SNAP{states[i].screenshot_id}_L")
#                     elif current_ob_dict['y'] == current_robot_position.y:
#                         commands.append(f"SNAP{states[i].screenshot_id}_C")
#                     elif current_ob_dict['y'] < current_robot_position.y:
#                         commands.append(f"SNAP{states[i].screenshot_id}_R")
#                     else:
#                         commands.append(f"SNAP{states[i].screenshot_id}")
                
#                 # Obstacle facing EAST, robot facing WEST
#                 elif current_ob_dict['d'] == 2 and current_robot_position.direction == 6:
#                     if current_ob_dict['y'] > current_robot_position.y:
#                         commands.append(f"SNAP{states[i].screenshot_id}_R")
#                     elif current_ob_dict['y'] == current_robot_position.y:
#                         commands.append(f"SNAP{states[i].screenshot_id}_C")
#                     elif current_ob_dict['y'] < current_robot_position.y:
#                         commands.append(f"SNAP{states[i].screenshot_id}_L")
#                     else:
#                         commands.append(f"SNAP{states[i].screenshot_id}")

#                 # Obstacle facing NORTH, robot facing SOUTH
#                 elif current_ob_dict['d'] == 0 and current_robot_position.direction == 4:
#                     if current_ob_dict['x'] > current_robot_position.x:
#                         commands.append(f"SNAP{states[i].screenshot_id}_L")
#                     elif current_ob_dict['x'] == current_robot_position.x:
#                         commands.append(f"SNAP{states[i].screenshot_id}_C")
#                     elif current_ob_dict['x'] < current_robot_position.x:
#                         commands.append(f"SNAP{states[i].screenshot_id}_R")
#                     else:
#                         commands.append(f"SNAP{states[i].screenshot_id}")

#                 # Obstacle facing SOUTH, robot facing NORTH
#                 elif current_ob_dict['d'] == 4 and current_robot_position.direction == 0:
#                     if current_ob_dict['x'] > current_robot_position.x:
#                         commands.append(f"SNAP{states[i].screenshot_id}_R")
#                     elif current_ob_dict['x'] == current_robot_position.x:
#                         commands.append(f"SNAP{states[i].screenshot_id}_C")
#                     elif current_ob_dict['x'] < current_robot_position.x:
#                         commands.append(f"SNAP{states[i].screenshot_id}_L")
#                     else:
#                         commands.append(f"SNAP{states[i].screenshot_id}")
#             continue

#         # If previous state and current state are not the same direction, it means that there will be a turn command involved
#         # Assume there are 4 turning command: FR, FL, BL, BR (the turn command will turn the robot 90 degrees)
#         # FR00 | FR30: Forward Right;
#         # FL00 | FL30: Forward Left;
#         # BR00 | BR30: Backward Right;
#         # BL00 | BL30: Backward Left;

#         # Facing north previously
#         if states[i - 1].direction == Direction.NORTH:
#             # Facing east afterwards
#             if states[i].direction == Direction.EAST:
#                 # y value increased -> Forward Right
#                 if states[i].y > states[i - 1].y:
#                     commands.append("FR{}".format(steps))
#                 # y value decreased -> Backward Left
#                 else:
#                     commands.append("BL{}".format(steps))
#             # Facing west afterwards
#             elif states[i].direction == Direction.WEST:
#                 # y value increased -> Forward Left
#                 if states[i].y > states[i - 1].y:
#                     commands.append("FL{}".format(steps))
#                 # y value decreased -> Backward Right
#                 else:
#                     commands.append("BR{}".format(steps))
#             else:
#                 raise Exception("Invalid turing direction")

#         elif states[i - 1].direction == Direction.EAST:
#             if states[i].direction == Direction.NORTH:
#                 if states[i].y > states[i - 1].y:
#                     commands.append("FL{}".format(steps))
#                 else:
#                     commands.append("BR{}".format(steps))

#             elif states[i].direction == Direction.SOUTH:
#                 if states[i].y > states[i - 1].y:
#                     commands.append("BL{}".format(steps))
#                 else:
#                     commands.append("FR{}".format(steps))
#             else:
#                 raise Exception("Invalid turing direction")

#         elif states[i - 1].direction == Direction.SOUTH:
#             if states[i].direction == Direction.EAST:
#                 if states[i].y > states[i - 1].y:
#                     commands.append("BR{}".format(steps))
#                 else:
#                     commands.append("FL{}".format(steps))
#             elif states[i].direction == Direction.WEST:
#                 if states[i].y > states[i - 1].y:
#                     commands.append("BL{}".format(steps))
#                 else:
#                     commands.append("FR{}".format(steps))
#             else:
#                 raise Exception("Invalid turing direction")

#         elif states[i - 1].direction == Direction.WEST:
#             if states[i].direction == Direction.NORTH:
#                 if states[i].y > states[i - 1].y:
#                     commands.append("FR{}".format(steps))
#                 else:
#                     commands.append("BL{}".format(steps))
#             elif states[i].direction == Direction.SOUTH:
#                 if states[i].y > states[i - 1].y:
#                     commands.append("BR{}".format(steps))
#                 else:
#                     commands.append("FL{}".format(steps))
#             else:
#                 raise Exception("Invalid turing direction")
#         else:
#             raise Exception("Invalid position")

#         # If any of these states has a valid screenshot ID, then add a SNAP command as well to take a picture
#         if states[i].screenshot_id != -1:  
#             # NORTH = 0
#             # EAST = 2
#             # SOUTH = 4
#             # WEST = 6

#             current_ob_dict = obstacles_dict[states[i].screenshot_id] # {'x': 9, 'y': 10, 'd': 6, 'id': 9}
#             current_robot_position = states[i] # {'x': 1, 'y': 8, 'd': <Direction.NORTH: 0>, 's': -1}

#             # Obstacle facing WEST, robot facing EAST
#             if current_ob_dict['d'] == 6 and current_robot_position.direction == 2:
#                 if current_ob_dict['y'] > current_robot_position.y:
#                     commands.append(f"SNAP{states[i].screenshot_id}_L")
#                 elif current_ob_dict['y'] == current_robot_position.y:
#                     commands.append(f"SNAP{states[i].screenshot_id}_C")
#                 elif current_ob_dict['y'] < current_robot_position.y:
#                     commands.append(f"SNAP{states[i].screenshot_id}_R")
#                 else:
#                     commands.append(f"SNAP{states[i].screenshot_id}")
            
#             # Obstacle facing EAST, robot facing WEST
#             elif current_ob_dict['d'] == 2 and current_robot_position.direction == 6:
#                 if current_ob_dict['y'] > current_robot_position.y:
#                     commands.append(f"SNAP{states[i].screenshot_id}_R")
#                 elif current_ob_dict['y'] == current_robot_position.y:
#                     commands.append(f"SNAP{states[i].screenshot_id}_C")
#                 elif current_ob_dict['y'] < current_robot_position.y:
#                     commands.append(f"SNAP{states[i].screenshot_id}_L")
#                 else:
#                     commands.append(f"SNAP{states[i].screenshot_id}")

#             # Obstacle facing NORTH, robot facing SOUTH
#             elif current_ob_dict['d'] == 0 and current_robot_position.direction == 4:
#                 if current_ob_dict['x'] > current_robot_position.x:
#                     commands.append(f"SNAP{states[i].screenshot_id}_L")
#                 elif current_ob_dict['x'] == current_robot_position.x:
#                     commands.append(f"SNAP{states[i].screenshot_id}_C")
#                 elif current_ob_dict['x'] < current_robot_position.x:
#                     commands.append(f"SNAP{states[i].screenshot_id}_R")
#                 else:
#                     commands.append(f"SNAP{states[i].screenshot_id}")

#             # Obstacle facing SOUTH, robot facing NORTH
#             elif current_ob_dict['d'] == 4 and current_robot_position.direction == 0:
#                 if current_ob_dict['x'] > current_robot_position.x:
#                     commands.append(f"SNAP{states[i].screenshot_id}_R")
#                 elif current_ob_dict['x'] == current_robot_position.x:
#                     commands.append(f"SNAP{states[i].screenshot_id}_C")
#                 elif current_ob_dict['x'] < current_robot_position.x:
#                     commands.append(f"SNAP{states[i].screenshot_id}_L")
#                 else:
#                     commands.append(f"SNAP{states[i].screenshot_id}")

#     # Final command is the stop command (FIN)
#     commands.append("FIN")  

#     # Compress commands if there are consecutive forward or backward commands
#     compressed_commands = [commands[0]]

#     for i in range(1, len(commands)):
#         # If both commands are BW
#         if commands[i].startswith("BW") and compressed_commands[-1].startswith("BW"):
#             # Get the number of steps of previous command
#             steps = int(compressed_commands[-1][2:])
#             # If steps are not 90, add 10 to the steps
#             if steps != 90:
#                 compressed_commands[-1] = "BW{}".format(steps + 10)
#                 continue

#         # If both commands are FW
#         elif commands[i].startswith("FW") and compressed_commands[-1].startswith("FW"):
#             # Get the number of steps of previous command
#             steps = int(compressed_commands[-1][2:])
#             # If steps are not 90, add 10 to the steps
#             if steps != 90:
#                 compressed_commands[-1] = "FW{}".format(steps + 10)
#                 continue
        
#         # Otherwise, just add as usual
#         compressed_commands.append(commands[i])
#     time = time_generator(compressed_commands)
#     return compressed_commands,time

def generateCommands(states, obstacles):
    """
    Generate movement + turn + SNAP commands for the robot.
    Handles straight, 45° diagonals, and 90° arcs consistently with get_neighbors.
    """

    obstacles_dict = {ob['id']: ob for ob in obstacles}
    commands = []

    for i in range(1, len(states)):
        prev = states[i - 1]
        curr = states[i]

        dx = curr.x - prev.x
        dy = curr.y - prev.y
        old_dir = int(prev.direction)
        new_dir = int(curr.direction)
        diff = (new_dir - old_dir) % 8

        # # === Case 1: Straight ===
        # if curr.direction == prev.direction:
        #     if (dx > 0 and curr.direction in [Direction.EAST]) \
        #        or (dx < 0 and curr.direction in [Direction.WEST]) \
        #        or (dy > 0 and curr.direction in [Direction.NORTH]) \
        #        or (dy < 0 and curr.direction in [Direction.SOUTH]):
        #         commands.append("FW10")
        #     else:
        #         commands.append("BW10")

        # === Case 1: Straight ===
        if curr.direction == prev.direction:
            # Get the canonical (dx, dy) for this direction
            expected_dx, expected_dy, _ = MOVE_DIRECTION[int(curr.direction)]

            if (dx, dy) == (expected_dx, expected_dy):
                commands.append("FW10")
            elif (dx, dy) == (-expected_dx, -expected_dy):
                commands.append("BW10")
            else:
                raise Exception(
                    f"Unexpected straight movement: dir={curr.direction}, "
                    f"expected ({expected_dx},{expected_dy}) or opposite, got ({dx},{dy})"
                )
        # === Case 2: 45° Diagonal Turns ===
        elif diff == 1:   # +45° clockwise
            # forward if movement is in same general quadrant
            expected_dx, expected_dy, _ = MOVE_DIRECTION[int(curr.direction)]
            new_dx,new_dy = expected_dx * dx, expected_dy * dy
            if new_dx > 0 or new_dy > 0:
                commands.append("FR45")
            else:
                commands.append("BL45")
        elif diff == 7:  # -45° counter-clockwise
            expected_dx, expected_dy, _ = MOVE_DIRECTION[int(curr.direction)]
            new_dx,new_dy = expected_dx * dx, expected_dy * dy
            if new_dx > 0 or new_dy > 0:
                commands.append("FL45")
            else:
                commands.append("BR45")

        # === Case 3: 90° Arcs ===
        elif diff == 2:  # clockwise (FR90 or BL90)
            expected_dx, expected_dy, _ = MOVE_DIRECTION[int(curr.direction)]
            new_dx,new_dy = expected_dx * dx, expected_dy * dy
            if new_dx > 0 or new_dy > 0:
                commands.append("FR90")
            else:
                commands.append("BL90")
        elif diff == 6:  # counter-clockwise (FL90 or BR90)
            expected_dx, expected_dy, _ = MOVE_DIRECTION[int(curr.direction)]
            new_dx,new_dy = expected_dx * dx, expected_dy * dy
            if new_dx > 0 or new_dy > 0:
                commands.append("FL90")
            else:
                commands.append("BR90")

        # === Case 4: 180° Turn ===
        elif diff == 4:
            commands.extend(["FR90", "FR90"])

        else:
            raise Exception(f"Unexpected turn diff: {diff} from {old_dir} -> {new_dir}")

        # === Case 5: SNAP ===
        if curr.screenshot_id != -1:
            ob = obstacles_dict[curr.screenshot_id]
            rob = curr

            if ob['d'] == Direction.WEST and rob.direction == Direction.EAST:
                if ob['y'] > rob.y: commands.append(f"SNAP{curr.screenshot_id}_L")
                elif ob['y'] == rob.y: commands.append(f"SNAP{curr.screenshot_id}_C")
                else: commands.append(f"SNAP{curr.screenshot_id}_R")

            elif ob['d'] == Direction.EAST and rob.direction == Direction.WEST:
                if ob['y'] > rob.y: commands.append(f"SNAP{curr.screenshot_id}_R")
                elif ob['y'] == rob.y: commands.append(f"SNAP{curr.screenshot_id}_C")
                else: commands.append(f"SNAP{curr.screenshot_id}_L")

            elif ob['d'] == Direction.NORTH and rob.direction == Direction.SOUTH:
                if ob['x'] > rob.x: commands.append(f"SNAP{curr.screenshot_id}_L")
                elif ob['x'] == rob.x: commands.append(f"SNAP{curr.screenshot_id}_C")
                else: commands.append(f"SNAP{curr.screenshot_id}_R")

            elif ob['d'] == Direction.SOUTH and rob.direction == Direction.NORTH:
                if ob['x'] > rob.x: commands.append(f"SNAP{curr.screenshot_id}_R")
                elif ob['x'] == rob.x: commands.append(f"SNAP{curr.screenshot_id}_C")
                else: commands.append(f"SNAP{curr.screenshot_id}_L")

    # Final stop
    commands.append("FIN")

    # === Compress FW/BW ===
    compressed = [commands[0]]
    for i in range(1, len(commands)):
        if commands[i].startswith("FW") and compressed[-1].startswith("FW"):
            steps = int(compressed[-1][2:])
            if steps != 180:
                compressed[-1] = f"FW{steps + 10}"
                continue
        elif commands[i].startswith("BW") and compressed[-1].startswith("BW"):
            steps = int(compressed[-1][2:])
            if steps != 180:
                compressed[-1] = f"BW{steps + 10}"
                continue
        compressed.append(commands[i])

    time = generateCommandTimes(compressed)
    return compressed, time




# def time_generator(compressed_commands: list):
#     """
#     This function takes in a list of commands and generates the time taken

#     Inputs
#     ------
#     compressed_commands: list of commands 

#     Returns
#     -------
#     time: list of time taken for each command
#     """
#     time = []
    
#     # Iterate through each command in the list of compressed commands
#     for command in compressed_commands:
#         # Check if the command starts with 'FW' (forward movement) or 'BW' (backward movement)
#         if command.startswith("FW") or command.startswith("BW"):
#             # Extract the number of steps from the command string
#             steps = int(command[2:])
#             # Calculate time for movement: 3 seconds per step
#             time.append(steps / 10 * 3)
#         # Check if the command is a turning command (FR, FL, BR, BL)
#         elif command.startswith("FR") or command.startswith("FL") or command.startswith("BR") or command.startswith("BL"):
#             # A turn takes 8 seconds, 
#             time.append(8)
#         # Handle 'SNAP' command for taking a picture
#         elif command.startswith("SNAP"):
#             # (We assume) taking a picture takes 0 second (but we filter this out later anyway, if not we can just add x seconds to the latest step)
#             #time[:-1] += 1
#             time.append(0)
#         # Handle 'FIN' command to stop
#         elif command.startswith("FIN"):
#             # Final Commands just to end simulation should take 0 seconds
#             time.append(0)
    
#     return time


def generateCommandTimes(compressed_commands: list):
    """
    This function takes in a list of commands and generates the time taken

    Inputs
    ------
    compressed_commands: list of commands 

    Returns
    -------
    time: list of time taken for each command
    """
    time = []
    
    for command in compressed_commands:
        # Forward / Backward
        if command.startswith("FW") or command.startswith("BW"):
            steps = int(command[2:])
            # 3 seconds per 10-unit step
            time.append(steps / 10 * 3)

        # 45° turns
        elif command.startswith("FR45") or command.startswith("FL45") \
             or command.startswith("BR45") or command.startswith("BL45"):
            time.append(4)  # half of 90°

        # 90° turns
        elif command.startswith("FR90") or command.startswith("FL90") \
             or command.startswith("BR90") or command.startswith("BL90"):
            time.append(8)

        # SNAP (picture taking)
        elif command.startswith("SNAP"):
            time.append(0)

        # Finish
        elif command.startswith("FIN"):
            time.append(0)

        else:
            # Safety fallback
            raise Exception(f"Unknown command in time_generator: {command}")
    
    return time
