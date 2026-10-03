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
    def rotation_cost(d1, d2):
        diff = abs(d1 - d2)
        return min(diff, 8 - diff)

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

TURN_FACTOR = 13  # higher = fewer turns preferred; tune to taste

EXPANDED_CELL = 1 # for both agent and obstacles

# External arena coordinates are treated as 0..ARENA_WIDTH-1 / 0..ARENA_HEIGHT-1.
# Internally, we pad the grid by PADDING cells on every side so the planner can
# "go out of bounds" by up to that amount (e.g., for turning / clearance).
# PADDING = 1
# ARENA_WIDTH = 20
# ARENA_HEIGHT = 20
# WIDTH = ARENA_WIDTH + 2 * PADDING
# HEIGHT = ARENA_HEIGHT + 2 * PADDING
GRID_WIDTH = 20
GRID_HEIGHT = 20

MAX_ITERATIONS = 4000
TURN_RADIUS = 2
TURN_BIG   = 3   # primary displacement (tune against physical robot)
TURN_SMALL = 2   # secondary displacement (calibrated: reality is +1 over TURN_RADIUS)

SAFE_TURN_COST = 700 # the cost for the turn in case there is a chance that the robot is touch some obstacle
SNAPSHOT_COST = 50 # the cost for the place where the picture is taken
NUM_VIEWPOINTS = 4