from src.rendering import (
    FeaturePolygonData,
    FeatureRenderer,
    FeatureLineData,
    PolygonStyle,
    LineStyle,
)
from src.transforms import transform_relation_to_rings_and_holes

from osmium import osm
from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas
from shapely.geometry import Polygon, MultiPolygon
from typing import List, Tuple, Dict
from src.map_dimensions import MapDimensions


WATER_STYLE: PolygonStyle = {
    "fill_color": Color(0.529, 0.808, 0.922),
}

RIVER_STYLE: LineStyle = {
    "stroke_color": Color(0.529, 0.808, 0.922),
    "stroke_width": 2,
}


class WaterHandler:
    def __init__(self):
        super().__init__()
        if not hasattr(self, "water"):
            self.water: List[FeaturePolygonData] = []
            self.water_lines: List[FeatureLineData] = []

    def process_way_water(
        self, way: osm.Way, coords: List[Tuple[float, float]]
    ) -> bool:
        """Process a way to possibly add it to the water list"""
        if (
            way.tags.get("natural") in ["water", "wetland", "spring", "lake"]
            or way.tags.get("leisure") in ["swimming_pool"]
            or way.tags.get("amenity") in ["fountain", "swimming_pool"]
            or way.tags.get("waterway")
            in [
                "riverbank",
                "canal",
                "river",
                "stream",
                "lake",
                "pond",
            ]
            or way.tags.get("water")
            in [
                "lake",
                "pond",
                "reservoir",
                "basin",
                "river",
                "canal",
                "stream",
                "moat",
            ]
            or way.tags.get("man_made")
            in [
                "reservoir_covered",
                "reservoir",
                "lake",
                "pond",
            ]
        ):
            if way.tags.get("waterway") in ["river", "stream", "canal"]:
                self.water_lines.append(
                    {
                        "type": "waterway",
                        "coords": coords,
                        "way_id": way.id,
                    }
                )
            else:
                self.water.append(
                    {
                        "type": "water_polygon",
                        "exterior": coords,
                        "interiors": [],
                        "relation_id": None,
                        "name": way.tags.get("name"),
                    }
                )
            return True

        return False

    def add_water_polygon(
        self,
        coords: List[Tuple[float, float]],
        interiors: List[List[Tuple[float, float]]] = [],
        relation_id: int | None = None,
        name: str | None = None,
    ) -> None:
        """Add water as a polygon feature"""
        self.water.append(
            {
                "type": "water_polygon",
                "exterior": coords,
                "interiors": interiors,
                "relation_id": relation_id,
                "name": name,
            }
        )

    def relation_tag_is_water(self, tag: osm.Tag) -> bool:
        """Check if relation is a water feature"""
        return tag.k in ["water", "waterway"]

    def process_relation_water(
        self, relation: osm.Relation, way_coords: Dict[int, List[Tuple[float, float]]]
    ) -> bool:
        """Process a relation to possibly add it to the building list"""
        if bool(relation.tags.get("water") or relation.tags.get("waterway")):
            for ring, holes in transform_relation_to_rings_and_holes(
                relation, way_coords
            ):
                self.water.append(
                    {
                        "type": "water_polygon",
                        "exterior": ring,
                        "interiors": holes,
                        "name": relation.tags.get("name"),
                        "relation_id": relation.id,
                    }
                )
            return True

        return False

    def render_water_features(
        self,
        c: canvas.Canvas,
        map_dimensions: MapDimensions,
        boundary: Polygon | MultiPolygon | None,
    ) -> None:
        """Render water features"""
        renderer = FeatureRenderer(c, map_dimensions, boundary)

        renderer.render_polygon_features(
            features=self.water,
            style=WATER_STYLE,
            desc="Rendering water bodies",
        )

        renderer.render_line_features(
            features=self.water_lines,
            style=RIVER_STYLE,
            desc="Rendering rivers",
        )
