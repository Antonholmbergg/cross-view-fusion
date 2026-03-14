import asyncio
import json
import os
from pathlib import Path

import dotenv
import httpx
from tqdm.asyncio import tqdm as async_tqdm

import dataset_creation.street_view.mapillary_api as api

DEFAULT_RESOLUTION = 1024
RESOLUTION_CHOICES = [256, 1024, 2048]
DEFAULT_DOTENV_PATH = Path(__file__).parent.parent.parent.parent / ".env"


def load_geojson(path: Path) -> dict:
    with open(path, mode="r") as f:
        return json.load(f)


def get_mapillary_token(dotenv_path: Path) -> str:
    dotenv.load_dotenv(dotenv_path)
    token = os.getenv("MAPILLARY_TOKEN")
    if not token:
        raise ValueError("MAPILLARY_TOKEN not found in environment or .env file")
    return token


def download_images(
    images: dict,
    output_dir: Path,
    resolution: int,
    max_semaphores: int = 10,
) -> tuple[int, int]:
    images_dir = output_dir / "images"
    metadata_dir = output_dir / "metadata"
    images_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    skipped = 0
    results = asyncio.run(
        download_all(images["features"], images_dir, metadata_dir, resolution, max_semaphores)
    )
    for success, skipped_flag in results:
        if success:
            downloaded += 1
        elif skipped_flag:
            skipped += 1

    return downloaded, skipped


async def download_all(
    images, images_dir, metadata_dir, resolution, max_semaphores
) -> list[tuple[bool, bool]]:
    sem = asyncio.Semaphore(max_semaphores)
    async with httpx.AsyncClient() as client:
        results = await async_tqdm.gather(
            *[
                api.MapillaryClient.download_image(
                    client, image, images_dir, metadata_dir, resolution, sem
                )
                for image in images
            ],
            total=len(images),
            desc="Downloading images",
            unit="img",
        )
    return results
