from pathlib import Path
from typing import Annotated, Any, Generator, Literal

import typer

# import mapillary.interface as mly
# import mapillary.models.geojson as geojson_module
# import mercantile
import dataset_creation.street_view.mapillary_api as api
from dataset_creation.download_mapillary import (
    DEFAULT_DOTENV_PATH,
    DEFAULT_RESOLUTION,
    RESOLUTION_CHOICES,
    download_images,
    get_mapillary_token,
    load_geojson,
)

# def append_feature_without_deduplication(self, feature_inputs: dict) -> None:
#     from mapillary.models.geojson import Feature

#     feature = Feature(feature=feature_inputs)
#     self.features.append(feature)


# Needed for performance
# geojson_module.GeoJSON.append_feature = append_feature_without_deduplication  # type: ignore


ImageDir = Annotated[
    Path,
    typer.Argument(help="Output directory for downloaded images"),
]

GeojsonPath = Annotated[
    Path,
    typer.Argument(help="Path to GeoJSON file defining the download area"),
]

DotenvPath = Annotated[
    Path,
    typer.Option(
        help="Path to the .env (dotenv) file with you mapillary token, named MAPILLARY_TOKEN, defaults to the cross-view-fusion dir"
    ),
]

app = typer.Typer(help="Download Mapillary street view images for dataset creation")


@app.command()
def download(
    geojson: GeojsonPath,
    output: ImageDir,
    resolution: Annotated[
        Literal[256, 1024, 2048], typer.Option("--resolution", "-r")
    ] = DEFAULT_RESOLUTION,
    dotenv_path: DotenvPath = DEFAULT_DOTENV_PATH,
) -> None:
    """Download Mapillary images within a GeoJSON boundary."""
    if resolution not in RESOLUTION_CHOICES:
        typer.echo(f"Error: resolution must be one of {RESOLUTION_CHOICES}", err=True)
        raise typer.Exit(code=1)

    if not geojson.exists():
        typer.echo(f"Error: GeoJSON file not found: {geojson}", err=True)
        raise typer.Exit(code=1)

    token = get_mapillary_token(dotenv_path)

    api.set_token(token)

    typer.echo(f"Loading GeoJSON from: {geojson}")
    geojson_data = load_geojson(geojson)

    typer.echo("Querying Mapillary for images in area...")

    image_data = api.images_in_shape(geojson_data, image_type="pano", is_computed=True)

    if not image_data:
        typer.echo("No images found in the specified area.")
        raise typer.Exit(code=0)

    typer.echo(f"Found {len(image_data.features)} images. Starting download...")

    downloaded, skipped = download_images(image_data.to_dict(), output, resolution)

    typer.echo(f"Download complete: {downloaded} new, {skipped} skipped (already exists)")


# def get_tiles_in_geojson(geojson_data: dict) -> Generator[mercantile.Tile, Any, None]:
#     coords = geojson_data["features"][0]["geometry"]["coordinates"][0]
#     west = 180
#     south = 90
#     east = -180
#     north = -90

#     for coord in coords:
#         if coord[0] < west:
#             west = coord[0]
#         elif coord[0] > east:
#             east = coord[0]

#         if coord[1] < south:
#             south = coord[1]
#         elif coord[1] > north:
#             north = coord[1]
#     print(west, south, east, north)
#     return mercantile.tiles(west, south, east, north, zooms=14)


def main():
    app()
