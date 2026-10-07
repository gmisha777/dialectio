"""Map labels for a concept: the word(s) to print on each country and first-level region.

Countries show the main word of every language mapped to them (main language first).
First-level regions (oblasts) show dialect words when a dialect of that region has a word
for the concept, otherwise the country's word, plus regional languages mapped to the region
(e.g. Crimean Tatar in Crimea). The map shows region labels instead of their country's label
when zoomed in.
"""

from collections import defaultdict
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

# Primary approved word of each variety for the concept, per region the variety is mapped to.
REGION_WORDS = text("""
    SELECT r.id AS region_id, v.id AS variety_id, v.kind, f.spelling
    FROM form f
    JOIN variety v ON v.id = f.variety_id
    JOIN variety_region vr ON vr.variety_id = v.id
    JOIN region r ON r.id = vr.region_id
    WHERE f.concept_id = :concept_id AND f.is_primary AND f.status = 'approved'
    ORDER BY v.id
""")

REGIONS = text("""
    SELECT r.id, r.code, r.level, r.name_en, r.name_uk, r.parent_id, parent.code AS parent_code,
           ST_X(point) AS lng, ST_Y(point) AS lat,
           coalesce(r.label_rank, 10) AS rank, ST_Area(r.geom) AS area
    FROM region r
    LEFT JOIN region parent ON parent.id = r.parent_id,
         LATERAL (SELECT coalesce(r.label_point, ST_PointOnSurface(r.geom)) AS point) p
    WHERE r.id = ANY(:region_ids) OR r.parent_id = ANY(:region_ids)
""")


def join_words(words: list[str]) -> str:
    unique = list(dict.fromkeys(words))  # keep order, drop repeats ("бараболя / бараболя")
    return " / ".join(unique)


def build_labels(session: Session, concept_id: int) -> dict[str, Any]:
    words: dict[int, list[tuple[int, str, str]]] = defaultdict(list)
    for row in session.execute(REGION_WORDS, {"concept_id": concept_id}):
        words[row.region_id].append((row.variety_id, row.kind, row.spelling))
    if not words:
        return {"type": "FeatureCollection", "features": []}

    regions = session.execute(REGIONS, {"region_ids": list(words)}).all()
    ordered: list[tuple[tuple[int, float], dict[str, Any]]] = []
    for region in regions:
        own = words.get(region.id, [])
        if region.level == "country":
            if not own:
                continue
            label = join_words([spelling for _, _, spelling in own])
            dialect = False
        else:
            dialect_words = [s for _, kind, s in own if kind == "dialect"]
            regional = [s for _, kind, s in own if kind != "dialect"]
            base = dialect_words or [s for _, _, s in words.get(region.parent_id, [])]
            if not base and not regional:
                continue
            label = join_words(base + regional)
            dialect = bool(dialect_words)
        feature = {
            "type": "Feature",
            "properties": {
                "code": region.code,
                "level": region.level,
                "parent_code": region.parent_code,
                "text": label,
                "dialect": dialect,
                "name_en": region.name_en,
                "name_uk": region.name_uk,
                "rank": region.rank,
            },
            "geometry": {
                "type": "Point",
                "coordinates": [round(region.lng, 3), round(region.lat, 3)],
            },
        }
        # Most important labels first (the map hides lower ones where labels overlap).
        ordered.append(((region.rank, -region.area), feature))
    ordered.sort(key=lambda item: item[0])
    return {"type": "FeatureCollection", "features": [feature for _, feature in ordered]}
