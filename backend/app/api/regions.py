from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_session

router = APIRouter(prefix="/api/regions", tags=["regions"])

MAX_ZOOM = 10
TILE_EXTENT = 4096

# Mapbox Vector Tile layer of one region level. Geometry is simplified to about half a pixel at
# the tile's zoom and clipped to Web Mercator's latitude range (poles can't be projected).
TILE_LAYER = """
    WITH bounds AS (
        SELECT ST_TileEnvelope(:z, :x, :y) AS merc,
               ST_Transform(ST_TileEnvelope(:z, :x, :y), 4326) AS geo
    ),
    features AS (
        SELECT r.id, r.code, r.name_en, r.name_uk, parent.code AS parent_code,
               ST_AsMVTGeom(
                   ST_Transform(
                       ST_ClipByBox2D(
                           ST_SimplifyPreserveTopology(r.geom, :tolerance),
                           ST_MakeEnvelope(-180, -85.0511, 180, 85.0511, 4326)),
                       3857),
                   bounds.merc, :extent, 64, true) AS geom
        FROM region r
        LEFT JOIN region parent ON parent.id = r.parent_id, bounds
        WHERE r.level = '{level}' AND r.geom && bounds.geo
    )
    SELECT ST_AsMVT(features, '{layer}', :extent, 'geom', 'id')
    FROM features
    WHERE geom IS NOT NULL
"""
COUNTRY_TILE = text(TILE_LAYER.format(level="country", layer="countries"))
REGION_TILE = text(TILE_LAYER.format(level="adm1", layer="regions"))
# First-level regions (oblasts) are only drawn from this zoom on.
REGIONS_MIN_ZOOM = 4


def tolerance_degrees(z: int) -> float:
    # Degrees per pixel of a 256px tile at zoom z, halved.
    return 360 / (256 * 2**z) / 2


# Country borders only change when the importer runs, so rendered tiles are kept in memory
# for the life of the process (restart the API after re-importing regions).
_tile_cache: dict[tuple[int, int, int], bytes] = {}
TILE_CACHE_SIZE = 4096


def render_tile(session: Session, z: int, x: int, y: int) -> bytes:
    key = (z, x, y)
    if (tile := _tile_cache.get(key)) is not None:
        return tile
    params = {"z": z, "x": x, "y": y, "tolerance": tolerance_degrees(z), "extent": TILE_EXTENT}
    tile = bytes(session.execute(COUNTRY_TILE, params).scalar_one())
    if z >= REGIONS_MIN_ZOOM:
        # A vector tile is a list of layers, so two encoded tiles concatenate into one.
        tile += bytes(session.execute(REGION_TILE, params).scalar_one())
    if len(_tile_cache) < TILE_CACHE_SIZE:
        _tile_cache[key] = tile
    return tile


@router.get("/tiles/{z}/{x}/{y}.mvt")
def region_tile(
    session: Annotated[Session, Depends(get_session)],
    z: Annotated[int, Path(ge=0, le=MAX_ZOOM)],
    x: Annotated[int, Path(ge=0)],
    y: Annotated[int, Path(ge=0)],
) -> Response:
    if x >= 2**z or y >= 2**z:
        raise HTTPException(status_code=404, detail="Tile out of range")
    tile = render_tile(session, z, x, y)
    return Response(
        content=tile,
        media_type="application/vnd.mapbox-vector-tile",
        headers={"Cache-Control": "public, max-age=86400"},
    )
