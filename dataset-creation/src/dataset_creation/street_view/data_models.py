from typing import Annotated, Any, Literal

from pydantic import BaseModel

type GeoJSON = Annotated[dict[str, Any], "Any dict that would be valid GeoJSON"]


class Geometry(BaseModel):
    coordinates: list[tuple[float, float]] | tuple[float, float]
    type: str

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class Feature(BaseModel):
    type: Literal["Feature"]
    geometry: Geometry
    properties: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class FeatureCollection(BaseModel):
    features: list[Feature]
    type: str | None

    def append_features(self, features: list[dict]) -> None:
        for feature in features:
            self.append_feature(feature)

    def append_feature(self, feature_inputs: dict) -> None:
        feature = Feature(**feature_inputs)
        self.features.append(feature)

    def encode(self) -> str:
        return self.model_dump_json()

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()
