from typing import List
from pathfinding.consts import Direction, EXPANDED_CELL, SNAPSHOT_COST, NUM_VIEWPOINTS
from pathfinding.helper import withinBounds

class CellState:
    """Base class for all objects on the arena, such as cells, obstacles, etc"""

    def __init__(self, x, y, direction: Direction = Direction.NORTH, screenshot_id=-1, penalty=0):
        self.x = x
        self.y = y
        self.pos_x = x
        self.pos_y = y
        self.direction = direction
        # If screenshot_od != -1, the snapshot is taken at that position is for the obstacle with id = screenshot_id
        self.screenshot_id = screenshot_id
        self.penalty = penalty  # Penalty for the view point of taking picture

    def cmp_position(self, x, y) -> bool:
        """Compare given (x,y) position with cell state's position

        Args:
            x (int): x coordinate
            y (int): y coordinate

        Returns:
            bool: True if same, False otherwise
        """
        return self.x == x and self.y == y

    def is_eq(self, x, y, direction):
        """Compare given x, y, direction with cell state's position and direction

        Args:
            x (int): x coordinate
            y (int): y coordinate
            direction (Direction): direction of cell

        Returns:
            bool: True if same, False otherwise
        """
        return self.x == x and self.y == y and self.direction == direction

    def __repr__(self):
        return "x: {}, y: {}, d: {}, screenshot: {}".format(self.x, self.y, self.direction, self.screenshot_id)

    def set_screenshot(self, screenshot_id):
        """Set screenshot id for cell

        Args:
            screenshot_id (int): screenshot id of cell
        """
        self.screenshot_id = screenshot_id

    def getDict(self):
        """Returns a dictionary representation of the cell

        Returns:
            dict: {x,y,direction,screeshot_id}
        """
        return {'x': self.x, 'y': self.y, 'd': self.direction, 's': self.screenshot_id}


class Obstacle(CellState):
    """Obstacle class, inherited from CellState"""

    def __init__(self, x: int, y: int, direction: Direction, obstacle_id: int):
        super().__init__(x, y, direction)
        self.obstacle_id = obstacle_id

    def __eq__(self, other):
        """Checks if this obstacle is the same as input in terms of x, y, and direction

        Args:
            other (Obstacle): input obstacle to compare to

        Returns:
            bool: True if same, False otherwise
        """
        return self.x == other.x and self.y == other.y and self.direction == other.direction

    def getViewState6(self, retrying) -> List[CellState]:
        """Constructs list of CellStates from which the robot can view the symbol on the obstacle"""
        cells = []

        # If obstacle is facing north, robot must face south
        if self.direction == Direction.NORTH:
            if not retrying:
                # (x, y + 3), penalty 5
                if withinBounds(self.pos_x, self.pos_y + 1 + EXPANDED_CELL * 2):
                    cells.append(CellState(
                        self.pos_x,
                        self.pos_y + 1 + EXPANDED_CELL * 2,
                        Direction.SOUTH,
                        self.obstacle_id,
                        5
                    ))

                # (x, y + 4), penalty 0
                if withinBounds(self.pos_x, self.pos_y + 2 + EXPANDED_CELL * 2):
                    cells.append(CellState(
                        self.pos_x,
                        self.pos_y + 2 + EXPANDED_CELL * 2,
                        Direction.SOUTH,
                        self.obstacle_id,
                        0
                    ))

                # NEW: (x + 1, y + 3), penalty 100
                if withinBounds(self.pos_x + 1, self.pos_y + 1 + EXPANDED_CELL * 2):
                    cells.append(CellState(
                        self.pos_x + 1,
                        self.pos_y + 1 + EXPANDED_CELL * 2,
                        Direction.SOUTH,
                        self.obstacle_id,
                        SNAPSHOT_COST * 2
                    ))

                # NEW: (x - 1, y + 3), penalty 100
                if withinBounds(self.pos_x - 1, self.pos_y + 1 + EXPANDED_CELL * 2):
                    cells.append(CellState(
                        self.pos_x - 1,
                        self.pos_y + 1 + EXPANDED_CELL * 2,
                        Direction.SOUTH,
                        self.obstacle_id,
                        SNAPSHOT_COST * 2
                    ))

                # (x + 1, y + 4), penalty 50
                if withinBounds(self.pos_x + 1, self.pos_y + 2 + EXPANDED_CELL * 2):
                    cells.append(CellState(
                        self.pos_x + 1,
                        self.pos_y + 2 + EXPANDED_CELL * 2,
                        Direction.SOUTH,
                        self.obstacle_id,
                        SNAPSHOT_COST
                    ))

                # (x - 1, y + 4), penalty 50
                if withinBounds(self.pos_x - 1, self.pos_y + 2 + EXPANDED_CELL * 2):
                    cells.append(CellState(
                        self.pos_x - 1,
                        self.pos_y + 2 + EXPANDED_CELL * 2,
                        Direction.SOUTH,
                        self.obstacle_id,
                        SNAPSHOT_COST
                    ))

        # Facing south → robot faces north
        elif self.direction == Direction.SOUTH:
            if not retrying:
                # (x, y - 3), penalty 5
                if withinBounds(self.pos_x, self.pos_y - 1 - EXPANDED_CELL * 2):
                    cells.append(CellState(
                        self.pos_x,
                        self.pos_y - 1 - EXPANDED_CELL * 2,
                        Direction.NORTH,
                        self.obstacle_id,
                        5
                    ))

                # (x, y - 4), penalty 0
                if withinBounds(self.pos_x, self.pos_y - 2 - EXPANDED_CELL * 2):
                    cells.append(CellState(
                        self.pos_x,
                        self.pos_y - 2 - EXPANDED_CELL * 2,
                        Direction.NORTH,
                        self.obstacle_id,
                        0
                    ))

                # NEW: (x + 1, y - 3), penalty 100
                if withinBounds(self.pos_x + 1, self.pos_y - 1 - EXPANDED_CELL * 2):
                    cells.append(CellState(
                        self.pos_x + 1,
                        self.pos_y - 1 - EXPANDED_CELL * 2,
                        Direction.NORTH,
                        self.obstacle_id,
                        SNAPSHOT_COST * 2
                    ))

                # NEW: (x - 1, y - 3), penalty 100
                if withinBounds(self.pos_x - 1, self.pos_y - 1 - EXPANDED_CELL * 2):
                    cells.append(CellState(
                        self.pos_x - 1,
                        self.pos_y - 1 - EXPANDED_CELL * 2,
                        Direction.NORTH,
                        self.obstacle_id,
                        SNAPSHOT_COST * 2
                    ))

                # (x + 1, y - 4), penalty 50
                if withinBounds(self.pos_x + 1, self.pos_y - 2 - EXPANDED_CELL * 2):
                    cells.append(CellState(
                        self.pos_x + 1,
                        self.pos_y - 2 - EXPANDED_CELL * 2,
                        Direction.NORTH,
                        self.obstacle_id,
                        SNAPSHOT_COST
                    ))

                # (x - 1, y - 4), penalty 50
                if withinBounds(self.pos_x - 1, self.pos_y - 2 - EXPANDED_CELL * 2):
                    cells.append(CellState(
                        self.pos_x - 1,
                        self.pos_y - 2 - EXPANDED_CELL * 2,
                        Direction.NORTH,
                        self.obstacle_id,
                        SNAPSHOT_COST
                    ))

        # Facing east → robot faces west
        elif self.direction == Direction.EAST:
            if not retrying:
                # (x + 3, y), penalty 5
                if withinBounds(self.pos_x + 1 + EXPANDED_CELL * 2, self.pos_y):
                    cells.append(CellState(
                        self.pos_x + 1 + EXPANDED_CELL * 2,
                        self.pos_y,
                        Direction.WEST,
                        self.obstacle_id,
                        5
                    ))

                # (x + 4, y), penalty 0
                if withinBounds(self.pos_x + 2 + EXPANDED_CELL * 2, self.pos_y):
                    cells.append(CellState(
                        self.pos_x + 2 + EXPANDED_CELL * 2,
                        self.pos_y,
                        Direction.WEST,
                        self.obstacle_id,
                        0
                    ))

                # NEW: (x + 3, y + 1), penalty 100
                if withinBounds(self.pos_x + 1 + EXPANDED_CELL * 2, self.pos_y + 1):
                    cells.append(CellState(
                        self.pos_x + 1 + EXPANDED_CELL * 2,
                        self.pos_y + 1,
                        Direction.WEST,
                        self.obstacle_id,
                        SNAPSHOT_COST * 2
                    ))

                # NEW: (x + 3, y - 1), penalty 100
                if withinBounds(self.pos_x + 1 + EXPANDED_CELL * 2, self.pos_y - 1):
                    cells.append(CellState(
                        self.pos_x + 1 + EXPANDED_CELL * 2,
                        self.pos_y - 1,
                        Direction.WEST,
                        self.obstacle_id,
                        SNAPSHOT_COST * 2
                    ))

                # (x + 4, y + 1), penalty 50
                if withinBounds(self.pos_x + 2 + EXPANDED_CELL * 2, self.pos_y + 1):
                    cells.append(CellState(
                        self.pos_x + 2 + EXPANDED_CELL * 2,
                        self.pos_y + 1,
                        Direction.WEST,
                        self.obstacle_id,
                        SNAPSHOT_COST
                    ))

                # (x + 4, y - 1), penalty 50
                if withinBounds(self.pos_x + 2 + EXPANDED_CELL * 2, self.pos_y - 1):
                    cells.append(CellState(
                        self.pos_x + 2 + EXPANDED_CELL * 2,
                        self.pos_y - 1,
                        Direction.WEST,
                        self.obstacle_id,
                        SNAPSHOT_COST
                    ))

        # Facing west → robot faces east
        elif self.direction == Direction.WEST:
            if not retrying:
                # (x - 3, y), penalty 5
                if withinBounds(self.pos_x - 1 - EXPANDED_CELL * 2, self.pos_y):
                    cells.append(CellState(
                        self.pos_x - 1 - EXPANDED_CELL * 2,
                        self.pos_y,
                        Direction.EAST,
                        self.obstacle_id,
                        5
                    ))

                # (x - 4, y), penalty 0
                if withinBounds(self.pos_x - 2 - EXPANDED_CELL * 2, self.pos_y):
                    cells.append(CellState(
                        self.pos_x - 2 - EXPANDED_CELL * 2,
                        self.pos_y,
                        Direction.EAST,
                        self.obstacle_id,
                        0
                    ))

                # NEW: (x - 3, y + 1), penalty 100
                if withinBounds(self.pos_x - 1 - EXPANDED_CELL * 2, self.pos_y + 1):
                    cells.append(CellState(
                        self.pos_x - 1 - EXPANDED_CELL * 2,
                        self.pos_y + 1,
                        Direction.EAST,
                        self.obstacle_id,
                        SNAPSHOT_COST * 2
                    ))

                # NEW: (x - 3, y - 1), penalty 100
                if withinBounds(self.pos_x - 1 - EXPANDED_CELL * 2, self.pos_y - 1):
                    cells.append(CellState(
                        self.pos_x - 1 - EXPANDED_CELL * 2,
                        self.pos_y - 1,
                        Direction.EAST,
                        self.obstacle_id,
                        SNAPSHOT_COST * 2
                    ))

                # (x - 4, y + 1), penalty 50
                if withinBounds(self.pos_x - 2 - EXPANDED_CELL * 2, self.pos_y + 1):
                    cells.append(CellState(
                        self.pos_x - 2 - EXPANDED_CELL * 2,
                        self.pos_y + 1,
                        Direction.EAST,
                        self.obstacle_id,
                        SNAPSHOT_COST
                    ))

                # (x - 4, y - 1), penalty 50
                if withinBounds(self.pos_x - 2 - EXPANDED_CELL * 2, self.pos_y - 1):
                    cells.append(CellState(
                        self.pos_x - 2 - EXPANDED_CELL * 2,
                        self.pos_y - 1,
                        Direction.EAST,
                        self.obstacle_id,
                        SNAPSHOT_COST
                    ))

        return cells

    def getViewState4(self, retrying) -> List[CellState]:
        """Constructs list of 4 CellStates from which the robot can view the symbol on the obstacle"""
        cells = []

        # If obstacle is facing north, robot must face south
        if self.direction == Direction.NORTH:
            if not retrying:
                # (x, y + 5), penalty 0
                if withinBounds(self.pos_x, self.pos_y + 3 + EXPANDED_CELL * 2):
                    cells.append(CellState(
                        self.pos_x,
                        self.pos_y + 3 + EXPANDED_CELL * 2,
                        Direction.SOUTH,
                        self.obstacle_id,
                        0
                    ))

                # (x - 1, y + 4), penalty 50
                if withinBounds(self.pos_x - 1, self.pos_y + 2 + EXPANDED_CELL * 2):
                    cells.append(CellState(
                        self.pos_x - 1,
                        self.pos_y + 2 + EXPANDED_CELL * 2,
                        Direction.SOUTH,
                        self.obstacle_id,
                        SNAPSHOT_COST
                    ))

                # (x, y + 4), penalty 0
                if withinBounds(self.pos_x, self.pos_y + 2 + EXPANDED_CELL * 2):
                    cells.append(CellState(
                        self.pos_x,
                        self.pos_y + 2 + EXPANDED_CELL * 2,
                        Direction.SOUTH,
                        self.obstacle_id,
                        0
                    ))

                # (x + 1, y + 4), penalty 50
                if withinBounds(self.pos_x + 1, self.pos_y + 2 + EXPANDED_CELL * 2):
                    cells.append(CellState(
                        self.pos_x + 1,
                        self.pos_y + 2 + EXPANDED_CELL * 2,
                        Direction.SOUTH,
                        self.obstacle_id,
                        SNAPSHOT_COST
                    ))

        # Facing south → robot faces north
        elif self.direction == Direction.SOUTH:
            if not retrying:
                # (x, y - 5), penalty 0
                if withinBounds(self.pos_x, self.pos_y - 3 - EXPANDED_CELL * 2):
                    cells.append(CellState(
                        self.pos_x,
                        self.pos_y - 3 - EXPANDED_CELL * 2,
                        Direction.NORTH,
                        self.obstacle_id,
                        0
                    ))

                # (x - 1, y - 4), penalty 50
                if withinBounds(self.pos_x - 1, self.pos_y - 2 - EXPANDED_CELL * 2):
                    cells.append(CellState(
                        self.pos_x - 1,
                        self.pos_y - 2 - EXPANDED_CELL * 2,
                        Direction.NORTH,
                        self.obstacle_id,
                        SNAPSHOT_COST
                    ))

                # (x, y - 4), penalty 0
                if withinBounds(self.pos_x, self.pos_y - 2 - EXPANDED_CELL * 2):
                    cells.append(CellState(
                        self.pos_x,
                        self.pos_y - 2 - EXPANDED_CELL * 2,
                        Direction.NORTH,
                        self.obstacle_id,
                        0
                    ))

                # (x + 1, y - 4), penalty 50
                if withinBounds(self.pos_x + 1, self.pos_y - 2 - EXPANDED_CELL * 2):
                    cells.append(CellState(
                        self.pos_x + 1,
                        self.pos_y - 2 - EXPANDED_CELL * 2,
                        Direction.NORTH,
                        self.obstacle_id,
                        SNAPSHOT_COST
                    ))

        # Facing east → robot faces west
        elif self.direction == Direction.EAST:
            if not retrying:
                # (x + 5, y), penalty 0
                if withinBounds(self.pos_x + 3 + EXPANDED_CELL * 2, self.pos_y):
                    cells.append(CellState(
                        self.pos_x + 3 + EXPANDED_CELL * 2,
                        self.pos_y,
                        Direction.WEST,
                        self.obstacle_id,
                        0
                    ))

                # (x + 4, y - 1), penalty 50
                if withinBounds(self.pos_x + 2 + EXPANDED_CELL * 2, self.pos_y - 1):
                    cells.append(CellState(
                        self.pos_x + 2 + EXPANDED_CELL * 2,
                        self.pos_y - 1,
                        Direction.WEST,
                        self.obstacle_id,
                        SNAPSHOT_COST
                    ))

                # (x + 4, y), penalty 0
                if withinBounds(self.pos_x + 2 + EXPANDED_CELL * 2, self.pos_y):
                    cells.append(CellState(
                        self.pos_x + 2 + EXPANDED_CELL * 2,
                        self.pos_y,
                        Direction.WEST,
                        self.obstacle_id,
                        0
                    ))

                # (x + 4, y + 1), penalty 50
                if withinBounds(self.pos_x + 2 + EXPANDED_CELL * 2, self.pos_y + 1):
                    cells.append(CellState(
                        self.pos_x + 2 + EXPANDED_CELL * 2,
                        self.pos_y + 1,
                        Direction.WEST,
                        self.obstacle_id,
                        SNAPSHOT_COST
                    ))

        # Facing west → robot faces east
        elif self.direction == Direction.WEST:
            if not retrying:
                # (x - 5, y), penalty 0
                if withinBounds(self.pos_x - 3 - EXPANDED_CELL * 2, self.pos_y):
                    cells.append(CellState(
                        self.pos_x - 3 - EXPANDED_CELL * 2,
                        self.pos_y,
                        Direction.EAST,
                        self.obstacle_id,
                        0
                    ))

                # (x - 4, y - 1), penalty 50
                if withinBounds(self.pos_x - 2 - EXPANDED_CELL * 2, self.pos_y - 1):
                    cells.append(CellState(
                        self.pos_x - 2 - EXPANDED_CELL * 2,
                        self.pos_y - 1,
                        Direction.EAST,
                        self.obstacle_id,
                        SNAPSHOT_COST
                    ))

                # (x - 4, y), penalty 0
                if withinBounds(self.pos_x - 2 - EXPANDED_CELL * 2, self.pos_y):
                    cells.append(CellState(
                        self.pos_x - 2 - EXPANDED_CELL * 2,
                        self.pos_y,
                        Direction.EAST,
                        self.obstacle_id,
                        0
                    ))

                # (x - 4, y + 1), penalty 50
                if withinBounds(self.pos_x - 2 - EXPANDED_CELL * 2, self.pos_y + 1):
                    cells.append(CellState(
                        self.pos_x - 2 - EXPANDED_CELL * 2,
                        self.pos_y + 1,
                        Direction.EAST,
                        self.obstacle_id,
                        SNAPSHOT_COST
                    ))
        return cells

class Grid:
    """
    Grid object that contains the size of the grid and a list of obstacles
    """
    def __init__(self, size_x: int, size_y: int):
        """
        Args:
            size_x (int): Size of the grid in the x direction
            size_y (int): Size of the grid in the y direction
        """
        self.size_x = size_x
        self.size_y = size_y
        self.obstacles: List[Obstacle] = []
        self._reachable_cache = None

    def addObstacle(self, obstacle: Obstacle):
        """Add a new obstacle to the Grid object, ignores if duplicate obstacle

        Args:
            obstacle (Obstacle): Obstacle to be added
        """
        # Loop through the existing obstacles to check for duplicates
        to_add = True
        for ob in self.obstacles:
            if ob == obstacle:
                to_add = False
                break

        if to_add:
            self.obstacles.append(obstacle)
            self._reachable_cache = None

    def reset_obstacles(self):
        """
        Resets the obstacles in the grid
        """
        self.obstacles = []
        self._reachable_cache = None

    def get_obstacles(self):
        """
        Returns the list of obstacles in the grid
        """
        return self.obstacles

    def _reachable_uncached(self, x: int, y: int, turn=False, preTurn=False) -> bool:
        if not self.is_valid_coord(x, y):
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

    def is_valid_coord(self, x: int, y: int) -> bool:
        """Checks if given position is within bounds"""
        if x < 1 or x >= self.size_x - 1 or y < 1 or y >= self.size_y - 1:
            return False
        return True

    def is_valid_cell_state(self, state: CellState) -> bool:
        """Checks if given state is within bounds

        Args:
            state (CellState)

        Returns:
            bool: True if valid, False otherwise
        """
        return self.is_valid_coord(state.x, state.y)

    def get_view_obstacle_positions(self, retrying) -> List[List[CellState]]:
            optimal_positions = []
    
            # Process obstacles in ascending obstacle ID order
            for obstacle in sorted(self.obstacles, key=lambda ob: ob.obstacle_id):
                if obstacle.direction == 8:
                    continue
    
                if NUM_VIEWPOINTS == 4:
                    view_states = [
                        vs for vs in obstacle.getViewState4(retrying)
                        if self.reachable(vs.x, vs.y)
                    ]
                    optimal_positions.append(view_states)
    
                elif NUM_VIEWPOINTS == 6:
                    view_states = [
                        vs for vs in obstacle.getViewState6(retrying)
                        if self.reachable(vs.x, vs.y)
                    ]
                    optimal_positions.append(view_states)
    
            return optimal_positions