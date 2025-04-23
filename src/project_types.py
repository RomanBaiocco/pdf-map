from typing import List, Tuple

Lon = float
Lat = float
Coord = Tuple[Lon, Lat]
Line = List[Coord]

PdfPoint = Tuple[float, float]


class MapConfig:
    def __init__(
        self,
        pbf_file: str,
        bbox_bottom_left_coord: Tuple[Lat, Lon],
        bbox_top_right_coord: Tuple[Lat, Lon],
        boundary_relation_id: int | None = None,
    ):
        if boundary_relation_id is None:
            raise ValueError("boundary_relation_id is required")
        if bbox_bottom_left_coord is None or bbox_top_right_coord is None:
            raise ValueError(
                "bbox_bottom_left_coord and bbox_top_right_coord are required"
            )

        if bbox_bottom_left_coord[0] > bbox_top_right_coord[0]:
            raise ValueError(
                "bbox_bottom_left_coord[0] must be less than bbox_top_right_coord[0]"
            )
        if bbox_bottom_left_coord[1] > bbox_top_right_coord[1]:
            raise ValueError(
                "bbox_bottom_left_coord[1] must be less than bbox_top_right_coord[1]"
            )
        if bbox_bottom_left_coord[0] < -90 or bbox_bottom_left_coord[0] > 90:
            raise ValueError("bbox_bottom_left_coord[0] must be between -90 and 90")
        if bbox_bottom_left_coord[1] < -180 or bbox_bottom_left_coord[1] > 180:
            raise ValueError("bbox_bottom_left_coord[1] must be between -180 and 180")
        if bbox_top_right_coord[0] < -90 or bbox_top_right_coord[0] > 90:
            raise ValueError("bbox_top_right_coord[0] must be between -90 and 90")
        if bbox_top_right_coord[1] < -180 or bbox_top_right_coord[1] > 180:
            raise ValueError("bbox_top_right_coord[1] must be between -180 and 180")
        if (
            bbox_bottom_left_coord[0] == bbox_top_right_coord[0]
            or bbox_bottom_left_coord[1] == bbox_top_right_coord[1]
        ):
            raise ValueError(
                "bbox_bottom_left_coord and bbox_top_right_coord must be different"
            )

        self.pbf_file = pbf_file
        self.bbox_bottom_left_coord = bbox_bottom_left_coord
        self.bbox_top_right_coord = bbox_top_right_coord
        self.boundary_relation_id = boundary_relation_id
