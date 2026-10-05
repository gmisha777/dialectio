"""Word editor: lets trusted editors add forms for concepts (e.g. fill gaps in Ukrainian).

Protected by a shared token (settings.editor_token, sent as the X-Editor-Token header).
"""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.db.session import get_session
from app.importers.common import upsert_source
from app.models import Concept, Form, Source, Variety

EDITOR_SOURCE_NAME = "Dialectio editors"
EDITOR_SOURCE_URL = "https://github.com/gmisha777/dialectio"
# Own data stays closed until the project decides on an open license.
EDITOR_SOURCE_LICENSE = "All rights reserved (Dialectio)"

# Languages shown as hints next to each concept in the editor
HINT_LANGUAGES = ("eng", "pol", "deu", "rus")


def require_editor(x_editor_token: Annotated[str | None, Header()] = None) -> None:
    if not settings.editor_token:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Editing is disabled")
    if not x_editor_token or not secrets.compare_digest(x_editor_token, settings.editor_token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid editor token")


router = APIRouter(prefix="/api/editor", tags=["editor"], dependencies=[Depends(require_editor)])

SessionDep = Annotated[Session, Depends(get_session)]


class EditorForm(BaseModel):
    id: int
    spelling: str
    ipa: str | None
    is_primary: bool
    source: str | None
    editable: bool


class EditorConcept(BaseModel):
    id: int
    wikidata_id: str | None
    gloss_en: str
    gloss_uk: str | None
    description_en: str | None
    description_uk: str | None
    hints: dict[str, str]
    forms: list[EditorForm]


class NewForm(BaseModel):
    concept_id: int
    iso639_3: str = Field(min_length=3, max_length=3)
    spelling: str = Field(min_length=1, max_length=200)
    ipa: str | None = Field(default=None, max_length=200)

    @field_validator("spelling", "ipa")
    @classmethod
    def strip(cls, value: str | None) -> str | None:
        value = value.strip() if value else value
        return value or None


def get_variety(session: Session, iso639_3: str) -> Variety:
    variety = session.scalar(select(Variety).where(Variety.iso639_3 == iso639_3))
    if variety is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown language {iso639_3}")
    return variety


def to_editor_form(form: Form, editor_source_id: int | None) -> EditorForm:
    return EditorForm(
        id=form.id,
        spelling=form.spelling,
        ipa=form.ipa,
        is_primary=form.is_primary,
        source=form.source.name if form.source else None,
        editable=form.source_id is not None and form.source_id == editor_source_id,
    )


def editor_source_id(session: Session) -> int | None:
    return session.scalar(select(Source.id).where(Source.name == EDITOR_SOURCE_NAME))


@router.get("/concepts")
def list_concepts(
    session: SessionDep, lang: Annotated[str, Query(min_length=3, max_length=3)] = "ukr"
) -> list[EditorConcept]:
    variety = get_variety(session, lang)
    hint_varieties = {
        v.id: v.iso639_3
        for v in session.scalars(select(Variety).where(Variety.iso639_3.in_(HINT_LANGUAGES)))
    }
    own_source = editor_source_id(session)
    concepts = session.scalars(
        select(Concept)
        .options(selectinload(Concept.forms).selectinload(Form.source))
        .order_by(Concept.gloss_en)
    ).all()

    result = []
    for concept in concepts:
        primary = {
            hint_varieties[f.variety_id]: f.spelling
            for f in concept.forms
            if f.is_primary and f.variety_id in hint_varieties
        }
        hints = {lang: primary[lang] for lang in HINT_LANGUAGES if lang in primary}
        forms = sorted(
            (f for f in concept.forms if f.variety_id == variety.id),
            key=lambda f: (not f.is_primary, f.spelling),
        )
        result.append(
            EditorConcept(
                id=concept.id,
                wikidata_id=concept.wikidata_id,
                gloss_en=concept.gloss_en,
                gloss_uk=concept.gloss_uk,
                description_en=concept.description_en,
                description_uk=concept.description_uk,
                hints=hints,
                forms=[to_editor_form(f, own_source) for f in forms],
            )
        )
    return result


@router.post("/forms", status_code=status.HTTP_201_CREATED)
def add_form(session: SessionDep, payload: NewForm) -> EditorForm:
    if session.get(Concept, payload.concept_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Concept not found")
    variety = get_variety(session, payload.iso639_3)

    existing = session.scalars(
        select(Form).where(Form.concept_id == payload.concept_id, Form.variety_id == variety.id)
    ).all()
    if any(f.spelling == payload.spelling for f in existing):
        raise HTTPException(status.HTTP_409_CONFLICT, "This word already exists")

    source = upsert_source(session, EDITOR_SOURCE_NAME, EDITOR_SOURCE_URL, EDITOR_SOURCE_LICENSE)
    form = Form(
        concept_id=payload.concept_id,
        variety=variety,
        spelling=payload.spelling,
        ipa=payload.ipa,
        is_primary=not any(f.is_primary for f in existing),
        source=source,
    )
    session.add(form)
    session.commit()
    return to_editor_form(form, source.id)


@router.delete("/forms/{form_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_form(session: SessionDep, form_id: int) -> None:
    form = session.get(Form, form_id)
    if form is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Form not found")
    if form.source_id is None or form.source_id != editor_source_id(session):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only editor-added words can be deleted")

    was_primary = form.is_primary
    concept_id, variety_id = form.concept_id, form.variety_id
    session.delete(form)
    session.flush()
    if was_primary:
        # Promote another word (oldest id) so the concept keeps a primary form in this language.
        replacement = session.scalars(
            select(Form)
            .where(Form.concept_id == concept_id, Form.variety_id == variety_id)
            .order_by(Form.id)
        ).first()
        if replacement:
            replacement.is_primary = True
    session.commit()
