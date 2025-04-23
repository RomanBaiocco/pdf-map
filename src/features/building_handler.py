from src.rendering import FeatureRenderer, FeaturePolygonData, PolygonStyle

from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas
from shapely.geometry import Polygon, MultiPolygon
from osmium import osm
from typing import List, Tuple, Dict
from src.map_dimensions import MapDimensions
from src.transforms import transform_relation_to_rings_and_holes


BUILDING_STYLE: PolygonStyle = {
    "fill_color": Color(0.85, 0.85, 0.85),
}


class BuildingHandler:
    def __init__(self):
        super().__init__()
        if not hasattr(self, "buildings"):
            self.buildings: List[FeaturePolygonData] = []

    def process_way_building(
        self, way: osm.Way, coords: List[Tuple[float, float]]
    ) -> bool:
        """Process a way to possibly add it to the building list"""
        has_building_tag = bool(way.tags.get("building", None))
        is_not_underground = way.tags.get("location", None) not in ["underground"]

        if has_building_tag and is_not_underground:
            self.buildings.append(
                {
                    "type": "building_polygon",
                    "exterior": coords,
                    "interiors": [],
                    "name": None,
                    "relation_id": None,
                }
            )
            return True

        return False

    def process_relation_building(
        self, relation: osm.Relation, way_coords: Dict[int, List[Tuple[float, float]]]
    ) -> bool:
        """Process a relation to possibly add it to the building list"""
        if bool(relation.tags.get("building", None)):
            for ring, holes in transform_relation_to_rings_and_holes(
                relation, way_coords
            ):
                self.buildings.append(
                    {
                        "type": "building_polygon",
                        "exterior": ring,
                        "interiors": holes,
                        "name": relation.tags.get("name"),
                        "relation_id": relation.id,
                    }
                )
            return True

        return False

    def relation_tag_is_building(self, tag: osm.Tag) -> bool:
        """Check if relation is a building"""
        return tag.k == "building" and tag.v not in ["no", "false"]

    def add_building_relation(
        self,
        relation_name: str,
        ring: List[Tuple[float, float]],
        holes: List[List[Tuple[float, float]]],
        relation_id: int,
    ) -> None:
        self.buildings.append(
            {
                "type": "building_polygon",
                "exterior": ring,
                "interiors": holes,
                "name": relation_name,
                "relation_id": relation_id,
            }
        )

    def render_buildings(
        self,
        c: canvas.Canvas,
        map_dimensions: MapDimensions,
        boundary: Polygon | MultiPolygon | None,
    ) -> None:
        renderer = FeatureRenderer(c, map_dimensions, boundary)
        renderer.render_polygon_features(
            features=self.buildings,
            style=BUILDING_STYLE,
            desc="Rendering buildings",
        )
