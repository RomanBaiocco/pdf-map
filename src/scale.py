import math

# Constants for coordinate conversion
SCALE: float = 1
EARTH_RADIUS = 6371000  # Earth's radius in meters
METERS_PER_DEGREE_LAT = EARTH_RADIUS * (math.pi / 180)  # ~111km per degree

# Scale settings
INCHES_PER_METER = 39.3701 * SCALE  # Standard conversion adjusted for scale
POINTS_PER_INCH = 72.0  # Standard PostScript points per inch
POINTS_PER_METER = (
    POINTS_PER_INCH * INCHES_PER_METER
)  # Points per meter at current scale
TILE_SIZE_METERS = 100  # Process in tiles internally for memory management
