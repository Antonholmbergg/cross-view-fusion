import typer
from pathlib import Path
from typing import Annotated

from dataset_creation.download_mapillary import (
    DEFAULT_RESOLUTION,
    RESOLUTION_CHOICES,
    download_images,
    get_mapillary_token,
    load_geojson,
)

app = typer.Typer(help="Download Mapillary street view images for dataset creation")

ImageDir = Annotated[
    Path,
    typer.Argument(help="Output directory for downloaded images"),
]

GeojsonPath = Annotated[
    Path,
    typer.Argument(help="Path to GeoJSON file defining the download area"),
]


@app.command()
def download(
    geojson: GeojsonPath,
    output: ImageDir,
    resolution: Annotated[int, typer.Option("--resolution", "-r")] = DEFAULT_RESOLUTION,
) -> None:
    """Download Mapillary images within a GeoJSON boundary."""
    if resolution not in RESOLUTION_CHOICES:
        typer.echo(f"Error: resolution must be one of {RESOLUTION_CHOICES}", err=True)
        raise typer.Exit(code=1)

    if not geojson.exists():
        typer.echo(f"Error: GeoJSON file not found: {geojson}", err=True)
        raise typer.Exit(code=1)

    token = get_mapillary_token()
    import mapillary.interface as mly

    mly.set_access_token(token)

    typer.echo(f"Loading GeoJSON from: {geojson}")
    geojson_data = load_geojson(geojson)

    typer.echo("Querying Mapillary for images in area...")
    images_data = mly.images_in_geojson(geojson_data)
    images = list(images_data)

    if not images:
        typer.echo("No images found in the specified area.")
        raise typer.Exit(code=0)

    typer.echo(f"Found {len(images)} images. Starting download...")

    downloaded, skipped = download_images(images, output, resolution)

    typer.echo(
        f"Download complete: {downloaded} new, {skipped} skipped (already exists)"
    )


def main() -> None:
    app()
