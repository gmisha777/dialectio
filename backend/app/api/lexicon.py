import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

from app.api.schemas import (
    ConceptDetail,
    ConceptSummary,
    FormOut,
    LanguageForms,
    SearchHit,
)
from app.db.session import get_session
from app.models import Concept, Form, Variety

router = APIRouter(prefix="/api", tags=["lexicon"])

SessionDep = Annotated[Session, Depends(get_session)]

# Rank: exact match 3, prefix match 2, otherwise trigram similarity (0..1).
# Matches word spellings in any language and concept glosses (en/uk).
SEARCH = text("""
    WITH candidates AS (
        SELECT f.concept_id, f.spelling AS matched, f.variety_id, f.is_primary
        FROM form f
        WHERE lower(f.spelling) LIKE :prefix ESCAPE '\\'
           OR similarity(lower(f.spelling), :q) > 0.4
        UNION ALL
        SELECT c.id, g.gloss, NULL, true
        FROM concept c, LATERAL (VALUES (c.gloss_en), (c.gloss_uk)) AS g(gloss)
        WHERE g.gloss IS NOT NULL
          AND (lower(g.gloss) LIKE :prefix ESCAPE '\\' OR similarity(lower(g.gloss), :q) > 0.4)
    ), scored AS (
        SELECT *,
               CASE WHEN lower(matched) = :q THEN 3
                    WHEN lower(matched) LIKE :prefix ESCAPE '\\' THEN 2
                    ELSE similarity(lower(matched), :q) END AS score
        FROM candidates
    )
    SELECT DISTINCT ON (concept_id) concept_id, matched, variety_id, score
    FROM scored
    ORDER BY concept_id, score DESC,
             variety_id = (SELECT id FROM variety WHERE iso639_3 = :prefer) DESC NULLS LAST,
             is_primary DESC
""")

LABELS = text("""
    SELECT json_build_object(
        'type', 'FeatureCollection',
        'features', coalesce(json_agg(json_build_object(
            'type', 'Feature',
            'properties', json_build_object('code', code, 'text', spellings),
            'geometry', ST_AsGeoJSON(ST_PointOnSurface(geom), 3)::json
        )), '[]'::json)
    )::text
    FROM (
        SELECT r.code, r.geom, string_agg(DISTINCT f.spelling, ' / ') AS spellings
        FROM form f
        JOIN variety_region vr ON vr.variety_id = f.variety_id
        JOIN region r ON r.id = vr.region_id
        WHERE f.concept_id = :concept_id AND f.is_primary
        GROUP BY r.code, r.geom
    ) labelled
""")


def like_prefix(q: str) -> str:
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"{escaped}%"


@router.get("/search")
def search(
    session: SessionDep,
    q: Annotated[str, Query(min_length=1, max_length=100)],
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
    # ISO 639-3 code of the language to prefer when the same spelling exists in several
    # languages (e.g. "вода" is both Ukrainian and Russian); usually the UI language.
    prefer: Annotated[str, Query(max_length=3)] = "ukr",
) -> list[SearchHit]:
    needle = q.strip().lower()
    if not needle:
        return []
    params = {"q": needle, "prefix": like_prefix(needle), "prefer": prefer}
    rows = session.execute(SEARCH, params).all()
    rows = sorted(rows, key=lambda r: r.score, reverse=True)[:limit]

    concepts = {
        c.id: c
        for c in session.scalars(
            select(Concept).where(Concept.id.in_([r.concept_id for r in rows]))
        )
    }
    varieties = {
        v.id: v
        for v in session.scalars(
            select(Variety).where(Variety.id.in_({r.variety_id for r in rows if r.variety_id}))
        )
    }
    hits = []
    for row in rows:
        variety = varieties.get(row.variety_id)
        hits.append(
            SearchHit(
                concept=ConceptSummary.model_validate(concepts[row.concept_id]),
                matched_spelling=row.matched,
                matched_language_en=variety.name_en if variety else "English",
                matched_language_uk=variety.name_uk if variety else None,
            )
        )
    return hits


@router.get("/concepts/{concept_id}")
def concept_detail(session: SessionDep, concept_id: int) -> ConceptDetail:
    concept = session.get(Concept, concept_id)
    if concept is None:
        raise HTTPException(status_code=404, detail="Concept not found")

    forms = session.scalars(
        select(Form)
        .where(Form.concept_id == concept_id)
        .options(
            selectinload(Form.audio),
            selectinload(Form.variety).selectinload(Variety.regions),
        )
        .order_by(Form.variety_id, Form.is_primary.desc(), Form.spelling)
    ).all()

    languages: dict[int, LanguageForms] = {}
    for form in forms:
        variety = form.variety
        entry = languages.get(variety.id)
        if entry is None:
            entry = languages[variety.id] = LanguageForms(
                variety_id=variety.id,
                iso639_3=variety.iso639_3,
                name_en=variety.name_en,
                name_uk=variety.name_uk,
                region_codes=sorted(r.code for r in variety.regions),
                forms=[],
            )
        entry.forms.append(FormOut.model_validate(form))

    labels = json.loads(session.execute(LABELS, {"concept_id": concept_id}).scalar_one())
    summary = ConceptSummary.model_validate(concept)
    return ConceptDetail(
        **summary.model_dump(),
        languages=sorted(languages.values(), key=lambda lang: lang.name_en),
        labels=labels,
    )
