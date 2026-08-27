from typing import List
from consts import Direction, EXPANDED_CELL, SNAPSHOT_COST
from helper import withinBounds


class CellState:
    """Base class for all objects on the arena, such as cells, obstacles, etc"""

    def __init__(self, x, y, direction: Direction = Direction.NORTH, screenshot_id=-1, penalty=0):
        # Use x/y (MazeSolver expects these). Keep pos_x/pos_y as backwards-compatible aliases.
        self.x = x
        self.y = y
        self.pos_x = x
        self.pos_y = y

        self.direction = direction
        self.screenshot_id = screenshot_id  # If screenshot_id != -1, snapshot is for obstacle with id = screenshot_id
        self.penalty = penalty  # Penalty for the viewpoint of taking picture

    def cmpPosition(self, x, y) -> bool:
        return self.x == x and self.y == y

    def isEq(self, x, y, direction):
        return self.x == x and self.y == y and self.direction == direction

    def __repr__(self):
        return f"x: {self.x}, y: {self.y}, d: {self.direction}, screenshot: {self.screenshot_id}"

    def setScreenshot(self, screenshot_id):
        self.screenshot_id = screenshot_id

    def getDict(self):
        return {'x': self.x, 'y': self.y, 'd': self.direction, 's': self.screenshot_id}


class Obstacle(CellState):
    """Obstacle class, inherited from CellState"""

    def __init__(self, x: int, y: int, direction: Direction, obstacle_id: int):
        super().__init__(x, y, direction)
        self.obstacle_id = obstacle_id

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y and self.direction == other.direction

    def getViewState(self, retrying) -> List[CellState]:
        """Constructs list of CellStates from which the robot can view the symbol on the obstacle"""
        cells = []

        # If obstacle is facing north, robot must face south
        if self.direction == Direction.NORTH:
            if not retrying:
                if withinBounds(self.pos_x, self.pos_y + 1 + EXPANDED_CELL * 2):
                    cells.append(CellState(self.pos_x, self.pos_y + 1 + EXPANDED_CELL * 2, Direction.SOUTH, self.obstacle_id, 5))
                if withinBounds(self.pos_x, self.pos_y + 2 + EXPANDED_CELL * 2):
                    cells.append(CellState(self.pos_x, self.pos_y + 2 + EXPANDED_CELL * 2, Direction.SOUTH, self.obstacle_id, 0))
                if withinBounds(self.pos_x + 1, self.pos_y + 2 + EXPANDED_CELL * 2):
                    cells.append(CellState(self.pos_x + 1, self.pos_y + 2 + EXPANDED_CELL * 2, Direction.SOUTH, self.obstacle_id, SNAPSHOT_COST))
                if withinBounds(self.pos_x - 1, self.pos_y + 2 + EXPANDED_CELL * 2):
                    cells.append(CellState(self.pos_x - 1, self.pos_y + 2 + EXPANDED_CELL * 2, Direction.SOUTH, self.obstacle_id, SNAPSHOT_COST))
            else:
                if withinBounds(self.pos_x, self.pos_y + 2 + EXPANDED_CELL * 2):
                    cells.append(CellState(self.pos_x, self.pos_y + 2 + EXPANDED_CELL * 2, Direction.SOUTH, self.obstacle_id, 0))
                if withinBounds(self.pos_x, self.pos_y + 3 + EXPANDED_CELL * 2):
                    cells.append(CellState(self.pos_x, self.pos_y + 3 + EXPANDED_CELL * 2, Direction.SOUTH, self.obstacle_id, 0))
                if withinBounds(self.pos_x + 1, self.pos_y + 2 + EXPANDED_CELL * 2):
                    cells.append(CellState(self.pos_x + 1, self.pos_y + 2 + EXPANDED_CELL * 2, Direction.SOUTH, self.obstacle_id, SNAPSHOT_COST))
                if withinBounds(self.pos_x - 1, self.pos_y + 2 + EXPANDED_CELL * 2):
                    cells.append(CellState(self.pos_x - 1, self.pos_y + 2 + EXPANDED_CELL * 2, Direction.SOUTH, self.obstacle_id, SNAPSHOT_COST))

        # Facing south → robot faces north
        elif self.direction == Direction.SOUTH:
            if not retrying:
                if withinBounds(self.pos_x, self.pos_y - 1 - EXPANDED_CELL * 2):
                    cells.append(CellState(self.pos_x, self.pos_y - 1 - EXPANDED_CELL * 2, Direction.NORTH, self.obstacle_id, 5))
                if withinBounds(self.pos_x, self.pos_y - 2 - EXPANDED_CELL * 2):
                    cells.append(CellState(self.pos_x, self.pos_y - 2 - EXPANDED_CELL * 2, Direction.NORTH, self.obstacle_id, 0))
                if withinBounds(self.pos_x + 1, self.pos_y - 2 - EXPANDED_CELL * 2):
                    cells.append(CellState(self.pos_x + 1, self.pos_y - 2 - EXPANDED_CELL * 2, Direction.NORTH, self.obstacle_id, SNAPSHOT_COST))
                if withinBounds(self.pos_x - 1, self.pos_y - 2 - EXPANDED_CELL * 2):
                    cells.append(CellState(self.pos_x - 1, self.pos_y - 2 - EXPANDED_CELL * 2, Direction.NORTH, self.obstacle_id, SNAPSHOT_COST))
            else:
                if withinBounds(self.pos_x, self.pos_y - 2 - EXPANDED_CELL * 2):
                    cells.append(CellState(self.pos_x, self.pos_y - 2 - EXPANDED_CELL * 2, Direction.NORTH, self.obstacle_id, 0))
                if withinBounds(self.pos_x, self.pos_y - 3 - EXPANDED_CELL * 2):
                    cells.append(CellState(self.pos_x, self.pos_y - 3 - EXPANDED_CELL * 2, Direction.NORTH, self.obstacle_id, 0))
                if withinBounds(self.pos_x + 1, self.pos_y - 2 - EXPANDED_CELL * 2):
                    cells.append(CellState(self.pos_x + 1, self.pos_y - 2 - EXPANDED_CELL * 2, Direction.NORTH, self.obstacle_id, SNAPSHOT_COST))
                if withinBounds(self.pos_x - 1, self.pos_y - 2 - EXPANDED_CELL * 2):
                    cells.append(CellState(self.pos_x - 1, self.pos_y - 2 - EXPANDED_CELL * 2, Direction.NORTH, self.obstacle_id, SNAPSHOT_COST))

        # Facing east → robot faces west
        elif self.direction == Direction.EAST:
            if not retrying:
                if withinBounds(self.pos_x + 1 + EXPANDED_CELL * 2, self.pos_y):
                    cells.append(CellState(self.pos_x + 1 + EXPANDED_CELL * 2, self.pos_y, Direction.WEST, self.obstacle_id, 5))
                if withinBounds(self.pos_x + 2 + EXPANDED_CELL * 2, self.pos_y):
                    cells.append(CellState(self.pos_x + 2 + EXPANDED_CELL * 2, self.pos_y, Direction.WEST, self.obstacle_id, 0))
                if withinBounds(self.pos_x + 2 + EXPANDED_CELL * 2, self.pos_y + 1):
                    cells.append(CellState(self.pos_x + 2 + EXPANDED_CELL * 2, self.pos_y + 1, Direction.WEST, self.obstacle_id, SNAPSHOT_COST))
                if withinBounds(self.pos_x + 2 + EXPANDED_CELL * 2, self.pos_y - 1):
                    cells.append(CellState(self.pos_x + 2 + EXPANDED_CELL * 2, self.pos_y - 1, Direction.WEST, self.obstacle_id, SNAPSHOT_COST))
            else:
                if withinBounds(self.pos_x + 2 + EXPANDED_CELL * 2, self.pos_y):
                    cells.append(CellState(self.pos_x + 2 + EXPANDED_CELL * 2, self.pos_y, Direction.WEST, self.obstacle_id, 0))
                if withinBounds(self.pos_x + 3 + EXPANDED_CELL * 2, self.pos_y):
                    cells.append(CellState(self.pos_x + 3 + EXPANDED_CELL * 2, self.pos_y, Direction.WEST, self.obstacle_id, 0))
                if withinBounds(self.pos_x + 2 + EXPANDED_CELL * 2, self.pos_y + 1):
                    cells.append(CellState(self.pos_x + 2 + EXPANDED_CELL * 2, self.pos_y + 1, Direction.WEST, self.obstacle_id, SNAPSHOT_COST))
                if withinBounds(self.pos_x + 2 + EXPANDED_CELL * 2, self.pos_y - 1):
                    cells.append(CellState(self.pos_x + 2 + EXPANDED_CELL * 2, self.pos_y - 1, Direction.WEST, self.obstacle_id, SNAPSHOT_COST))

        # Facing west → robot faces east
        elif self.direction == Direction.WEST:
            if not retrying:
                if withinBounds(self.pos_x - 1 - EXPANDED_CELL * 2, self.pos_y):
                    cells.append(CellState(self.pos_x - 1 - EXPANDED_CELL * 2, self.pos_y, Direction.EAST, self.obstacle_id, 5))
                if withinBounds(self.pos_x - 2 - EXPANDED_CELL * 2, self.pos_y):
                    cells.append(CellState(self.pos_x - 2 - EXPANDED_CELL * 2, self.pos_y, Direction.EAST, self.obstacle_id, 0))
                if withinBounds(self.pos_x - 2 - EXPANDED_CELL * 2, self.pos_y + 1):
                    cells.append(CellState(self.pos_x - 2 - EXPANDED_CELL * 2, self.pos_y + 1, Direction.EAST, self.obstacle_id, SNAPSHOT_COST))
                if withinBounds(self.pos_x - 2 - EXPANDED_CELL * 2, self.pos_y - 1):
                    cells.append(CellState(self.pos_x - 2 - EXPANDED_CELL * 2, self.pos_y - 1, Direction.EAST, self.obstacle_id, SNAPSHOT_COST))
            else:
                if withinBounds(self.pos_x - 2 - EXPANDED_CELL * 2, self.pos_y):
                    cells.append(CellState(self.pos_x - 2 - EXPANDED_CELL * 2, self.pos_y, Direction.EAST, self.obstacle_id, 0))
                if withinBounds(self.pos_x - 3 - EXPANDED_CELL * 2, self.pos_y):
                    cells.append(CellState(self.pos_x - 3 - EXPANDED_CELL * 2, self.pos_y, Direction.EAST, self.obstacle_id, 0))
                if withinBounds(self.pos_x - 2 - EXPANDED_CELL * 2, self.pos_y + 1):
                    cells.append(CellState(self.pos_x - 2 - EXPANDED_CELL * 2, self.pos_y + 1, Direction.EAST, self.obstacle_id, SNAPSHOT_COST))
                if withinBounds(self.pos_x - 2 - EXPANDED_CELL * 2, self.pos_y - 1):
                    cells.append(CellState(self.pos_x - 2 - EXPANDED_CELL * 2, self.pos_y - 1, Direction.EAST, self.obstacle_id, SNAPSHOT_COST))

        return cells


class Grid:
    """Grid containing size and obstacles"""

    def __init__(self, size_x: int, size_y: int):
        self.size_x = size_x
        self.size_y = size_y
        self.obstacles: List[Obstacle] = []
        self._reachable_cache = None

    def addObstacle(self, obstacle: Obstacle):
        if not any(ob == obstacle for ob in self.obstacles):
            self.obstacles.append(obstacle)
            self._reachable_cache = None

    def reset_obstacles(self):
        self.obstacles = []
        self._reachable_cache = None

    def get_obstacles(self):
        return self.obstacles

    def _reachable_uncached(self, x: int, y: int, turn=False, preTurn=False) -> bool:
        if not self.within_bounds_coord(x, y):
            return False

        for ob in self.obstacles:
            if ob.x == 4 and ob.y <= 4 and x < 4 and y < 4:
                continue
            if abs(ob.x - x) + abs(ob.y - y) >= 4:
                continue
            if turn or preTurn:
                if max(abs(ob.x - x), abs(ob.y - y)) < EXPANDED_CELL * 2 + 1:
                    return False
            else:
                if max(abs(ob.x - x), abs(ob.y - y)) < 3:
                    return False

        return True

    def _build_reachable_cache(self):
        cache = {}
        for x in range(self.size_x):
            for y in range(self.size_y):
                for turn in (False, True):
                    for preTurn in (False, True):
                        cache[(x, y, turn, preTurn)] = self._reachable_uncached(x, y, turn, preTurn)
        self._reachable_cache = cache

    def reachable(self, x: int, y: int, turn=False, preTurn=False) -> bool:
        if self._reachable_cache is None:
            self._build_reachable_cache()
        return self._reachable_cache.get((x, y, turn, preTurn), False)

    def within_bounds_coord(self, x: int, y: int) -> bool:
        return not (x < 1 or x >= self.size_x - 1 or y < 1 or y >= self.size_y - 1)

    def within_bounds_cell_state(self, state: CellState) -> bool:
        return self.within_bounds_coord(state.pos_x, state.pos_y)

    def get_view_obstacle_positions(self, retrying) -> List[List[CellState]]:
        optimal_positions = []
        for obstacle in self.obstacles:
            if obstacle.direction == 8:
                continue
            view_states = [vs for vs in obstacle.getViewState(retrying) if self.reachable(vs.x, vs.y)]
            optimal_positions.append(view_states)
        return optimal_positions
