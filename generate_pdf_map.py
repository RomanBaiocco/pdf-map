import os
import osmium
import time
from tqdm import tqdm
from datetime import datetime
from reportlab.pdfgen import canvas

from src.logger import logger
from src.osm_handler import OSMHandler
from config import CONFIG
from src.map_dimensions import MapDimensions


class PdfMapHandler(OSMHandler):
    def __init__(self, boundary_relation_id: int | None = None):
        super().__init__(boundary_relation_id)
        self.progress: tqdm | None = None


class CounterHandler(osmium.SimpleHandler):
    "Counts the number of elements in the OSM file"

    def __init__(self):
        super().__init__()
        self.node_count = 0
        self.way_count = 0
        self.relation_count = 0

    def way(self, _w):
        self.way_count += 1

    def node(self, _n):
        self.node_count += 1

    def relation(self, _r):
        self.relation_count += 1


def main():
    # Start timing
    start_time = time.time()

    map_dimensions = MapDimensions(
        bottom_left_coord=CONFIG.bbox_bottom_left_coord,
        top_right_coord=CONFIG.bbox_top_right_coord,
    )

    # Generate timestamp for the output file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join("maps", f"pdf_map_{timestamp}.pdf")
    os.makedirs("maps", exist_ok=True)

    # Count the number of elements in the OSM file
    logger.info("Counting elements in the OSM file...")
    counter = CounterHandler()
    counter.apply_file(CONFIG.pbf_file)
    logger.info(
        f"Found {counter.node_count} nodes, {counter.way_count} ways, and {counter.relation_count} relations"
    )

    handler = PdfMapHandler(CONFIG.boundary_relation_id)

    # First pass
    logger.info("First pass: identifying needed nodes...")
    handler.progress = tqdm(
        total=counter.way_count + counter.node_count,
        desc="Processing OSM data (Pass 1)",
    )
    handler.apply_file(CONFIG.pbf_file)
    handler.progress.close()

    # Second pass
    logger.info("Second pass: processing features...")
    handler.pass_num = 2
    handler.progress = tqdm(
        total=counter.way_count + counter.node_count,
        desc="Processing OSM data (Pass 2)",
    )
    handler.apply_file(CONFIG.pbf_file)
    handler.progress.close()

    logger.info(f"Found {len(handler.coastlines)} coastline segments")

    boundary_polygon = handler.get_boundary_polygon()

    c = canvas.Canvas(
        output_path,
        pagesize=(map_dimensions.width_points, map_dimensions.height_points),
    )

    handler.render_coastline_and_background_water(c, map_dimensions)
    handler.render_parks(c, map_dimensions, boundary_polygon)
    handler.render_water_features(c, map_dimensions, boundary_polygon)
    handler.render_buildings(c, map_dimensions, boundary_polygon)
    handler.render_roads(c, map_dimensions, boundary_polygon)

    c.save()

    end_time = time.time()
    execution_time = end_time - start_time
    minutes = int(execution_time // 60)
    seconds = execution_time % 60
    logger.info(f"Generated map at: {output_path}")
    logger.info(f"Total execution time: {minutes} minutes and {seconds:.2f} seconds")


if __name__ == "__main__":
    main()
