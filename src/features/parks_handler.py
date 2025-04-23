from src.rendering import FeatureRenderer, FeaturePolygonData, PolygonStyle
from src.transforms import transform_relation_to_rings_and_holes

from reportlab.lib.colors import Color
from shapely.geometry import Polygon, MultiPolygon
from osmium import osm
from reportlab.pdfgen import canvas
from typing import List, Tuple, Dict
from src.map_dimensions import MapDimensions

PARK_STYLE: PolygonStyle = {
    "fill_color": Color(0.698, 0.792, 0.682),  # Main park green
}

PARK_INTERIOR_STYLE: PolygonStyle = {
    "fill_color": Color(0.8, 0.9, 0.8),  # Lighter green for inner areas
}


class ParksHandler:
    def __init__(self):
        super().__init__()
        if not hasattr(self, "parks"):
            self.parks: List[FeaturePolygonData] = []

    def process_way_park(self, way: osm.Way, coords: List[Tuple[float, float]]) -> bool:
        """Process a way to possibly add it to the park list"""
        if (
            way.tags.get("leisure")
            in [
                "park",
                "garden",
                "playground",
                "pitch",
                "sports_centre",
                "golf_course",
            ]
            or way.tags.get("landuse")
            in [
                "park",
                "grass",
                "recreation_ground",
                "village_green",
                "meadow",
                "cemetery",
                "forest",
            ]
            or way.tags.get("natural")
            in [
                "wood",
                "forest",
            ]
        ):
            self.parks.append(
                {
                    "type": "park_polygon",
                    "exterior": coords,
                    "interiors": [],
                    "name": way.tags.get("name"),
                    "relation_id": None,
                }
            )
            return True

        return False

    def relation_tag_is_park(self, tag: osm.Tag) -> bool:
        """Check if relation is a park"""
        return (tag.k == "leisure" or tag.k == "landuse") and tag.v == "park"

    def process_relation_park(
        self, relation: osm.Relation, way_coords: Dict[int, List[Tuple[float, float]]]
    ) -> bool:
        """Process a relation to possibly add it to the building list"""
        if (
            relation.tags.get("leisure")
            in [
                "park",
                "garden",
                "playground",
                "pitch",
                "sports_centre",
                "golf_course",
            ]
            or relation.tags.get("landuse")
            in [
                "park",
                "grass",
                "recreation_ground",
                "village_green",
                "meadow",
                "cemetery",
                "forest",
                "wood",
                "orchard",
                "vineyard",
                "farm",
                "farmyard",
                "farmyard",
            ]
            or relation.tags.get("natural")
            in [
                "wood",
                "forest",
            ]
        ):
            for ring, holes in transform_relation_to_rings_and_holes(
                relation, way_coords
            ):
                self.parks.append(
                    {
                        "type": "park_polygon",
                        "exterior": ring,
                        "interiors": holes,
                        "name": relation.tags.get("name"),
                        "relation_id": relation.id,
                    }
                )
            return True

        return False

    def add_park_relation(
        self,
        relation_name: str,
        ring: List[Tuple[float, float]],
        holes: List[List[Tuple[float, float]]],
        relation_id: int,
    ) -> None:
        self.parks.append(
            {
                "type": "park_polygon",
                "exterior": ring,
                "interiors": holes,
                "name": relation_name,
                "relation_id": relation_id,
            }
        )

    def render_parks(
        self,
        c: canvas.Canvas,
        map_dimensions: MapDimensions,
        boundary: Polygon | MultiPolygon | None,
    ) -> None:
        renderer = FeatureRenderer(c, map_dimensions, boundary)
        renderer.render_polygon_features(
            features=self.parks, style=PARK_STYLE, desc="Rendering parks"
        )

        # Park interiors should be slightly lighter than the main park color
        all_interior_features: List[FeaturePolygonData] = []
        for park in self.parks:
            if park.get("interiors"):
                all_interior_features.extend(
                    [
                        {
                            "type": "park_interior",
                            "exterior": interior,
                            "interiors": [],
                            "name": None,
                            "relation_id": None,
                        }
                        for interior in park["interiors"]
                    ]
                )

        # Render all interior areas with a single call if there are any
        if all_interior_features:
            renderer.render_polygon_features(
                features=all_interior_features,
                style=PARK_INTERIOR_STYLE,
                desc="Rendering park interiors",
            )
