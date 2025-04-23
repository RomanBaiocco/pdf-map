from src.features.road_handler import RoadHandler
from src.features.coastline_handler import CoastlineHandler
from src.features.parks_handler import ParksHandler
from src.features.building_handler import BuildingHandler
from src.features.water_handler import WaterHandler

from osmium import osm, SimpleHandler
from typing import Set, Dict, List, Tuple
from shapely.geometry import Polygon, MultiPolygon
from src.transforms import transform_relation_to_rings_and_holes
from src.logger import logger


class OSMHandler(
    SimpleHandler,
    CoastlineHandler,
    RoadHandler,
    ParksHandler,
    BuildingHandler,
    WaterHandler,
):
    def __init__(self, boundary_relation_id: int | None = None):
        logger.info("Initializing OSMHandler")
        super().__init__()
        self.pass_num = 1  # Track which pass we're on
        self.needed_nodes: Set[int | str] = set()
        self.nodes: Dict[int, Tuple[float, float]] = (
            {}
        )  # Will only store needed nodes in second pass
        self.way_coords: Dict[int, List[Tuple[float, float]]] = (
            {}
        )  # Store way coordinates for relations

        self.boundary_relation_id: int | None = boundary_relation_id
        self.boundary_polygon: MultiPolygon | None = None

        if not hasattr(self, "progress"):
            self.progress = None

    def node(self, n):
        if self.progress:
            self.progress.update()

        if self.pass_num == 2 and n.id in self.needed_nodes:
            self.nodes[n.id] = (n.location.lon, n.location.lat)

    def way(self, w: osm.Way):
        if self.progress:
            self.progress.update()

        if len(w.nodes) > 0:
            # Store way coordinates for relations in second pass
            if self.pass_num == 2:
                coords = []
                for node in w.nodes:
                    if node.ref in self.nodes:
                        coords.append(self.nodes[node.ref])
                if coords:
                    self.way_coords[w.id] = coords

            if self.pass_num == 1:
                for node in w.nodes:
                    self.needed_nodes.add(node.ref)

            elif self.pass_num == 2:
                # Second pass: process ways as before
                coords = []
                for node in w.nodes:
                    if node.ref in self.nodes:
                        coords.append(self.nodes[node.ref])
                if coords:
                    if (
                        # If a way is identified as a feature the logic will short circuit and not check the rest
                        # This is generally sorted by the frequency of the feature in the data so that the performs the most likely checks first
                        self.process_way_building(w, coords)
                        or self.process_way_road(w, coords)
                        or self.process_way_water(w, coords)
                        or self.process_way_park(w, coords)
                        or self.process_way_coastline(w, coords)
                    ):
                        pass

    def relation(self, r: osm.Relation):
        # Update progress if needed
        if self.progress:
            self.progress.update()

        # In first pass, collect nodes for water and park relations
        if self.pass_num == 1:
            is_needed = False

            # First check for type=multipolygon
            for tag in r.tags:
                if tag.k == "type" and tag.v == "multipolygon":
                    is_needed = True
                    break

            # Then check other tags if not already needed
            if not is_needed:
                for tag in r.tags:
                    if self.relation_tag_is_water(tag):
                        is_needed = True
                    elif self.relation_tag_is_park(tag):
                        is_needed = True
                    elif self.relation_tag_is_building(tag):
                        is_needed = True

            if is_needed:
                # Collect all member way IDs
                for member in r.members:
                    if member.type == "w":
                        # Store the way ID and collect all its nodes
                        way_id = f"relation_{r.id}_{member.ref}"
                        self.needed_nodes.add(way_id)
                        # Also add the way itself to needed nodes
                        self.needed_nodes.add(member.ref)

        # In second pass, process water, park, and building relations
        elif self.pass_num == 2:
            if r.id == self.boundary_relation_id:
                self.store_boundary_polygon(r, self.way_coords)

            if (
                self.process_relation_building(r, self.way_coords)
                or self.process_relation_water(r, self.way_coords)
                or self.process_relation_park(r, self.way_coords)
                or self.process_relation_pedestrian(r, self.way_coords)
            ):
                pass

    def store_boundary_polygon(
        self, relation: osm.Relation, way_coords: Dict[int, List[Tuple[float, float]]]
    ):
        logger.info(f"Boundary relation found: {relation.id}")
        boundary_rings_and_holes = transform_relation_to_rings_and_holes(
            relation, way_coords
        )

        self.boundary_polygon = MultiPolygon(
            [Polygon(ring, holes) for ring, holes in boundary_rings_and_holes]
        )

    def get_boundary_polygon(self) -> MultiPolygon | None:
        if self.pass_num < 2:
            raise ValueError("Boundary polygon not available until after second pass")

        if not self.boundary_relation_id:
            return None

        if not self.boundary_polygon:
            raise ValueError("Boundary polygon not found in dataset")

        return self.boundary_polygon
