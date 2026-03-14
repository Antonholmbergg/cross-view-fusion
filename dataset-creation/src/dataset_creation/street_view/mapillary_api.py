import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import httpx
import mercantile
import shapely
from geojson import Polygon
from vt2geojson.tools import vt_bytes_to_geojson

from dataset_creation.street_view.data_models import FeatureCollection, GeoJSON

logger = logging.getLogger(__file__)


def set_token(token: str) -> dict:
    """
    Allows the user to set access token to be able to interact with API v4

    :param token: Access token
    :return: Dictionary containing the access token
    """
    if len(token) < 1:
        raise ValueError("Token cannot be empty")
    try:
        MapillaryClient.set_token(token)
    except ValueError:
        raise ValueError("Token is invalid")
    return {"token": "SUCCESS"}


class MapillaryAuth(httpx.Auth):
    def __init__(self, token: str):
        self.token = token

    def auth_flow(self, request):
        request.url = request.url.copy_add_param("access_token", self.token)
        yield request


class MapillaryClient:
    __access_token = ""

    def __init__(self) -> None:
        self.session = httpx.AsyncClient(auth=MapillaryAuth(self.__access_token))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.session.aclose()

    @staticmethod
    def __check_token_validity(token):
        res = httpx.get(
            "https://graph.mapillary.com/1933525276802129?fields=id",
            headers={"Authorization": f"OAuth {token}"},
        )

        if res.status_code == 401:
            res_content = res.json()
            raise ValueError(
                res_content["error"]["message"],
                res_content["error"]["type"],
                res_content["error"]["code"],
                res_content["error"]["fbtrace_id"],
            )

    @staticmethod
    async def download_image(
        client: httpx.AsyncClient,
        image_meta: dict[str, Any],
        images_dir: Path,
        metadata_dir: Path,
        resolution: int,
        sem: asyncio.Semaphore,
    ) -> tuple[bool, bool]:
        image_id = str(image_meta.get("properties", {}).get("id", "false"))
        image_path = images_dir / f"{image_id}.jpg"
        metadata_path = metadata_dir / f"{image_id}.json"

        if image_path.exists():
            return False, True
        url = f"https://graph.mapillary.com/{image_id}?fields=thumb_2048_url"
        header = {"Authorization": f"OAuth {MapillaryClient.__access_token}"}
        async with sem:
            r = await client.get(url, headers=header)
        data = r.json()
        thumb_url = data["thumb_2048_url"]

        if not thumb_url:
            return False, False

        try:
            async with sem:
                response = await client.get(thumb_url, timeout=30)
            response.raise_for_status()
            image_path.write_bytes(response.content)

            metadata = {
                "id": image_id,
                "thumb_url": thumb_url,
                "resolution": resolution,
            }
            metadata.update(image_meta.get("properties", {}))
            metadata_path.write_text(json.dumps(metadata, indent=2))

            return True, False
        except Exception:
            return False, False

    @classmethod
    def set_token(cls, access_token: str) -> None:
        cls.__check_token_validity(access_token)
        cls.__access_token = access_token

    async def get(self, url: str, params: dict = {}) -> httpx.Response:
        req = self.session.build_request("GET", url, params=params)

        res = await self.session.send(req)
        await res.aread()

        if res.status_code == 200:
            try:
                logger.debug(f"Response: {res.json()}")
            except Exception:
                return res

        elif res.status_code >= 400:
            logger.error(f"Server responded with a {res.status_code} error!")
            try:
                logger.debug(f"Error details: {res.json()}")
            except Exception:
                logger.debug(
                    "[Client - _initiate_request] res.json() not available, empty response"
                )
            res.raise_for_status()

        return res


def images_in_shape(
    shape: GeoJSON,
    image_type: Literal["pano", "flat", "all"] = "all",
    is_computed: bool = False,
) -> FeatureCollection:
    polygon = Polygon(shape["features"][0]["geometry"]["coordinates"])
    boundary: shapely.Polygon = shapely.geometry.shape(polygon)

    bbox = _get_bbox_around_polygon_geojson(polygon)

    output = fetch_image_layers(
        bbox, is_computed=is_computed, boundary=boundary, image_type=image_type
    )

    return output


class VectorTiles:
    @staticmethod
    def get_image_layer_url(
        x: float,
        y: float,
        z: float,
    ) -> str:
        """
        Contain positions of images and sequences with original geometries (not computed) for the
        layer 'image'

        This layer offers,

        1. zoom: 14
        2. geometry: Point
        3. data source: images

        With the following properties,

        1. captured_at, int, timestamp in ms since epoch
        2. compass_angle, int, the compass angle of the image
        3. id, int, ID of the image
        4. sequence_id, string, ID of the sequence this image belongs to
        5. organization_id, int, ID of the organization this image belongs to. It can be absent
        6. is_pano, bool, if it is a panoramic image
        """

        return f"https://tiles.mapillary.com/maps/vtp/mly1_public/2/{z}/{x}/{y}/"

    @staticmethod
    def get_computed_image_layer_url(
        x: float,
        y: float,
        z: float,
    ) -> str:
        """
        Contain positions of images and sequences with original geometries (computed) for the
        layer 'image'

        This layer offers,

        1. zoom: 14
        2. geometry: Point
        3. data source: images

        With the following properties,

        1. captured_at, int, timestamp in ms since epoch
        2. compass_angle, int, the compass angle of the image
        3. id, int, ID of the image
        4. sequence_id, string, ID of the sequence this image belongs to
        5. organization_id, int, ID of the organization this image belongs to. It can be absent
        6. is_pano, bool, if it is a panoramic image
        """

        return f"https://tiles.mapillary.com/maps/vtp/mly1_computed_public/2/{z}/{x}/{y}/"


@dataclass
class BBox:
    west: int
    south: int
    east: int
    north: int


def _get_bbox_around_polygon_geojson(geometry: dict) -> BBox:
    coords = geometry["coordinates"][0]
    west = 180
    south = 90
    east = -180
    north = -90

    for coord in coords:
        if coord[0] < west:
            west = coord[0]
        elif coord[0] > east:
            east = coord[0]

        if coord[1] < south:
            south = coord[1]
        elif coord[1] > north:
            north = coord[1]
    return BBox(west=west, south=south, east=east, north=north)


def fetch_image_layers(
    bbox: BBox,
    is_computed: bool,
    boundary: shapely.Polygon,
    image_type: Literal["pano", "flat", "all"],
) -> FeatureCollection:
    ZOOM = 14
    LAYER = "image"

    feature_collection = FeatureCollection(type="FeatureCollection", features=[])

    # A list of tiles that are either confined within or intersect with the bbox
    tiles = list(
        mercantile.tiles(
            west=bbox.west,
            south=bbox.south,
            east=bbox.east,
            north=bbox.north,
            zooms=ZOOM,
        )
    )

    logger.info(
        f"[Vector Tiles API] Fetching {len(tiles)} {'tiles' if len(tiles) > 1 else 'tile'}"
        "for images ..."
    )
    results = asyncio.run(fetch_all(tiles, is_computed, LAYER, ZOOM))
    for result in results:
        for feature in result["features"]:
            point = shapely.geometry.shape(feature["geometry"])
            is_pano = feature["properties"]["is_pano"]
            match image_type:
                case "all":
                    correct_image_type = True
                case "flat":
                    correct_image_type = is_pano is False
                case "pano":
                    correct_image_type = is_pano is True

            if correct_image_type and boundary.contains(point):
                feature_collection.append_feature(feature)

    return feature_collection


async def fetch_tile(client, tile, is_computed, layer, zoom, sem):
    if is_computed:
        url = VectorTiles.get_computed_image_layer_url(x=tile[0], y=tile[1], z=zoom)
    else:
        url = VectorTiles.get_image_layer_url(x=tile[0], y=tile[1], z=zoom)
    async with sem:
        response = await client.get(url)

    return vt_bytes_to_geojson(
        b_content=response.content,
        x=tile.x,
        y=tile.y,
        z=tile.z,
        layer=layer,
    )


async def fetch_all(tiles, is_computed, layer, zoom):
    sem = asyncio.Semaphore(10)
    async with MapillaryClient() as client:
        results = await asyncio.gather(
            *[fetch_tile(client, tile, is_computed, layer, zoom, sem) for tile in tiles],
            return_exceptions=False,
        )
    return results
