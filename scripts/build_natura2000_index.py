#!/usr/bin/env python3
"""Build lookup-friendly Natura2000 artifacts from the source GeoParquet."""

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from typing import Any

import boto3
import pyarrow as pa
import pyarrow.parquet as parquet
from dotenv import load_dotenv
from pyproj import Transformer
from shapely import from_wkb
from shapely.geometry import mapping
from shapely.ops import transform


@dataclass(frozen=True, slots=True)
class Settings:
    bucket: str
    source_key: str
    output_dir: Path
    upload_prefix: str | None
    region: str
    source_crs: str


def parse_args() -> Settings:
    """Parse command-line options and environment-backed defaults."""
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket", default=os.getenv("AWS_BUCKET_NAME", ""))
    parser.add_argument(
        "--source-key",
        default="natura2000/Natura2000_end2024/NaturaSite_polygon.parquet",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--upload-prefix",
        help="Upload generated files to this S3 prefix after building them.",
    )
    parser.add_argument(
        "--region",
        default=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "eu-north-1")),
    )
    parser.add_argument(
        "--source-crs",
        default=os.getenv("AWS_NATURA_SOURCE_CRS", "EPSG:3035"),
        help="CRS of the source Natura2000 geometries (default: EPSG:3035).",
    )
    args = parser.parse_args()
    if not args.bucket:
        parser.error("--bucket or AWS_BUCKET_NAME is required")
    return Settings(
        bucket=args.bucket,
        source_key=args.source_key,
        output_dir=args.output_dir,
        upload_prefix=args.upload_prefix,
        region=args.region,
        source_crs=args.source_crs,
    )


def download_source(settings: Settings, destination: Path) -> None:
    """Download the authoritative source object to a local temporary file."""
    client = boto3.client("s3", region_name=settings.region)
    client.download_file(settings.bucket, settings.source_key, str(destination))


def build_artifacts(
    source: Path, output_dir: Path, source_crs: str = "EPSG:3035"
) -> None:
    """Create an index Parquet file and one GeoJSON file per site."""
    output_dir.mkdir(parents=True, exist_ok=True)
    index_dir = output_dir / "index"
    index_dir.mkdir(parents=True, exist_ok=True)
    geometry_dir = output_dir / "geometries"
    geometry_dir.mkdir(parents=True, exist_ok=True)
    transformer = Transformer.from_crs(source_crs, "EPSG:4326", always_xy=True)

    source_table = parquet.read_table(source)
    rows: list[dict[str, Any]] = []
    columns = source_table.to_pydict()
    for values in zip(
        columns["SITECODE"],
        columns["SITENAME"],
        columns["MS"],
        columns["SITETYPE"],
        columns["INSPIRE_ID"],
        columns["geometry"],
        strict=True,
    ):
        site_code, site_name, country_code, site_type, inspire_id, wkb = values
        if not site_code or not wkb:
            continue
        site_code_text = str(site_code)
        geometry = transform(transformer.transform, from_wkb(wkb))
        filename = f"{site_code_text}.geojson"
        geometry_key = f"geometries/{filename}"
        feature = {
            "type": "Feature",
            "properties": {
                "SITECODE": site_code_text,
                "SITENAME": str(site_name or site_code_text),
                "MS": str(country_code or ""),
                "SITETYPE": str(site_type or ""),
                "INSPIRE_ID": str(inspire_id or ""),
            },
            "geometry": mapping(geometry),
        }
        (geometry_dir / filename).write_text(
            json.dumps(feature, separators=(",", ":")), encoding="utf-8"
        )
        bounds = geometry.bounds
        rows.append(
            {
                "SITECODE": site_code_text,
                "SITENAME": str(site_name or site_code_text),
                "MS": str(country_code or ""),
                "SITETYPE": str(site_type or ""),
                "INSPIRE_ID": str(inspire_id or ""),
                "bbox": [bounds[0], bounds[1], bounds[2], bounds[3]],
                "geometry_object_key": geometry_key,
            }
        )

    parquet.write_table(pa.Table.from_pylist(rows), index_dir / "sites.parquet")


def upload_artifacts(settings: Settings) -> None:
    """Upload generated artifacts while preserving their relative paths."""
    if settings.upload_prefix is None:
        return
    client = boto3.client("s3", region_name=settings.region)
    for path in settings.output_dir.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(settings.output_dir).as_posix()
        key = f"{settings.upload_prefix.rstrip('/')}/{relative}"
        client.upload_file(str(path), settings.bucket, key)


def main() -> None:
    """Build and optionally publish the Natura2000 lookup artifacts."""
    settings = parse_args()
    with tempfile.TemporaryDirectory() as temporary_dir:
        source = Path(temporary_dir) / "NaturaSite_polygon.parquet"
        download_source(settings, source)
        build_artifacts(source, settings.output_dir, settings.source_crs)
    upload_artifacts(settings)


if __name__ == "__main__":
    main()
