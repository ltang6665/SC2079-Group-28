import heapq
import math
from typing import List
import numpy as np
from pathfinding.entities.Robot import Robot
from pathfinding.entities.Entity import Obstacle, CellState, Grid
from pathfinding.consts import Direction, MOVE_DIRECTION, TURN_FACTOR, ITERATIONS, TURN_RADIUS, SAFE_COST, TURN_BIG, TURN_SMALL
from python_tsp.exact import solve_tsp_dynamic_programming

turn_wrt_big_turns = [
    [TURN_BIG,     TURN_SMALL],
    [TURN_BIG + 1, TURN_SMALL]
]


class MazeSolver:
    def __init__(
            self,
            size_x: int,
            size_y: int,
            robot_x: int,
            robot_y: int,
            robot_direction: Direction,
            big_turn=None, # the big_turn here is to allow 3-1 turn(0 - by default) | 4-2 turn(1)
            allow_45 = True
    ):
        # Initialize a Grid object for the arena representation
        self.grid = Grid(size_x, size_y)
        # Initialize a Robot object for robot representation
        self.robot = Robot(robot_x, robot_y, robot_direction)
        # Create tables for paths and costs
        self.path_table = dict()
        self.cost_table = dict()
        if big_turn is None:
            self.big_turn = 0
        else:
            self.big_turn = int(big_turn)
        self.allow_45 = allow_45
        self._safe_cost_cache = None

    def addObstacle(self, x: int, y: int, direction: Direction, obstacle_id: int):
        """Add obstacle to MazeSolver object

        Args:
            x (int): x coordinate of obstacle
            y (int): y coordinate of obstacle
            direction (Direction): Direction of obstacle
            obstacle_id (int): ID of obstacle
        """
        obstacle = Obstacle(x, y, direction, obstacle_id)
        self.grid.addObstacle(obstacle)
        self._safe_cost_cache = None

    def resetObstacles(self):
        self.grid.reset_obstacles()
        self._safe_cost_cache = None

    @staticmethod
    def computeCoordDistance(x1: int, y1: int, x2: int, y2: int, level=1):
        """Compute the L-n distance between two coordinates

        Args:
            x1 (int)
            y1 (int)
            x2 (int)
            y2 (int)
            level (int, optional): L-n distance to compute. Defaults to 1.

        Returns:
            float: L-n distance between the two given points
        """
        horizontal_distance = x1 - x2
        vertical_distance = y1 - y2

        if level == 2:
            return math.sqrt(horizontal_distance ** 2 + vertical_distance ** 2)

        return abs(horizontal_distance) + abs(vertical_distance)

    @staticmethod
    def computeStateDistance(start_state: CellState, end_state: CellState, level=1):
        """Compute the L-n distance between two cell states

        Args:
            start_state (CellState): Start cell state
            end_state (CellState): End cell state
            level (int, optional): L-n distance to compute. Defaults to 1.

        Returns:
            float: L-n distance between the two given cell states
        """
        return MazeSolver.computeCoordDistance(start_state.x, start_state.y, end_state.x, end_state.y, level)

    @staticmethod
    def getVisitOptions(n):
        """Generate all possible n-digit binary strings

        Args:
            n (int): number of digits in binary string to generate

        Returns:
            List: list of all possible n-digit binary strings
        """
        s = []
        l = bin(2 ** n - 1).count('1')

        for i in range(2 ** n):
            s.append(bin(i)[2:].zfill(l))

        s.sort(key=lambda x: x.count('1'), reverse=True)
        return s

    def getOptimalOrderDp(self, retrying) -> List[CellState]:
        distance = 1e9
        optimal_path = []
        all_view_positions = self.grid.get_view_obstacle_positions(retrying)

        for op in self.getVisitOptions(len(all_view_positions)):
            # op is binary string of length len(all_view_positions) == len(obstacles)
            # If index == 1 means the view_positions[index] is selected to visit, otherwise drop

            # Calculate optimal_cost table

            # Initialize `items` to be a list containing the robot's start state as the first item
            items = [self.robot.get_start_state()]
            # Initialize `cur_view_positions` to be an empty list
            cur_view_positions = []
            
            # print(f"===================\nop = {op}")
            # print("List of obstacle visited: \n")

            # For each obstacle
            for idx in range(len(all_view_positions)):
                # If robot is visiting
                if op[idx] == '1':
                    # Add possible cells to `items`
                    items = items + all_view_positions[idx]
                    # Add possible cells to `cur_view_positions`
                    cur_view_positions.append(all_view_positions[idx])
                    #print("obstacle: {}\n".format(self.grid.obstacles[idx]))

            self.pathCostGenerator(items)
            combination = []
            self.generateCombination(cur_view_positions, 0, [], combination, [ITERATIONS])

            for c in combination: # run the algo some times ->
                visited_candidates = [0] # add the start state of the robot

                cur_index = 1
                fixed_cost = 0 # the cost applying for the position taking obstacle pictures
                for index, view_position in enumerate(cur_view_positions):
                    visited_candidates.append(cur_index + c[index])
                    fixed_cost += view_position[c[index]].penalty
                    cur_index += len(view_position)
                
                cost_np = np.zeros((len(visited_candidates), len(visited_candidates)))

                for s in range(len(visited_candidates) - 1):
                    for e in range(s + 1, len(visited_candidates)):
                        u = items[visited_candidates[s]]
                        v = items[visited_candidates[e]]
                        if (u, v) in self.cost_table.keys():
                            cost_np[s][e] = self.cost_table[(u, v)]
                        else:
                            cost_np[s][e] = 1e9
                        cost_np[e][s] = cost_np[s][e]
                cost_np[:, 0] = 0
                _permutation, _distance = solve_tsp_dynamic_programming(cost_np)
                # print(f"fixed_cost = {fixed_cost}")
                # print(f"distance = {_distance}")
                if _distance + fixed_cost >= distance:
                    continue

                optimal_path = [items[0]]
                distance = _distance + fixed_cost

                for i in range(len(_permutation) - 1):
                    from_item = items[visited_candidates[_permutation[i]]]
                    to_item = items[visited_candidates[_permutation[i + 1]]]

                    cur_path = self.path_table[(from_item, to_item)]
                    for j in range(1, len(cur_path)):
                        optimal_path.append(CellState(cur_path[j][0], cur_path[j][1], cur_path[j][2]))

                    optimal_path[-1].set_screenshot(to_item.screenshot_id)

            if optimal_path:
                # if found optimal path, return
                break

        return optimal_path, distance

    @staticmethod
    def generateCombination(view_positions, index, current, result, iteration_left):
        if index == len(view_positions):
            result.append(current[:])
            return

        if iteration_left[0] == 0:
            return

        iteration_left[0] -= 1
        for j in range(len(view_positions[index])):
            current.append(j)
            MazeSolver.generateCombination(view_positions, index + 1, current, result, iteration_left)
            current.pop()

    def _buildSafeCostCache(self):
        cache = {}
        for x in range(self.grid.size_x):
            for y in range(self.grid.size_y):
                cost = 0
                for ob in self.grid.obstacles:
                    if ((abs(ob.x - x) == 2 and abs(ob.y - y) == 2) or
                            (abs(ob.x - x) == 1 and abs(ob.y - y) == 2) or
                            (abs(ob.x - x) == 2 and abs(ob.y - y) == 1) or
                            (abs(ob.x - x) <= 1 and abs(ob.y - y) <= 1)):
                        cost = SAFE_COST
                        break
                cache[(x, y)] = cost
        self._safe_cost_cache = cache

    def getSafeCost(self, x, y):
        """Get the safe cost of a particular x,y coordinate wrt obstacles that are exactly 2 units away from it in both x and y directions

        Args:
            x (int): x-coordinate
            y (int): y-coordinate

        Returns:
            int: safe cost
        """
        if self._safe_cost_cache is None:
            self._buildSafeCostCache()
        return self._safe_cost_cache.get((x, y), 0)

    # def get_neighbors(self, x, y, direction):  # TODO: see the behavior of the robot and adjust...
    #     """
    #     Return a list of tuples with format:
    #     newX, newY, new_direction
    #     """
    #     # Neighbors have the following format: {newX, newY, movement direction, safe cost}
    #     # Neighbors are coordinates that fulfill the following criteria:
    #     # If moving in the same direction:
    #     #   - Valid position within bounds
    #     #   - Must be at least 4 units away in total (x+y) 
    #     #   - Furthest distance must be at least 3 units away (x or y)
    #     # If it is exactly 2 units away in both x and y directions, safe cost = SAFECOST. Else, safe cost = 0

    #     neighbors = []
    #     # Assume that after following this direction, the car direction is EXACTLY md
    #     for dx, dy, md in MOVE_DIRECTION:
    #         if md == direction:  # if the new direction == md
    #             # Check for valid position
    #             if self.grid.reachable(x + dx, y + dy):  # go forward;
    #                 # Get safe cost of destination
    #                 safe_cost = self.get_safe_cost(x + dx, y + dy)
    #                 neighbors.append((x + dx, y + dy, md, safe_cost))
    #             # Check for valid position
    #             if self.grid.reachable(x - dx, y - dy):  # go back;
    #                 # Get safe cost of destination
    #                 safe_cost = self.get_safe_cost(x - dx, y - dy)
    #                 neighbors.append((x - dx, y - dy, md, safe_cost))

    #         else:  # consider 8 cases
                
    #             # Turning displacement is either 4-2 or 3-1
    #             bigger_change = turn_wrt_big_turns[self.big_turn][0]
    #             smaller_change = turn_wrt_big_turns[self.big_turn][1]

    #             # north <-> east
    #             if direction == Direction.NORTH and md == Direction.EAST:

    #                 # Check for valid position
    #                 if self.grid.reachable(x + bigger_change, y + smaller_change, turn = True) and self.grid.reachable(x, y, preTurn = True):
    #                     # Get safe cost of destination
    #                     safe_cost = self.get_safe_cost(x + bigger_change, y + smaller_change)
    #                     neighbors.append((x + bigger_change, y + smaller_change, md, safe_cost + 10))

    #                 # Check for valid position
    #                 if self.grid.reachable(x - smaller_change, y - bigger_change, turn = True) and self.grid.reachable(x, y, preTurn = True):
    #                     # Get safe cost of destination
    #                     safe_cost = self.get_safe_cost(x - smaller_change, y - bigger_change)
    #                     neighbors.append((x - smaller_change, y - bigger_change, md, safe_cost + 10))

    #             if direction == Direction.EAST and md == Direction.NORTH:
    #                 if self.grid.reachable(x + smaller_change, y + bigger_change, turn = True) and self.grid.reachable(x, y, preTurn = True):
    #                     safe_cost = self.get_safe_cost(x + smaller_change, y + bigger_change)
    #                     neighbors.append((x + smaller_change, y + bigger_change, md, safe_cost + 10))

    #                 if self.grid.reachable(x - bigger_change, y - smaller_change, turn = True) and self.grid.reachable(x, y, preTurn = True):
    #                     safe_cost = self.get_safe_cost(x - bigger_change, y - smaller_change)
    #                     neighbors.append((x - bigger_change, y - smaller_change, md, safe_cost + 10))

    #             # east <-> south
    #             if direction == Direction.EAST and md == Direction.SOUTH:
                    
    #                 if self.grid.reachable(x + smaller_change, y - bigger_change, turn = True) and self.grid.reachable(x, y, preTurn = True):
    #                     safe_cost = self.get_safe_cost(x + smaller_change, y - bigger_change)
    #                     neighbors.append((x + smaller_change, y - bigger_change, md, safe_cost + 10))

    #                 if self.grid.reachable(x - bigger_change, y + smaller_change, turn = True) and self.grid.reachable(x, y, preTurn = True):
    #                     safe_cost = self.get_safe_cost(x - bigger_change, y + smaller_change)
    #                     neighbors.append((x - bigger_change, y + smaller_change, md, safe_cost + 10))

    #             if direction == Direction.SOUTH and md == Direction.EAST:
    #                 if self.grid.reachable(x + bigger_change, y - smaller_change, turn = True) and self.grid.reachable(x, y, preTurn = True):
    #                     safe_cost = self.get_safe_cost(x + bigger_change, y - smaller_change)
    #                     neighbors.append((x + bigger_change, y - smaller_change, md, safe_cost + 10))

    #                 if self.grid.reachable(x - smaller_change, y + bigger_change, turn = True) and self.grid.reachable(x, y, preTurn = True):
    #                     safe_cost = self.get_safe_cost(x - smaller_change, y + bigger_change)
    #                     neighbors.append((x - smaller_change, y + bigger_change, md, safe_cost + 10))

    #             # south <-> west
    #             if direction == Direction.SOUTH and md == Direction.WEST:
    #                 if self.grid.reachable(x - bigger_change, y - smaller_change, turn = True) and self.grid.reachable(x, y, preTurn = True):
    #                     safe_cost = self.get_safe_cost(x - bigger_change, y - smaller_change)
    #                     neighbors.append((x - bigger_change, y - smaller_change, md, safe_cost + 10))

    #                 if self.grid.reachable(x + smaller_change, y + bigger_change, turn = True) and self.grid.reachable(x, y, preTurn = True):
    #                     safe_cost = self.get_safe_cost(x + smaller_change, y + bigger_change)
    #                     neighbors.append((x + smaller_change, y + bigger_change, md, safe_cost + 10))

    #             if direction == Direction.WEST and md == Direction.SOUTH:
    #                 if self.grid.reachable(x - smaller_change, y - bigger_change, turn = True) and self.grid.reachable(x, y, preTurn = True):
    #                     safe_cost = self.get_safe_cost(x - smaller_change, y - bigger_change)
    #                     neighbors.append((x - smaller_change, y - bigger_change, md, safe_cost + 10))

    #                 if self.grid.reachable(x + bigger_change, y + smaller_change, turn = True) and self.grid.reachable(x, y, preTurn = True):
    #                     safe_cost = self.get_safe_cost(x + bigger_change, y + smaller_change)
    #                     neighbors.append((x + bigger_change, y + smaller_change, md, safe_cost + 10))

    #             # west <-> north
    #             if direction == Direction.WEST and md == Direction.NORTH:
    #                 if self.grid.reachable(x - smaller_change, y + bigger_change, turn = True) and self.grid.reachable(x, y, preTurn = True):
    #                     safe_cost = self.get_safe_cost(x - smaller_change, y + bigger_change)
    #                     neighbors.append((x - smaller_change, y + bigger_change, md, safe_cost + 10))

    #                 if self.grid.reachable(x + bigger_change, y - smaller_change, turn = True) and self.grid.reachable(x, y, preTurn = True):
    #                     safe_cost = self.get_safe_cost(x + bigger_change, y - smaller_change)
    #                     neighbors.append((x + bigger_change, y - smaller_change, md, safe_cost + 10))

    #             if direction == Direction.NORTH and md == Direction.WEST:
    #                 if self.grid.reachable(x + smaller_change, y - bigger_change, turn = True) and self.grid.reachable(x, y, preTurn = True):
    #                     safe_cost = self.get_safe_cost(x + smaller_change, y - bigger_change)
    #                     neighbors.append((x + smaller_change, y - bigger_change, md, safe_cost + 10))

    #                 if self.grid.reachable(x - bigger_change, y + smaller_change, turn = True) and self.grid.reachable(x, y, preTurn = True):
    #                     safe_cost = self.get_safe_cost(x - bigger_change, y + smaller_change)
    #                     neighbors.append((x - bigger_change, y + smaller_change, md, safe_cost + 10))

    #     return neighbors

    def _hasForwardClearance(self, x, y, direction, steps=2):
        """True if `steps` cells directly ahead are reachable (for pre-turn safety)."""
        fwd = {Direction.NORTH: (0, 1), Direction.EAST: (1, 0),
               Direction.SOUTH: (0, -1), Direction.WEST: (-1, 0)}
        if direction not in fwd:
            return True
        fdx, fdy = fwd[direction]
        return all(self.grid.reachable(x + fdx * s, y + fdy * s) for s in range(1, steps + 1))

    def _hasBackwardClearance(self, x, y, direction, steps=2):
        """True if `steps` cells directly behind are reachable (for reverse-turn safety)."""
        bwd = {Direction.NORTH: (0, -1), Direction.EAST: (-1, 0),
               Direction.SOUTH: (0, 1), Direction.WEST: (1, 0)}
        if direction not in bwd:
            return True
        bdx, bdy = bwd[direction]
        return all(self.grid.reachable(x + bdx * s, y + bdy * s) for s in range(1, steps + 1))

    def getNeighbors(self, x, y, direction):
        neighbors = []

        for dx, dy, md in MOVE_DIRECTION:
            if md == direction:
                if self.grid.reachable(x + dx, y + dy):
                    safe_cost = self.getSafeCost(x + dx, y + dy)
                    neighbors.append((x + dx, y + dy, md, safe_cost))
                if self.grid.reachable(x - dx, y - dy):
                    safe_cost = self.getSafeCost(x - dx, y - dy)
                    neighbors.append((x - dx, y - dy, md, safe_cost))

        if self.allow_45:
            for dx, dy, md in MOVE_DIRECTION:
                diff = (int(md) - int(direction)) % 8
                if diff in [1, 7]:
                    if self.grid.reachable(x + dx, y + dy, turn=True) and self.grid.reachable(x, y, preTurn=True):
                        safe_cost = self.getSafeCost(x + dx, y + dy)
                        neighbors.append((x + dx, y + dy, md, safe_cost + 5))

        bigger_change = turn_wrt_big_turns[self.big_turn][0]
        smaller_change = turn_wrt_big_turns[self.big_turn][1]
        _fvec = {Direction.NORTH: (0, 1), Direction.EAST: (1, 0),
                 Direction.SOUTH: (0, -1), Direction.WEST: (-1, 0)}
        fwd_penalty = 0 if self._hasForwardClearance(x, y, direction) else SAFE_COST
        bwd_clear = self._hasBackwardClearance(x, y, direction)
        fvec = _fvec.get(direction, (0, 0))

        if direction == Direction.NORTH:
            if self.grid.reachable(x + bigger_change, y + smaller_change, turn=True) and self.grid.reachable(x, y, preTurn=True):
                safe_cost = self.getSafeCost(x + bigger_change, y + smaller_change)
                neighbors.append((x + bigger_change, y + smaller_change, Direction.EAST, safe_cost + 10 + fwd_penalty))
            if bwd_clear and self.grid.reachable(x - smaller_change, y - bigger_change, turn=True) and self.grid.reachable(x, y, preTurn=True):
                safe_cost = self.getSafeCost(x - smaller_change, y - bigger_change)
                neighbors.append((x - smaller_change, y - bigger_change, Direction.EAST, safe_cost + 10))
            if self.grid.reachable(x - bigger_change, y + smaller_change, turn=True) and self.grid.reachable(x, y, preTurn=True):
                safe_cost = self.getSafeCost(x - bigger_change, y + smaller_change)
                neighbors.append((x - bigger_change, y + smaller_change, Direction.WEST, safe_cost + 10 + fwd_penalty))
            if bwd_clear and self.grid.reachable(x + smaller_change, y - bigger_change, turn=True) and self.grid.reachable(x, y, preTurn=True):
                safe_cost = self.getSafeCost(x + smaller_change, y - bigger_change)
                neighbors.append((x + smaller_change, y - bigger_change, Direction.WEST, safe_cost + 10))

        elif direction == Direction.EAST:
            if self.grid.reachable(x + smaller_change, y + bigger_change, turn=True) and self.grid.reachable(x, y, preTurn=True):
                safe_cost = self.getSafeCost(x + smaller_change, y + bigger_change)
                neighbors.append((x + smaller_change, y + bigger_change, Direction.NORTH, safe_cost + 10 + fwd_penalty))
            if bwd_clear and self.grid.reachable(x - bigger_change, y - smaller_change, turn=True) and self.grid.reachable(x, y, preTurn=True):
                safe_cost = self.getSafeCost(x - bigger_change, y - smaller_change)
                neighbors.append((x - bigger_change, y - smaller_change, Direction.NORTH, safe_cost + 10))
            if self.grid.reachable(x + smaller_change, y - bigger_change, turn=True) and self.grid.reachable(x, y, preTurn=True):
                safe_cost = self.getSafeCost(x + smaller_change, y - bigger_change)
                neighbors.append((x + smaller_change, y - bigger_change, Direction.SOUTH, safe_cost + 10 + fwd_penalty))
            if bwd_clear and self.grid.reachable(x - bigger_change, y + smaller_change, turn=True) and self.grid.reachable(x, y, preTurn=True):
                safe_cost = self.getSafeCost(x - bigger_change, y + smaller_change)
                neighbors.append((x - bigger_change, y + smaller_change, Direction.SOUTH, safe_cost + 10))

        elif direction == Direction.SOUTH:
            if self.grid.reachable(x + bigger_change, y - smaller_change, turn=True) and self.grid.reachable(x, y, preTurn=True):
                safe_cost = self.getSafeCost(x + bigger_change, y - smaller_change)
                neighbors.append((x + bigger_change, y - smaller_change, Direction.EAST, safe_cost + 10 + fwd_penalty))
            if bwd_clear and self.grid.reachable(x - smaller_change, y + bigger_change, turn=True) and self.grid.reachable(x, y, preTurn=True):
                safe_cost = self.getSafeCost(x - smaller_change, y + bigger_change)
                neighbors.append((x - smaller_change, y + bigger_change, Direction.EAST, safe_cost + 10))
            if self.grid.reachable(x - bigger_change, y - smaller_change, turn=True) and self.grid.reachable(x, y, preTurn=True):
                safe_cost = self.getSafeCost(x - bigger_change, y - smaller_change)
                neighbors.append((x - bigger_change, y - smaller_change, Direction.WEST, safe_cost + 10 + fwd_penalty))
            if bwd_clear and self.grid.reachable(x + smaller_change, y + bigger_change, turn=True) and self.grid.reachable(x, y, preTurn=True):
                safe_cost = self.getSafeCost(x + smaller_change, y + bigger_change)
                neighbors.append((x + smaller_change, y + bigger_change, Direction.WEST, safe_cost + 10))

        elif direction == Direction.WEST:
            if self.grid.reachable(x - smaller_change, y - bigger_change, turn=True) and self.grid.reachable(x, y, preTurn=True):
                safe_cost = self.getSafeCost(x - smaller_change, y - bigger_change)
                neighbors.append((x - smaller_change, y - bigger_change, Direction.SOUTH, safe_cost + 10 + fwd_penalty))
            if bwd_clear and self.grid.reachable(x + bigger_change, y + smaller_change, turn=True) and self.grid.reachable(x, y, preTurn=True):
                safe_cost = self.getSafeCost(x + bigger_change, y + smaller_change)
                neighbors.append((x + bigger_change, y + smaller_change, Direction.SOUTH, safe_cost + 10))
            if self.grid.reachable(x - smaller_change, y + bigger_change, turn=True) and self.grid.reachable(x, y, preTurn=True):
                safe_cost = self.getSafeCost(x - smaller_change, y + bigger_change)
                neighbors.append((x - smaller_change, y + bigger_change, Direction.NORTH, safe_cost + 10 + fwd_penalty))
            if bwd_clear and self.grid.reachable(x + bigger_change, y - smaller_change, turn=True) and self.grid.reachable(x, y, preTurn=True):
                safe_cost = self.getSafeCost(x + bigger_change, y - smaller_change)
                neighbors.append((x + bigger_change, y - smaller_change, Direction.NORTH, safe_cost + 10))

        return neighbors

    def pathCostGenerator(self, states: List[CellState]):
        """Generate the path cost between the input states and update the tables accordingly

        Args:
            states (List[CellState]): cell states to visit
        """
        def record_path(start, end, parent: dict, cost: int):
            self.cost_table[(start, end)] = cost
            self.cost_table[(end, start)] = cost

            path = []
            cursor = (end.x, end.y, end.direction)

            while cursor in parent:
                path.append(cursor)
                cursor = parent[cursor]

            path.append(cursor)

            self.path_table[(start, end)] = path[::-1]
            self.path_table[(end, start)] = path

        def astar_search(start: CellState, end: CellState):
            if (start, end) in self.path_table:
                return

            g_distance = {(start.x, start.y, start.direction): 0}
            heap = [(self.computeStateDistance(start, end), start.x, start.y, start.direction)]
            parent = dict()
            visited = set()

            while heap:
                _, cur_x, cur_y, cur_direction = heapq.heappop(heap)
                
                if (cur_x, cur_y, cur_direction) in visited:
                    continue

                if end.is_eq(cur_x, cur_y, cur_direction):
                    record_path(start, end, parent, g_distance[(cur_x, cur_y, cur_direction)])
                    return

                visited.add((cur_x, cur_y, cur_direction))
                cur_distance = g_distance[(cur_x, cur_y, cur_direction)]

                for next_x, next_y, new_direction, safe_cost in self.getNeighbors(cur_x, cur_y, cur_direction):
                    if (next_x, next_y, new_direction) in visited:
                        continue
                    
                    step_cost = math.sqrt((next_x - cur_x) ** 2 + (next_y - cur_y) ** 2)
                    move_cost = Direction.rotation_cost(new_direction, cur_direction) * TURN_FACTOR + step_cost + safe_cost

                    tentative_g = cur_distance + move_cost
                    next_cost = tentative_g + self.computeCoordDistance(next_x, next_y, end.x, end.y, level=2)

                    if (next_x, next_y, new_direction) not in g_distance or \
                            g_distance[(next_x, next_y, new_direction)] > tentative_g:
                        g_distance[(next_x, next_y, new_direction)] = tentative_g
                        parent[(next_x, next_y, new_direction)] = (cur_x, cur_y, cur_direction)

                        heapq.heappush(heap, (next_cost, next_x, next_y, new_direction))

        for i in range(len(states) - 1):
            for j in range(i + 1, len(states)):
                astar_search(states[i], states[j])

if __name__ == "__main__":
    pass