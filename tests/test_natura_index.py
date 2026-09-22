"""Tests for the Natura2000 preprocessing utility."""

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as parquet
from shapely.geometry import Polygon

from scripts.build_natura2000_index import build_artifacts


def test_build_artifacts_writes_index_and_site_geometry(tmp_path: Path) -> None:
    """The preprocessing output contains searchable metadata and GeoJSON."""
    source = tmp_path / "source.parquet"
    output = tmp_path / "output"
    geometry = Polygon([(10, 50), (11, 50), (11, 51), (10, 50)])
    parquet.write_table(
        pa.table(
            {
                "SITECODE": ["DE0000001"],
                "SITENAME": ["Example Site"],
                "MS": ["DE"],
                "SITETYPE": ["B"],
                "INSPIRE_ID": ["example-id"],
                "geometry": [geometry.wkb],
            }
        ),
        source,
    )

    build_artifacts(source, output)

    index = parquet.read_table(output / "index" / "sites.parquet").to_pydict()
    assert index["SITECODE"] == ["DE0000001"]
    assert index["geometry_object_key"] == ["geometries/DE0000001.geojson"]
    site = json.loads(
        (output / "geometries" / "DE0000001.geojson").read_text(encoding="utf-8")
    )
    assert site["properties"]["SITENAME"] == "Example Site"
    assert site["geometry"]["type"] == "Polygon"
