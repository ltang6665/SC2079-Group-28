from enum import Enum


class Direction(int, Enum):
    NORTH = 0
    NORTHEAST = 1
    EAST = 2
    SOUTHEAST = 3
    SOUTH = 4
    SOUTHWEST = 5
    WEST = 6
    NORTHWEST = 7
    SKIP = 8

    def __int__(self):
        return self.value

    @staticmethod
    def rotation_cost(direction1, direction2):
        difference = abs(direction1 - direction2)
        return min(difference, 8 - difference)


MOVE_DIRECTIONS = [
    (0, 1, Direction.NORTH),
    (1, 1, Direction.NORTHEAST),
    (1, 0, Direction.EAST),
    (1, -1, Direction.SOUTHEAST),
    (0, -1, Direction.SOUTH),
    (-1, -1, Direction.SOUTHWEST),
    (-1, 0, Direction.WEST),
    (-1, 1, Direction.NORTHWEST),
]

# Motion tuning parameters
TURN_FACTOR = 5  # higher = fewer turns preferred; tune to physical robot behavior
TURN_RADIUS = 2  # nominal turning radius in grid cells
TURN_BIG = 3     # cost for large turn (> 45 degrees)
TURN_SMALL = 2   # cost for small turn (45 degrees, usually one step more than TURN_RADIUS)

# Safety and planning costs
SAFE_TURN_COST = 1000
SNAPSHOT_COST = 50

# Grid and arena sizing
EXPANDED_CELL = 1  # buffer ring width around arena for internal planning
# External arena coordinates are 0..ARENA_WIDTH-1 / 0..ARENA_HEIGHT-1.
# Internally, we pad the grid by PADDING cells on every side so the planner has
# a 1-cell "invisible" ring it can use near borders.
# PADDING = 1
# ARENA_WIDTH = 20
# ARENA_HEIGHT = 20
# GRID_WIDTH = ARENA_WIDTH + 2 * PADDING
# GRID_HEIGHT = ARENA_HEIGHT + 2 * PADDING
GRID_WIDTH = 20
GRID_HEIGHT = 20

MAX_ITERATIONS = 2000
