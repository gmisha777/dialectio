"""Import first-level regions (oblasts) from Natural Earth admin-1 into `region` (level "adm1").

Regions are attached to their country by the ISO 3166-2 code prefix, so Crimea (UA-43) and
Sevastopol (UA-40), which Natural Earth lists under Russia de facto, belong to Ukraine here,
matching the country layer (Ukraine point of view).

Run from backend/ after the countries importer:  uv run python -m app.importers.natural_earth_admin1
"""

import json
from pathlib import Path

import httpx2
import shapefile
from sqlalchemy import select, text

from app.db.session import SessionLocal
from app.importers.common import RAW_DIR, upsert_source
from app.models import Region

DATASET = "ne_10m_admin_1_states_provinces"
BASE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/10m_cultural"
SOURCE_NAME = "Natural Earth 1:10m Admin 1 States, Provinces"
SOURCE_URL = "https://www.naturalearthdata.com/"
SOURCE_LICENSE = "Public domain"

# ISO 3166-2 country prefix -> our country region code
COUNTRIES = {"UA": "UKR"}

# Natural Earth names that are wrong or ambiguous
NAME_FIXES = {
    "UA-32": ("Kyiv Oblast", "Київська область"),
    "UA-30": ("Kyiv", "Київ"),
}

UPSERT_REGION = text("""
    INSERT INTO region (name_en, name_uk, level, code, parent_id, geom, label_point, label_rank)
    VALUES (:name_en, :name_uk, 'adm1', :code, :parent_id,
            ST_Multi(ST_CollectionExtract(ST_MakeValid(
                ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326)), 3)),
            ST_SetSRID(ST_MakePoint(:label_x, :label_y), 4326), :label_rank)
    ON CONFLICT (level, code) DO UPDATE
    SET name_en = EXCLUDED.name_en, name_uk = EXCLUDED.name_uk, parent_id = EXCLUDED.parent_id,
        geom = EXCLUDED.geom, label_point = EXCLUDED.label_point,
        label_rank = EXCLUDED.label_rank
""")


def download(target_dir: Path) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    for ext in ("shp", "shx", "dbf", "prj"):
        path = target_dir / f"{DATASET}.{ext}"
        if path.exists():
            continue
        print(f"Downloading {path.name} ...")
        response = httpx2.get(f"{BASE_URL}/{DATASET}.{ext}", follow_redirects=True, timeout=300)
        response.raise_for_status()
        path.write_bytes(response.content)
    return target_dir / DATASET


def english_name(name: str) -> str:
    # Natural Earth uses transliterations like "Ivano-Frankivs'k"; drop the apostrophes.
    return name.replace("'", "")


def main() -> None:
    reader = shapefile.Reader(str(download(RAW_DIR / "natural_earth")), encoding="utf-8")

    with SessionLocal() as session:
        upsert_source(session, SOURCE_NAME, SOURCE_URL, SOURCE_LICENSE)
        parents = {
            code: session.scalar(
                select(Region.id).where(Region.level == "country", Region.code == code)
            )
            for code in COUNTRIES.values()
        }
        missing = [code for code, region_id in parents.items() if region_id is None]
        if missing:
            raise SystemExit(f"Import countries first, missing: {missing}")

        count = 0
        for shape_record in reader.iterShapeRecords():
            attrs = shape_record.record.as_dict()
            code = attrs["iso_3166_2"] or ""
            country = COUNTRIES.get(code.split("-")[0])
            if country is None:
                continue
            name_en, name_uk = NAME_FIXES.get(
                code, (english_name(attrs["name"]), attrs.get("name_uk") or None)
            )
            session.execute(
                UPSERT_REGION,
                {
                    "code": code,
                    "name_en": name_en,
                    "name_uk": name_uk,
                    "parent_id": parents[country],
                    "geojson": json.dumps(shape_record.shape.__geo_interface__),
                    "label_x": attrs["longitude"],
                    "label_y": attrs["latitude"],
                    "label_rank": attrs["labelrank"],
                },
            )
            count += 1
        session.commit()

    print(f"Imported {count} first-level regions.")


if __name__ == "__main__":
    main()
