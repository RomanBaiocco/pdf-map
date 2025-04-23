from osmium import osm
from shapely.geometry import Polygon, LinearRing, MultiPolygon
from typing import List, Tuple, Dict, Any
from src.logger import logger


def transform_relation_to_rings_and_holes(
    relation: osm.Relation, way_coords: Dict[int, List[Tuple[float, float]]]
) -> List[Tuple[List[Tuple[float, float]], List[List[Tuple[float, float]]]]]:
    outer_rings: List[List[Tuple[float, float]]] = []
    inner_rings: List[List[Tuple[float, float]]] = []
    output: List[Tuple[List[Tuple[float, float]], List[List[Tuple[float, float]]]]] = []

    # Process members
    for member in relation.members:
        if member.type == "w" and member.ref in way_coords:
            coords = way_coords[member.ref]
            if member.role == "outer":
                outer_rings.append(coords)
            elif member.role == "inner":
                inner_rings.append(coords)

    if outer_rings:

        # First, try to connect outer ring segments that share endpoints
        connected_rings = []

        while outer_rings:
            current = outer_rings[0]
            outer_rings.pop(0)
            modified = True

            while modified:
                modified = False
                i = 0
                while i < len(outer_rings):
                    other = outer_rings[i]
                    if current[-1] == other[0]:
                        current.extend(other[1:])
                        outer_rings.pop(i)
                        modified = True
                    elif current[-1] == other[-1]:
                        current.extend(other[-2::-1])
                        outer_rings.pop(i)
                        modified = True
                    elif current[0] == other[-1]:
                        current = other + current[1:]
                        outer_rings.pop(i)
                        modified = True
                    elif current[0] == other[0]:
                        current = other[::-1] + current[1:]
                        outer_rings.pop(i)
                        modified = True
                    else:
                        i += 1

            # Close the ring if needed
            if current[0] != current[-1]:
                current.append(current[0])
            connected_rings.append(current)

        # Create polygons from the connected rings
        for ring in connected_rings:
            if (
                len(ring) >= 4
            ):  # Need at least 4 points for a valid polygon (3 unique + closing point)
                # Process inner rings
                holes: List[List[Tuple[float, float]]] = []
                for inner in inner_rings:
                    if len(inner) >= 3:
                        # Close the inner ring if needed
                        if inner[0] != inner[-1]:
                            inner = inner + [inner[0]]
                        try:
                            inner_ring = LinearRing(inner)
                            outer_ring = LinearRing(ring)
                            inner_poly = Polygon(inner_ring)
                            outer_poly = Polygon(outer_ring)
                            if outer_poly.contains(inner_poly):
                                holes.append(inner)
                        except Exception as e:
                            logger.warning(f"Failed to process inner ring: {e}")

                output.append((ring, holes))

    return output
