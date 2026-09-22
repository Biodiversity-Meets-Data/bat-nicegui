"""S3-backed datasets used by the analysis-area map widget."""

from dataclasses import dataclass
import io
import json
from typing import Any

import boto3  # type: ignore[import-untyped]
import pyarrow.parquet as parquet  # type: ignore[import-untyped]
from pyproj import Transformer
from shapely import from_wkb  # type: ignore[import-untyped]
from shapely.geometry import mapping, shape  # type: ignore[import-untyped]
from shapely.ops import transform  # type: ignore[import-untyped]

from config import (
    AWS_BUCKET_NAME,
    AWS_COUNTRIES_KEY,
    AWS_NATURA_GEOMETRY_PREFIX,
    AWS_NATURA_INDEX_KEY,
    AWS_REGION,
)


class MapDataError(RuntimeError):
    """Raised when map data cannot be loaded or decoded."""


@dataclass(frozen=True, slots=True)
class MapFeature:
    """A selectable map feature and its serializable geometry."""

    identifier: str
    label: str
    geometry_type: str
    wkt: str
    geojson: dict[str, Any]


@dataclass(frozen=True, slots=True)
class NaturaSiteOption:
    """Search metadata for one Natura2000 site."""

    site_code: str
    site_name: str
    country_code: str
    site_type: str
    geometry_key: str

    @property
    def label(self) -> str:
        """Human-readable dropdown label."""
        country = f" ({self.country_code})" if self.country_code else ""
        return f"{self.site_name} [{self.site_code}]{country}"


# Countries with mainland European territory. Island-only countries are omitted
# because the map selection is intended for continental Europe.
CONTINENTAL_EUROPE_ISO3 = frozenset(
    {
        "ALB",
        "AND",
        "AUT",
        "BEL",
        "BGR",
        "BIH",
        "BLR",
        "CHE",
        "CZE",
        "DEU",
        "DNK",
        "ESP",
        "FRA",
        "GEO",
        "HRV",
        "HUN",
        "ITA",
        "LIE",
        "LTU",
        "LUX",
        "LVA",
        "MCO",
        "MDA",
        "MKD",
        "MNE",
        "NLD",
        "NOR",
        "POL",
        "PRT",
        "ROU",
        "RUS",
        "SMR",
        "SRB",
        "SVK",
        "SVN",
        "SWE",
        "TUR",
        "UKR",
        "VAT",
        "XKX",
    }
)


class MapDataStore:
    """Lazy, process-local cache for country and Natura2000 map data."""

    def __init__(self) -> None:
        self._client = boto3.client("s3", region_name=AWS_REGION)
        self._countries: dict[str, MapFeature] | None = None
        self._natura_sites: dict[str, NaturaSiteOption] | None = None
        self._natura_transformer = Transformer.from_crs(
            "EPSG:3035", "EPSG:4326", always_xy=True
        )

    def country_options(self) -> dict[str, str]:
        """Return country identifiers mapped to searchable labels."""
        return {
            feature.identifier: feature.label
            for feature in self._load_countries().values()
        }

    def country(self, identifier: str) -> MapFeature:
        """Return one country feature by ISO3 or ISO2 identifier."""
        countries = self._load_countries()
        try:
            return countries[identifier]
        except KeyError as exc:
            raise MapDataError(f"Unknown country: {identifier}") from exc

    def natura_options(self) -> dict[str, str]:
        """Return Natura2000 site identifiers mapped to searchable labels."""
        return {key: option.label for key, option in self._load_natura_sites().items()}

    def natura_site(self, site_code: str) -> MapFeature:
        """Fetch and decode one derived Natura2000 geometry object."""
        sites = self._load_natura_sites()
        try:
            option = sites[site_code]
        except KeyError as exc:
            raise MapDataError(f"Unknown Natura2000 site: {site_code}") from exc

        try:
            response = self._client.get_object(
                Bucket=AWS_BUCKET_NAME, Key=option.geometry_key
            )
            payload = json.loads(response["Body"].read())
            geometry = payload.get("geometry", payload)
            shapely_geometry = transform(
                self._natura_transformer.transform, shape(geometry)
            )
            payload = {
                "type": "Feature",
                "properties": payload.get("properties", {}),
                "geometry": mapping(shapely_geometry),
            }
        except Exception as exc:
            raise MapDataError(
                f"Could not load Natura2000 geometry for {site_code}"
            ) from exc

        return MapFeature(
            identifier=site_code,
            label=option.label,
            geometry_type="natura2000",
            wkt=shapely_geometry.wkt,
            geojson=payload,
        )

    @staticmethod
    def _geometry_key(relative_key: str) -> str:
        """Resolve an index key with either supported prefix convention."""
        prefix = AWS_NATURA_GEOMETRY_PREFIX.rstrip("/")
        normalized = relative_key.lstrip("/")
        if normalized.startswith("geometries/") and prefix.endswith("/geometries"):
            prefix = prefix.removesuffix("/geometries")
        return f"{prefix}/{normalized}"

    def _load_countries(self) -> dict[str, MapFeature]:
        if self._countries is not None:
            return self._countries

        try:
            response = self._client.get_object(
                Bucket=AWS_BUCKET_NAME, Key=AWS_COUNTRIES_KEY
            )
            table = parquet.read_table(io.BytesIO(response["Body"].read()))
            columns = table.to_pydict()
            countries: dict[str, MapFeature] = {}
            for iso3, name, iso2, geometry in zip(
                columns["iso3"],
                columns["name"],
                columns["iso2"],
                columns["geometry"],
                strict=True,
            ):
                if not iso3 or not geometry or str(iso3) not in CONTINENTAL_EUROPE_ISO3:
                    continue
                iso3_text = str(iso3)
                shapely_geometry = from_wkb(geometry)
                geojson = mapping(shapely_geometry)
                feature = MapFeature(
                    identifier=iso3_text,
                    label=f"{name} [{iso3}/{iso2}]",
                    geometry_type="country",
                    wkt=shapely_geometry.wkt,
                    geojson={"type": "Feature", "properties": {}, "geometry": geojson},
                )
                countries[iso3_text] = feature
        except Exception as exc:
            raise MapDataError("Could not load country boundaries") from exc

        self._countries = countries
        return countries

    def _load_natura_sites(self) -> dict[str, NaturaSiteOption]:
        if self._natura_sites is not None:
            return self._natura_sites

        try:
            response = self._client.get_object(
                Bucket=AWS_BUCKET_NAME, Key=AWS_NATURA_INDEX_KEY
            )
            table = parquet.read_table(io.BytesIO(response["Body"].read()))
            columns = table.to_pydict()
            sites: dict[str, NaturaSiteOption] = {}
            for values in zip(
                columns["SITECODE"],
                columns["SITENAME"],
                columns.get("MS", [""] * table.num_rows),
                columns.get("SITETYPE", [""] * table.num_rows),
                columns["geometry_object_key"],
                strict=True,
            ):
                site_code, site_name, country_code, site_type, geometry_key = values
                if not site_code or not geometry_key:
                    continue
                sites[str(site_code)] = NaturaSiteOption(
                    site_code=str(site_code),
                    site_name=str(site_name or site_code),
                    country_code=str(country_code or ""),
                    site_type=str(site_type or ""),
                    geometry_key=self._geometry_key(str(geometry_key)),
                )
        except Exception as exc:
            raise MapDataError("Could not load Natura2000 site index") from exc

        self._natura_sites = sites
        return sites


_MAP_DATA_STORE: MapDataStore | None = None


def get_map_data_store() -> MapDataStore:
    """Return the process-local map data store."""
    global _MAP_DATA_STORE
    if _MAP_DATA_STORE is None:
        _MAP_DATA_STORE = MapDataStore()
    return _MAP_DATA_STORE
