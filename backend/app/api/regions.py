from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_session

router = APIRouter(prefix="/api/regions", tags=["regions"])

# Simplification tolerance in degrees (~5 km): plenty for a world map, keeps the payload small.
COUNTRIES_GEOJSON = text("""
    SELECT json_build_object(
        'type', 'FeatureCollection',
        'features', coalesce(json_agg(json_build_object(
            'type', 'Feature',
            'id', id,
            'properties', json_build_object(
                'code', code, 'name_en', name_en, 'name_uk', name_uk),
            'geometry', ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, 0.05), 3)::json
        )), '[]'::json)
    )::text
    FROM region
    WHERE level = 'country'
""")


@router.get("/countries.geojson")
def countries_geojson(session: Annotated[Session, Depends(get_session)]) -> Response:
    body = session.execute(COUNTRIES_GEOJSON).scalar_one()
    return Response(
        content=body,
        media_type="application/geo+json",
        headers={"Cache-Control": "public, max-age=86400"},
    )
