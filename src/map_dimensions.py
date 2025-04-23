import math
from enum import Enum, auto
from typing import Tuple
from src.scale import (
    METERS_PER_DEGREE_LAT,
    POINTS_PER_METER,
    EARTH_RADIUS,
)
from src.logger import logger


class Side(Enum):
    """Enum representing the sides of the map boundary"""

    TOP = auto()
    RIGHT = auto()
    BOTTOM = auto()
    LEFT = auto()


class MapDimensions:
    def __init__(
        self,
        bottom_left_coord: Tuple[float, float],
        top_right_coord: Tuple[float, float],
    ):
        logger.info("Calculating map dimensions...")

        self.min_lat: float = bottom_left_coord[0]
        self.min_lon: float = bottom_left_coord[1]
        self.max_lat: float = top_right_coord[0]
        self.max_lon: float = top_right_coord[1]

        self.meters_per_degree_lon_at_avg_lat: float = self.meters_per_degree_lon(
            (self.min_lat + self.max_lat) / 2
        )

        self.width_meters: float = (
            self.max_lon - self.min_lon
        ) * self.meters_per_degree_lon_at_avg_lat
        self.height_meters: float = (
            self.max_lat - self.min_lat
        ) * METERS_PER_DEGREE_LAT

        self.width_points: float = self.width_meters * POINTS_PER_METER
        self.height_points: float = self.height_meters * POINTS_PER_METER

        self.side_clockwise_corners = {
            Side.TOP: (self.max_lon, self.max_lat),  # top right
            Side.RIGHT: (self.max_lon, self.min_lat),  # bottom right
            Side.BOTTOM: (self.min_lon, self.min_lat),  # bottom left
            Side.LEFT: (self.min_lon, self.max_lat),  # top left
        }

        logger.info(
            f"Map dimensions: {self.width_meters:.2f}m x {self.height_meters:.2f}m"
        )
        logger.info(
            f"PDF dimensions: {self.width_points:.2f}pt x {self.height_points:.2f}pt"
        )

    def transform_coords(self, lon, lat):
        # Convert lon/lat to meters from origin
        x_meters = (lon - self.min_lon) * self.meters_per_degree_lon_at_avg_lat
        y_meters = (lat - self.min_lat) * METERS_PER_DEGREE_LAT
        # Convert meters to points
        return (x_meters * POINTS_PER_METER, y_meters * POINTS_PER_METER)

    def meters_per_degree_lon(self, lat):
        """Calculate meters per degree of longitude at a given latitude"""
        return EARTH_RADIUS * math.cos(math.radians(lat)) * (math.pi / 180)
