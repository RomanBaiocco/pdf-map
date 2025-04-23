from src.scale import POINTS_PER_METER
from src.logger import logger
from tqdm import tqdm
from shapely.geometry import (
    MultiPolygon,
    Polygon,
    LineString,
)
from reportlab.lib.colors import Color
from reportlab.pdfgen import canvas, pathobject
from typing import Callable, Tuple, Union, List, TypedDict, NotRequired
from src.map_dimensions import MapDimensions


class PolygonStyle(TypedDict):
    fill_color: Color


class LineStyle(TypedDict):
    stroke_color: Color
    stroke_width: float
    round_cap: NotRequired[bool]


class FeaturePolygonData(TypedDict):
    type: str
    exterior: List[Tuple[float, float]]
    interiors: List[List[Tuple[float, float]]]

    name: str | None
    relation_id: int | None


class FeatureLineData(TypedDict):
    type: str
    coords: List[Tuple[float, float]]
    way_id: int
    hierarchy: NotRequired[int]  # Used by road features to store importance level


class FeatureRenderer:
    def __init__(
        self,
        canvas: canvas.Canvas,
        map_dimensions: MapDimensions,
        boundary: Polygon | MultiPolygon | None,
    ):
        self.canvas = canvas
        self.transform_coords = map_dimensions.transform_coords
        self.boundary = boundary

    def render_line_features(
        self,
        features: List[FeatureLineData],
        style: Union[LineStyle, Callable[[FeatureLineData], LineStyle]],
        desc: str = "Drawing line features",
    ) -> None:
        """Render a list of line features with the specified style"""
        for feature in tqdm(features, desc=desc):
            try:
                feature_style: LineStyle = (
                    style if not callable(style) else style(feature)
                )
                self._render_line_feature(feature, feature_style)
            except Exception as e:
                logger.warning(f"Failed to render line feature: {e}")

    def _render_line_feature(
        self,
        feature: FeatureLineData,
        style: LineStyle,
    ) -> None:
        """Render a line feature"""
        coords = feature["coords"]
        if len(coords) < 2:
            return

        feature_line = LineString(coords)
        if self.boundary and not feature_line.intersects(self.boundary):
            return

        p = self.canvas.beginPath()
        x, y = self.transform_coords(*coords[0])
        p.moveTo(x, y)
        for coord in coords[1:]:
            x, y = self.transform_coords(*coord)
            p.lineTo(x, y)

        self.canvas.setStrokeColor(style["stroke_color"])
        self.canvas.setLineWidth(
            style["stroke_width"] * POINTS_PER_METER
        )  # Stroke width 1=1m, 10=10m
        if style.get("round_cap", False):
            self.canvas.setLineCap(1)
            self.canvas.setLineJoin(1)

        self.canvas.drawPath(p, fill=0, stroke=1)

    def render_polygon_features(
        self,
        features: List[FeaturePolygonData],
        style: PolygonStyle,
        desc: str = "Drawing features",
    ) -> None:
        """
        Render a list of geographic features with the same style

        Args:
            features: List of feature dictionaries
            style: Dictionary containing rendering style
            desc: Description for progress bar
        """

        for feature in tqdm(features, desc=desc):
            try:
                self._render_polygon_feature(feature, style)
            except Exception as e:
                logger.warning(f"Failed to render feature: {e}")

    def _render_polygon_feature(
        self,
        feature: FeaturePolygonData,
        style: PolygonStyle,
    ) -> None:
        """
        Render a geographic feature with the specified style

        Args:
            feature: Dictionary containing feature data with 'exterior' and optional 'interiors'
            style: Dictionary containing rendering style (color, stroke, etc)
        """
        exterior_coords = feature.get("exterior", [])
        interiors = feature.get("interiors", [])

        # Quick validation - need at least 3 points for a polygon
        if len(exterior_coords) < 3:
            return

        # Create exterior polygon
        exterior_poly = create_polygon_from_coords(exterior_coords)
        if not exterior_poly:
            return

        # Check if feature intersects boundary
        if self.boundary and not exterior_poly.intersects(self.boundary):
            return

        # If we have interior polygons (holes), handle them together with the exterior
        if interiors:
            # Create a list of interior polygons
            interior_polys = []
            for interior in interiors:
                if len(interior) >= 3:
                    interior_poly = create_polygon_from_coords(interior)
                    if interior_poly:
                        interior_polys.append(interior_poly)

            # Create a single polygon with holes
            if interior_polys:
                # Create a polygon with holes using the exterior and interiors
                try:
                    # Use the exterior and interior rings to create a proper polygon with holes
                    multi_poly = Polygon(
                        exterior_poly.exterior.coords,
                        [interior.exterior.coords for interior in interior_polys],
                    )
                    self._draw_polygon(multi_poly, style)
                    return
                except Exception as e:
                    logger.warning(f"Failed to create polygon with holes: {e}")
                    # Fall back to drawing just the exterior if creating the complex polygon fails

        # If we have no interiors or if creating the complex polygon failed, just draw the exterior
        self._draw_polygon(exterior_poly, style)

    def _draw_polygon(self, polygon: Polygon, style: PolygonStyle) -> None:
        """Internal method to draw a polygon with the specified style"""
        p = self.canvas.beginPath()
        self._draw_polygon_to_path(p, polygon)

        self.canvas.setFillColor(style["fill_color"])
        self.canvas.drawPath(p, fill=1, stroke=0)

    def _draw_polygon_to_path(
        self,
        p: pathobject.PDFPathObject,
        polygon: Union[Polygon, MultiPolygon],
    ) -> None:
        """Draw a polygon to a ReportLab path object"""
        if isinstance(polygon, MultiPolygon):
            for geom in polygon.geoms:
                self._draw_polygon_to_path(p, geom)
            return

        # Draw exterior
        exterior_coords = list(polygon.exterior.coords)
        x, y = self.transform_coords(*exterior_coords[0])
        p.moveTo(x, y)
        for coord in exterior_coords[1:]:
            x, y = self.transform_coords(*coord)
            p.lineTo(x, y)
        p.close()

        # Draw interior rings (holes)
        for interior in polygon.interiors:
            interior_coords = list(interior.coords)
            x, y = self.transform_coords(*interior_coords[0])
            p.moveTo(x, y)
            for coord in interior_coords[1:]:
                x, y = self.transform_coords(*coord)
                p.lineTo(x, y)
            p.close()


def create_polygon_from_coords(coords: List[Tuple[float, float]]) -> Polygon | None:
    """Creates a Polygon from a list of coordinates. Returns None if the coordinates do not form a valid polygon."""
    if len(coords) >= 3:
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        try:
            return Polygon(coords)
        except:
            return None
    return None
