import json

import rasterio
from pyproj import Transformer
from rasterio.crs import CRS
from rasterio.mask import mask
from shapely.geometry import box


def crop_sentinel2(tif_path, output_path, lon_min, lat_min, lon_max, lat_max):
    with rasterio.open(tif_path) as src:
        # Transform lat/lon (WGS84) → image CRS (likely UTM)
        transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)

        x_min, y_min = transformer.transform(lon_min, lat_min)
        x_max, y_max = transformer.transform(lon_max, lat_max)

        # Create bounding box geometry
        bbox = box(x_min, y_min, x_max, y_max)
        geojson = [json.loads(bbox.__geo_interface__.__str__().replace("'", '"'))]

        # Actually just use mapping():
        from shapely.geometry import mapping

        geojson = [mapping(bbox)]

        # Crop
        out_image, out_transform = mask(src, geojson, crop=True)
        out_meta = src.meta.copy()
        out_meta.update(
            {
                "height": out_image.shape[1],
                "width": out_image.shape[2],
                "transform": out_transform,
            }
        )

        with rasterio.open(output_path, "w", **out_meta) as dest:
            dest.write(out_image)


if __name__ == "__main__":
    crop_sentinel2(
        "T32VNH_B04.tif",
        "cropped_output.tif",
        lon_min=17.8,
        lat_min=59.5,
        lon_max=18.2,
        lat_max=59.8,
    )
