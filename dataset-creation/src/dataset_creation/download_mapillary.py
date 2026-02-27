import json
import os
from pathlib import Path

import dotenv
import httpx
import mapillary.interface as mly
from tqdm import tqdm

DEFAULT_RESOLUTION = 1024
RESOLUTION_CHOICES = [256, 1024, 2048]


def load_geojson(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def get_mapillary_token() -> str:
    dotenv.load_dotenv()
    token = os.getenv("MAPILLARY_TOKEN")
    if not token:
        raise ValueError("MAPILLARY_TOKEN not found in environment or .env file")
    return token


def download_images(
    images: list[dict],
    output_dir: Path,
    resolution: int,
    max_workers: int = 10,
) -> tuple[int, int]:
    images_dir = output_dir / "images"
    metadata_dir = output_dir / "metadata"
    images_dir.mkdir(parents=True, exist_ok=True)
    metadata_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    skipped = 0

    def download_single(image: dict) -> tuple[bool, bool]:
        image_id = str(image["id"])
        image_path = images_dir / f"{image_id}.jpg"
        metadata_path = metadata_dir / f"{image_id}.json"

        if image_path.exists():
            return False, True

        thumb_url = mly.image_thumbnail(image_id=image_id, resolution=resolution)
        if not thumb_url:
            return False, False

        try:
            response = httpx.get(thumb_url, timeout=30)
            response.raise_for_status()
            image_path.write_bytes(response.content)

            metadata = {
                "id": image_id,
                "thumb_url": thumb_url,
                "resolution": resolution,
            }
            metadata.update(image.get("properties", {}))
            metadata_path.write_text(json.dumps(metadata, indent=2))

            return True, False
        except Exception:
            return False, False

    with httpx.Client(timeout=30) as _:
        with tqdm(total=len(images), desc="Downloading images", unit="img") as pbar:
            for image in images:
                success, skipped_flag = download_single(image)
                if success:
                    downloaded += 1
                elif skipped_flag:
                    skipped += 1
                pbar.update(1)

    return downloaded, skipped
