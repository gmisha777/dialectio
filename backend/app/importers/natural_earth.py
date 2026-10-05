"""Import country boundaries from Natural Earth (Ukraine point of view) into `region`.

Run from backend/:  uv run python -m app.importers.natural_earth
"""

import json
from pathlib import Path

import httpx2
import shapefile
from sqlalchemy import text

from app.db.session import SessionLocal
from app.importers.common import RAW_DIR, upsert_source

DATASET = "ne_10m_admin_0_countries_ukr"
BASE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/10m_cultural"
SOURCE_NAME = "Natural Earth 1:10m Admin 0 Countries (Ukraine point of view)"
SOURCE_URL = "https://www.naturalearthdata.com/"
SOURCE_LICENSE = "Public domain"

UPSERT_REGION = text("""
    INSERT INTO region (name_en, name_uk, level, code, geom, label_point, label_rank)
    VALUES (:name_en, :name_uk, 'country', :code,
            ST_Multi(ST_CollectionExtract(ST_MakeValid(
                ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326)), 3)),
            ST_SetSRID(ST_MakePoint(:label_x, :label_y), 4326), :label_rank)
    ON CONFLICT (level, code) DO UPDATE
    SET name_en = EXCLUDED.name_en, name_uk = EXCLUDED.name_uk, geom = EXCLUDED.geom,
        label_point = EXCLUDED.label_point, label_rank = EXCLUDED.label_rank
""")


def download(target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    for ext in ("shp", "shx", "dbf", "prj"):
        path = target_dir / f"{DATASET}.{ext}"
        if path.exists():
            continue
        print(f"Downloading {path.name} ...")
        response = httpx2.get(f"{BASE_URL}/{DATASET}.{ext}", follow_redirects=True, timeout=120)
        response.raise_for_status()
        path.write_bytes(response.content)
    return target_dir / DATASET


def main() -> None:
    reader = shapefile.Reader(str(download(RAW_DIR / "natural_earth")), encoding="utf-8")

    with SessionLocal() as session:
        upsert_source(session, SOURCE_NAME, SOURCE_URL, SOURCE_LICENSE)
        count = 0
        for shape_record in reader.iterShapeRecords():
            attrs = shape_record.record.as_dict()
            # ISO_A3 is "-99" for some countries (France, Norway); ADM0_A3 is always set.
            session.execute(
                UPSERT_REGION,
                {
                    "code": attrs["ADM0_A3"],
                    "name_en": attrs["NAME_EN"],
                    "name_uk": attrs["NAME_UK"] or None,
                    "geojson": json.dumps(shape_record.shape.__geo_interface__),
                    "label_x": attrs["LABEL_X"],
                    "label_y": attrs["LABEL_Y"],
                    "label_rank": attrs["LABELRANK"],
                },
            )
            count += 1
        session.commit()

    print(f"Imported {count} countries.")


if __name__ == "__main__":
    main()
