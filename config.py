from src.project_types import MapConfig

CONFIG: MapConfig = MapConfig(
    pbf_file="manhattan-bounded.osm.pbf",
    bbox_bottom_left_coord=(40.68, -74.03),  # (Latitude, Longitude)
    bbox_top_right_coord=(40.88, -73.90),  # (Latitude, Longitude)
    boundary_relation_id=8398124,
)
