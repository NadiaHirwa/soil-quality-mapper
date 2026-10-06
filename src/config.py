"""Project-wide constants.

Every fixed number used by the project lives here, so it is easy to find,
explain and change in one place.
"""

# Size of the simulated field, in metres (x = east-west, y = north-south).
FIELD_WIDTH_M = 500.0
FIELD_HEIGHT_M = 400.0

# The field is split into a grid of cells; we take one sample per cell.
# 10 x 10 cells -> each cell is 50 m wide and 40 m tall -> 100 samples.
GRID_COLS = 10
GRID_ROWS = 10

# Seed for the random number generator, so results are reproducible.
RANDOM_SEED = 42
