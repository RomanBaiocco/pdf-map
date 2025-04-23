import uuid
from tqdm import tqdm
from reportlab.lib.colors import Color
from src.logger import logger
from typing import List, TypedDict, Dict, Optional, Literal, Tuple
from src.project_types import Coord, Line
from src.map_dimensions import Side, MapDimensions

WATER_COLOR = Color(0.529, 0.808, 0.922)
LAND_COLOR = Color(0.95, 0.95, 0.95)


class Coastline(TypedDict):
    id: int
    coords: List[Coord]
    refs: List[int]


class CoastlineSection(TypedDict):
    """
    A section of coastline that can be joined with other sections to form a continuous coastline
    """

    id: int
    coords: List[Coord]
    start: int
    end: int
    used: bool


# For traversing the map boundary clockwise
NEXT_SIDE_MAP = {
    Side.TOP: Side.RIGHT,
    Side.RIGHT: Side.BOTTOM,
    Side.BOTTOM: Side.LEFT,
    Side.LEFT: Side.TOP,
}


class Intersection(TypedDict):
    point: Coord
    is_entering: bool
    side: Side


class IntersectionWithId(Intersection):
    bounded_coastline_id: str


IntersectionMap = Dict[Side, List[IntersectionWithId]]

EMPTY_INTERSECTION_MAP: IntersectionMap = {
    Side.TOP: [],
    Side.RIGHT: [],
    Side.BOTTOM: [],
    Side.LEFT: [],
}


def generate_bounded_coastline_id() -> str:
    """Generate a unique ID for a bounded coastline"""
    return str(uuid.uuid4())


class CoastlineHandler:
    def __init__(self):
        super().__init__()
        if not hasattr(self, "coastline"):
            self.coastlines: List[Coastline] = []

    def test_way_for_coastline(self, way):
        for tag in way.tags:
            if tag.k == "natural" and tag.v == "coastline":
                return True
        return False

    def process_way_coastline(self, way, coords):
        for tag in way.tags:
            if tag.k == "natural" and tag.v == "coastline":
                self.add_coastline(way, coords)
                return True
        return False

    def add_coastline(self, way, coords):
        self.coastlines.append(
            {
                "id": way.id,
                "coords": coords,
                "refs": [n.ref for n in way.nodes],
            }
        )

    def render_coastline_and_background_water(
        self,
        c,
        map_dimensions: MapDimensions,
    ):
        """Render coastline and background water"""

        c.setFillColor(WATER_COLOR)
        c.rect(
            0,
            0,
            map_dimensions.width_points,
            map_dimensions.height_points,
            fill=1,
            stroke=0,
        )

        if len(self.coastlines) == 0:
            logger.warning(
                "No coastlines found to visualize. Assuming entire boundary is land."
            )
            c.setFillColor(LAND_COLOR)
            c.rect(
                0,
                0,
                map_dimensions.width_points,
                map_dimensions.height_points,
                fill=1,
                stroke=0,
            )
            return

        closed_coastlines, open_coastlines, intersection_map = (
            self.bound_and_sort_complete_coastlines(map_dimensions)
        )

        starting_point = self.find_intersection_map_starting_point(intersection_map)
        joined_open_coastlines: List[Line] = []
        if starting_point:
            joined_open_coastlines = self.join_open_coastlines(
                open_coastlines, intersection_map, starting_point, map_dimensions
            )

        all_coastlines = closed_coastlines + joined_open_coastlines

        logger.info(f"Total land masses to draw: {len(all_coastlines)}")

        for coastline in tqdm(all_coastlines, desc="Drawing coastline chains"):
            if len(coastline) < 2:
                continue

            path = c.beginPath()

            # Get first point
            first_lon, first_lat = coastline[0]
            first_x, first_y = map_dimensions.transform_coords(first_lon, first_lat)
            path.moveTo(first_x, first_y)

            # Add all remaining points
            for lon, lat in coastline[1:]:
                x, y = map_dimensions.transform_coords(lon, lat)
                path.lineTo(x, y)

            # Check if the chain is closed
            is_closed = len(coastline) > 3 and coastline[0] == coastline[-1]

            # If the chain is closed, fill it with land color
            if is_closed:
                path.close()
                c.setFillColor(LAND_COLOR)
                c.drawPath(path, fill=1, stroke=0)
            else:
                # Mark endpoints of open chains
                # Start point in blue
                c.setFillColorRGB(0.0, 0.0, 1.0)  # Blue
                c.setStrokeColorRGB(0.0, 0.0, 1.0)  # Blue outline
                c.circle(first_x, first_y, 5, fill=1, stroke=1)

                # End point in red
                last_lon, last_lat = coastline[-1]
                last_x, last_y = map_dimensions.transform_coords(last_lon, last_lat)
                c.setFillColorRGB(1.0, 0.0, 0.0)  # Red
                c.setStrokeColorRGB(1.0, 0.0, 0.0)  # Red outline
                c.circle(last_x, last_y, 5, fill=1, stroke=1)

                # Reset colors for next segment
                c.setStrokeColorRGB(0.3, 0.3, 0.3)  # Dark gray outline

    def is_inside_map(self, point: Coord, map_dimensions: MapDimensions) -> bool:
        """Check if a point is inside the map boundaries"""
        lon, lat = point
        return (
            map_dimensions.min_lon <= lon <= map_dimensions.max_lon
            and map_dimensions.min_lat <= lat <= map_dimensions.max_lat
        )

    def convert_coastline_ways_into_continuous_lines(self) -> List[Line]:
        """
        Convert sectioned coastline ways into continuous coastlines by connecting them

        Returns:
            Dict of one of the coastline way ids to the continuous coastline containing it
        """
        sections: Dict[int, CoastlineSection] = {}
        for coast in self.coastlines:
            sections[coast["id"]] = {
                "id": coast["id"],
                "coords": coast["coords"],
                "start": coast["refs"][0],
                "end": coast["refs"][-1],
                "used": False,
            }

        # Start with the longest section as it's likely part of the main coastline
        longest_section = None
        longest_length = 0
        for section in sections.values():
            length = len(section["coords"])
            if length > longest_length:
                longest_length = length
                longest_section = section

        if not longest_section:
            return []

        # Create chains of sections
        chains: List[Line] = []
        current_chain = list(longest_section["coords"])
        sections[longest_section["id"]]["used"] = True

        # Keep track of the endpoints of the current chain
        chain_start = longest_section["start"]
        chain_end = longest_section["end"]

        # Try to extend the chain in both directions
        while True:
            extended = False

            for section_id, section in list(sections.items()):
                if section["used"]:
                    continue

                # Because all coastlines are ordered, we don't need to check start against start or end against end
                if section["start"] == chain_end:
                    # Connect to end of chain
                    current_chain.extend(section["coords"][1:])
                    chain_end = section["end"]
                    sections[section_id]["used"] = True
                    extended = True
                    break
                elif section["end"] == chain_start:
                    # Connect to start of chain
                    current_chain = section["coords"] + current_chain[1:]
                    chain_start = section["start"]
                    sections[section_id]["used"] = True
                    extended = True
                    break

            if not extended:
                if len(current_chain) >= 2:
                    chains.append(current_chain)

                # Look for unused sections to start a new chain
                new_start: Optional[CoastlineSection] = None
                for section in sections.values():
                    if not section["used"]:
                        new_start = section
                        break

                if new_start is None:
                    break

                current_chain = list(new_start["coords"])
                chain_start = new_start["start"]
                chain_end = new_start["end"]
                sections[new_start["id"]]["used"] = True

        logger.info(f"Created {len(chains)} coastline chains")
        return chains

    def find_segment_intersection_with_boundary(
        self,
        p1: Coord,
        p2: Coord,
        map_dimensions: MapDimensions,
    ) -> Intersection | Literal["inside"] | Literal["outside"]:
        """
        Find intersection of line segment (p1, p2) with map boundary.

        Args:
            p1: First point of the line segment
            p2: Second point of the line segment

        Returns:
            Intersection | Literal["inside"] (if the segment is entirely inside the map) | Literal["outside"] (if the segment is entirely outside the map)
        """
        lon1, lat1 = p1
        lon2, lat2 = p2

        # Check if both points are inside or outside - no intersection in these cases
        p1_inside = self.is_inside_map(p1, map_dimensions)
        p2_inside = self.is_inside_map(p2, map_dimensions)

        if p1_inside and p2_inside:
            return "inside"
        elif not p1_inside and not p2_inside:
            return "outside"

        # The line is p1 + t * (p2 - p1) where t is in [0, 1]
        # Find t for each boundary
        intersections: List[Intersection] = []

        # Top boundary (lat = max_lat)
        if lat1 != lat2:  # Avoid division by zero
            t = (map_dimensions.max_lat - lat1) / (lat2 - lat1)
            if 0 <= t <= 1:
                lon_intersect = lon1 + t * (lon2 - lon1)
                if map_dimensions.min_lon <= lon_intersect <= map_dimensions.max_lon:
                    intersections.append(
                        {
                            "point": (lon_intersect, map_dimensions.max_lat),
                            "is_entering": lat1 > lat2,  # Entering if moving down
                            "side": Side.TOP,
                        }
                    )

        # Right boundary (lon = max_lon)
        if lon1 != lon2:
            t = (map_dimensions.max_lon - lon1) / (lon2 - lon1)
            if 0 <= t <= 1:
                lat_intersect = lat1 + t * (lat2 - lat1)
                if map_dimensions.min_lat <= lat_intersect <= map_dimensions.max_lat:
                    intersections.append(
                        {
                            "point": (map_dimensions.max_lon, lat_intersect),
                            "is_entering": lon1 > lon2,  # Entering if moving left
                            "side": Side.RIGHT,
                        }
                    )

        # Bottom boundary (lat = min_lat)
        if lat1 != lat2:
            t = (map_dimensions.min_lat - lat1) / (lat2 - lat1)
            if 0 <= t <= 1:
                lon_intersect = lon1 + t * (lon2 - lon1)
                if map_dimensions.min_lon <= lon_intersect <= map_dimensions.max_lon:
                    intersections.append(
                        {
                            "point": (lon_intersect, map_dimensions.min_lat),
                            "is_entering": lat1 < lat2,  # Entering if moving up
                            "side": Side.BOTTOM,
                        }
                    )

        # Left boundary (lon = min_lon)
        if lon1 != lon2:
            t = (map_dimensions.min_lon - lon1) / (lon2 - lon1)
            if 0 <= t <= 1:
                lat_intersect = lat1 + t * (lat2 - lat1)
                if map_dimensions.min_lat <= lat_intersect <= map_dimensions.max_lat:
                    intersections.append(
                        {
                            "point": (map_dimensions.min_lon, lat_intersect),
                            "is_entering": lon1 < lon2,  # Entering if moving right
                            "side": Side.LEFT,
                        }
                    )

        # There should be exactly one intersection unless the line passes through a corner
        if len(intersections) >= 1:
            # If we have multiple intersections, take the one closer to p1
            if len(intersections) > 1:
                distances = []
                for intersection in intersections:
                    dx = intersection["point"][0] - lon1
                    dy = intersection["point"][1] - lat1
                    distances.append(dx * dx + dy * dy)
                return intersections[distances.index(min(distances))]
            return intersections[0]

        raise ValueError("No intersection found for line segment that crosses boundary")

    def bound_and_sort_complete_coastlines(
        self,
        map_dimensions: MapDimensions,
    ) -> Tuple[List[Line], Dict[str, Line], IntersectionMap]:
        """
        Bound and sort complete coastlines

        Returns:
            Tuple of (closed_coastlines, open_coastlines, intersection_map)
        """
        # These coastlines are closed and don't cross the boundary (and thus we don't need their IDs)
        closed_coastlines: List[Line] = []
        # These coastlines are open and cross the boundary
        open_coastlines: Dict[str, Line] = {}

        intersection_map: IntersectionMap = EMPTY_INTERSECTION_MAP.copy()

        complete_coastlines = self.convert_coastline_ways_into_continuous_lines()

        for complete_coastline in tqdm(
            complete_coastlines, desc="Processing coastlines"
        ):
            if len(complete_coastline) < 2:
                continue

            does_coastline_cross_boundary = False
            # Each of the bounded coastlines that are made from the complete coastline (the str is the bounded coastline id)
            bounded_coastlines_from_complete_coastline: List[Tuple[str, Line]] = []
            # Temporary list to build up coordinates for a single bounded coastline
            bounded_coastline_accumulator: Line = []
            # Unique ID for the current bounded coastline being accumulated
            current_bounded_coastline_id = generate_bounded_coastline_id()

            for [p1, p2] in zip(complete_coastline, complete_coastline[1:]):
                intersection = self.find_segment_intersection_with_boundary(
                    p1, p2, map_dimensions
                )

                if intersection == "inside":
                    if not bounded_coastline_accumulator:
                        # If we're starting a new coastline, add the first point
                        bounded_coastline_accumulator.append(p1)
                    bounded_coastline_accumulator.append(p2)

                elif intersection == "outside":
                    if bounded_coastline_accumulator:
                        raise ValueError(
                            f"Coastline accumulator is not empty but we're outside the map"
                        )
                else:
                    # The coastline has crossed the map boundary
                    does_coastline_cross_boundary = True

                    intersection_map[intersection["side"]].append(
                        {
                            "point": intersection["point"],
                            "is_entering": intersection["is_entering"],
                            "side": intersection["side"],
                            "bounded_coastline_id": current_bounded_coastline_id,
                        }
                    )

                    if intersection["is_entering"]:
                        # Start a new bounded coastline
                        bounded_coastline_accumulator = [intersection["point"], p2]
                    else:  # coastline is exiting the map
                        if not bounded_coastline_accumulator:
                            # If we're starting a new coastline, add the first point
                            bounded_coastline_accumulator.append(p1)
                        bounded_coastline_accumulator.append(intersection["point"])

                        # Store the bounded coastline
                        bounded_coastlines_from_complete_coastline.append(
                            (
                                current_bounded_coastline_id,
                                bounded_coastline_accumulator,
                            )
                        )
                        # Generate a new ID for the next bounded coastline
                        current_bounded_coastline_id = generate_bounded_coastline_id()
                        # Clear the accumulator for the next coastline
                        bounded_coastline_accumulator = []

            # After processing all pairs, save any remaining part of the current bounded coastline
            if bounded_coastline_accumulator:
                if not does_coastline_cross_boundary:
                    if bounded_coastlines_from_complete_coastline:
                        raise ValueError(
                            "Coastline did not cross boundary yet we have a bounded coastline"
                        )

                    # This means it's a closed coastline as it never crossed the boundary
                    closed_coastlines.append(bounded_coastline_accumulator.copy())

                # Check if the chain formed a loop by crossing boundaries and re-entering
                # If the last point of the last bounded coastline is the first point of the first bounded coastline, merge them.
                elif bounded_coastline_accumulator[-1] == complete_coastline[0]:
                    # Prepend the last bounded coastline's points to the first bounded coastline
                    first_bounded_coastline_id = (
                        bounded_coastlines_from_complete_coastline[0][0]
                    )
                    first_bounded_coastline_coords = (
                        bounded_coastlines_from_complete_coastline[0][1].copy()
                    )
                    bounded_coastlines_from_complete_coastline[0] = (
                        first_bounded_coastline_id,
                        bounded_coastline_accumulator
                        + first_bounded_coastline_coords[1:],
                    )  # Avoid duplicating the connection point

                    # Update the bounded coastline id in all intersections that reference the current_bounded_coastline_id
                    for side in Side:
                        for intersection in intersection_map[side]:
                            if (
                                intersection["bounded_coastline_id"]
                                == current_bounded_coastline_id
                            ):
                                intersection["bounded_coastline_id"] = (
                                    first_bounded_coastline_id
                                )

                else:
                    # Otherwise, just add the last bounded coastline as is
                    bounded_coastlines_from_complete_coastline.append(
                        (
                            current_bounded_coastline_id,
                            bounded_coastline_accumulator.copy(),
                        )
                    )

            for (
                bounded_coastline_id,
                bounded_coastline,
            ) in bounded_coastlines_from_complete_coastline:
                open_coastlines[bounded_coastline_id] = bounded_coastline

        # Sort intersections along each side of the boundary
        intersection_map[Side.TOP].sort(key=lambda x: x["point"][0])
        intersection_map[Side.RIGHT].sort(key=lambda x: x["point"][1], reverse=True)
        intersection_map[Side.BOTTOM].sort(key=lambda x: x["point"][0], reverse=True)
        intersection_map[Side.LEFT].sort(key=lambda x: x["point"][1])

        self.validate_intersection_map(intersection_map)

        return closed_coastlines, open_coastlines, intersection_map

    def validate_intersection_map(self, intersection_map: IntersectionMap) -> bool:
        """
        Validates that the intersection map has the same number of entering and exiting intersections.

        Args:
            intersection_map: Map of intersections for each side of the boundary

        Returns:
            True if the map is valid

        Raises:
            ValueError: If there's not an equal number of entering and exiting intersections
        """
        entering_count = 0
        exiting_count = 0

        for side in Side:
            for intersection in intersection_map[side]:
                if intersection["is_entering"]:
                    entering_count += 1
                else:
                    exiting_count += 1

        if entering_count != exiting_count:
            raise ValueError(
                "Invalid intersection map, not an equal number of entering and exiting intersections. This most likely means that you have an incomplete coastline in your OSM file that is visible in the current map boundaries."
            )

        return True

    def find_intersection_map_starting_point(
        self,
        intersection_map: IntersectionMap,
    ) -> Optional[Tuple[Side, int]]:
        """
        Finds the first entering intersection in the map to use as a starting point.

        Args:
            intersection_map: Map of intersections for each side of the boundary

        Returns:
            Tuple of (side, intersection_index) or None if no entering intersection is found
        """
        for side in Side:
            for intersection_index, intersection in enumerate(intersection_map[side]):
                if intersection["is_entering"]:
                    return (side, intersection_index)
        return None

    def join_open_coastlines(
        self,
        open_coastlines: Dict[str, Line],
        intersection_map: IntersectionMap,
        starting_point: Tuple[Side, int],
        map_dimensions: MapDimensions,
    ) -> List[Line]:
        """
        Joins open coastlines into closed coastlines by rotating around the boundary in a clockwise direction.

        Args:
            open_coastlines: Dictionary of open coastlines
            intersection_map: Map of intersections for each side of the boundary
            starting_point: Tuple of (side, intersection_index) to start from

        Returns:
            List of closed coastlines
        """

        looking_for: Literal["exit", "enter"] = "exit"
        current_side: Side = starting_point[0]
        current_index: int = starting_point[1]

        starting_coastline_id = intersection_map[current_side][current_index][
            "bounded_coastline_id"
        ]

        current_open_coastline_accumulator: Line = open_coastlines[
            starting_coastline_id
        ]

        # We start with this initialized as we being looking for the exit of the starting coastline
        exit_id_to_look_for: Optional[str] = starting_coastline_id
        entrace_id_to_look_for: Optional[str] = None

        new_closed_coastlines: List[Line] = []

        # These are to handle a special case where 3+ coastlines are nested within eachother (the land would need to look like the rist peninsula)
        skipped_intersections: List[IntersectionMap] = []
        current_skipped_intersection_map: IntersectionMap = (
            EMPTY_INTERSECTION_MAP.copy()
        )
        current_skipped_intersection_map_is_used: bool = False

        current_index += 1
        # Base case: we've looped around the entire boundary and are back to the starting point
        while current_side != starting_point[0] or current_index != starting_point[1]:

            # We have reached the end of the current side
            if current_index >= len(intersection_map[current_side]):
                if looking_for == "exit" and entrace_id_to_look_for is None:
                    # We add the corner to the start of the coastline to prevent the line from cutting through the corner
                    current_open_coastline_accumulator.insert(
                        0, map_dimensions.side_clockwise_corners[current_side]
                    )
                current_index = 0
                current_side = NEXT_SIDE_MAP[current_side]
                continue

            current_intersection = intersection_map[current_side][current_index]
            current_intersection_coastline_id = current_intersection[
                "bounded_coastline_id"
            ]
            current_intersection_coastline = open_coastlines.get(
                current_intersection_coastline_id
            )

            if current_intersection_coastline is None:
                raise ValueError(
                    f"Invalid intersection map, no coastline found for intersection {current_intersection}"
                )

            if looking_for == "exit":
                if current_intersection["is_entering"]:
                    raise ValueError(
                        "Invalid intersection map, found entering intersection when looking for exit"
                    )

                if exit_id_to_look_for is None:
                    raise ValueError(
                        "Invalid intersection map, no exit id to look for when looking for exit"
                    )

                # We have found the exit of the original coastline, which means we can close this polygon
                if current_intersection_coastline_id == exit_id_to_look_for:
                    current_open_coastline_accumulator.insert(
                        0, current_intersection_coastline[-1]
                    )
                    new_closed_coastlines.append(current_open_coastline_accumulator)
                    exit_id_to_look_for = None
                    current_open_coastline_accumulator = []
                    looking_for = "enter"
                    current_index += 1
                    continue
                else:
                    if entrace_id_to_look_for is None:
                        entrace_id_to_look_for = current_intersection_coastline_id
                        current_open_coastline_accumulator = (
                            current_intersection_coastline
                            + current_open_coastline_accumulator
                        )
                        looking_for = "enter"
                        current_index += 1
                        continue
                    else:
                        raise ValueError(
                            "Invalid intersection map, while looking for exit we found an intersection that is not the exit of the original coastline when we shouldn't have"
                        )

            elif looking_for == "enter":
                if not current_intersection["is_entering"]:
                    raise ValueError(
                        "Invalid intersection map, found exiting intersection when looking for enter"
                    )

                if exit_id_to_look_for is None:
                    exit_id_to_look_for = current_intersection_coastline_id
                    current_open_coastline_accumulator = current_intersection_coastline
                    current_index += 1
                    looking_for = "exit"
                    continue

                if current_intersection_coastline_id == entrace_id_to_look_for:
                    entrace_id_to_look_for = None
                    if current_skipped_intersection_map_is_used:
                        skipped_intersections.append(current_skipped_intersection_map)
                        current_skipped_intersection_map = EMPTY_INTERSECTION_MAP.copy()
                    looking_for = "exit"
                    current_index += 1
                    continue
                else:
                    current_skipped_intersection_map[current_side].append(
                        current_intersection
                    )
                    current_skipped_intersection_map_is_used = True
                    current_index += 1
                    continue

        # Process any skipped intersections recursively
        for skipped_intersection_map in skipped_intersections:
            skipped_starting_point = self.find_intersection_map_starting_point(
                skipped_intersection_map
            )
            if skipped_starting_point:
                skipped_new_closed_coastlines = self.join_open_coastlines(
                    open_coastlines,
                    skipped_intersection_map,
                    skipped_starting_point,
                    map_dimensions,
                )
                new_closed_coastlines.extend(skipped_new_closed_coastlines)

        return new_closed_coastlines
