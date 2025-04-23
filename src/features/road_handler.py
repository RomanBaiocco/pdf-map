from src.rendering import (
    FeatureLineData,
    FeatureRenderer,
    LineStyle,
    PolygonStyle,
    FeaturePolygonData,
)
from src.transforms import transform_relation_to_rings_and_holes

from osmium import osm
from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas
from shapely.geometry import Polygon, MultiPolygon
from typing import List, Tuple, Dict
from src.map_dimensions import MapDimensions

BASE_ROAD_WIDTHS = {
    1: 8.0,  # Motorways (typical 4 lanes + shoulders)
    2: 8.0,  # Trunk (typical 3-4 lanes)
    3: 8.0,  # Primary (typical 2-3 lanes)
    4: 8.0,  # Secondary (typical 2 lanes)
    5: 8.0,  # Tertiary (typical 2 lanes, narrower)
    6: 6.0,  # Residential (typical 1-2 lanes)
    7: 4.0,  # Service/Other (single lane)
    8: 1.5,  # Pedestrian/Footway (single lane)
}
ROAD_STYLES: Dict[int, LineStyle] = {
    hierarchy: {
        "stroke_width": width,
        "stroke_color": Color(
            0.3 + (hierarchy * 0.1),
            0.3 + (hierarchy * 0.1),
            0.3 + (hierarchy * 0.1),
        ),
        "round_cap": True,
    }
    for hierarchy, width in BASE_ROAD_WIDTHS.items()
}
DEFAULT_ROAD_STYLE_KEY = 7
DEFAULT_ROAD_STYLE = ROAD_STYLES[DEFAULT_ROAD_STYLE_KEY]

ROAD_TYPES_HIERARCHY = {
    "motorway": 1,
    "trunk": 2,
    "primary": 3,
    "secondary": 4,
    "tertiary": 5,
    "residential": 6,
    "service": 7,
    "unclassified": 7,
    "motorway_link": 2,
    "trunk_link": 3,
    "primary_link": 4,
    "secondary_link": 5,
    "tertiary_link": 6,
    "living_street": 7,
    "track": 7,
    "road": 7,
    "pedestrian": 8,
    "footway": 8,
    "steps": 8,
}

DISSALOWED_FOOTWAYS = ["sidewalk", "crossing"]

PEDESTRIAN_RELATION_STYLES: PolygonStyle = {"fill_color": Color(0.866, 0.866, 0.910)}


class RoadHandler:
    def __init__(self):
        super().__init__()
        if not hasattr(self, "roads"):
            self.roads: List[FeatureLineData] = []
            self.pedestrian_relations: List[FeaturePolygonData] = []

    def get_road_type_from_way(self, way):
        if way.tags.get("highway") in ROAD_TYPES_HIERARCHY:
            return way.tags.get("highway")
        elif way.tags.get("highway") == "construction":
            if way.tags.get("construction") in ROAD_TYPES_HIERARCHY:
                return way.tags.get("construction")
        return None

    def process_way_road(self, way: osm.Way, coords: List[Tuple[float, float]]) -> bool:
        """Process a way to possibly add it to the road list"""
        road_type = self.get_road_type_from_way(way)
        is_not_sidewalk = way.tags.get("footway") not in DISSALOWED_FOOTWAYS

        if road_type and is_not_sidewalk:
            self.roads.append(
                {
                    "type": road_type,
                    "coords": coords,
                    "way_id": way.id,
                    "hierarchy": ROAD_TYPES_HIERARCHY[road_type],
                }
            )
            return True

        return False

    def process_relation_pedestrian(
        self, relation: osm.Relation, way_coords: Dict[int, List[Tuple[float, float]]]
    ) -> bool:
        if relation.tags.get("highway") == "pedestrian":
            for ring, holes in transform_relation_to_rings_and_holes(
                relation, way_coords
            ):
                self.pedestrian_relations.append(
                    {
                        "type": "pedestrian_polygon",
                        "exterior": ring,
                        "interiors": holes,
                        "name": relation.tags.get("name"),
                        "relation_id": relation.id,
                    }
                )
            return True

        return False

    def render_roads(
        self,
        c: canvas.Canvas,
        map_dimensions: MapDimensions,
        boundary: Polygon | MultiPolygon | None,
    ):
        # Sort roads by hierarchy (draw less important roads first)
        sorted_roads = sorted(
            self.roads,
            key=lambda x: x.get("hierarchy", 999) if isinstance(x, dict) else 999,
            reverse=True,
        )

        renderer = FeatureRenderer(c, map_dimensions, boundary)
        renderer.render_line_features(
            features=sorted_roads,
            style=lambda x: ROAD_STYLES[x.get("hierarchy", DEFAULT_ROAD_STYLE_KEY)],
            desc="Rendering roads",
        )

        renderer.render_polygon_features(
            features=self.pedestrian_relations,
            style=PEDESTRIAN_RELATION_STYLES,
            desc="Rendering pedestrian relations",
        )
