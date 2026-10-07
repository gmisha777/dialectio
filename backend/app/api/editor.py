"""Word editor: lets trusted editors add forms for concepts (e.g. fill gaps in Ukrainian)
and review draft suggestions (status "pending") before they become public.

Protected by a shared token (settings.editor_token, sent as the X-Editor-Token header).
"""

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import MEDIA_DIR, MEDIA_URL_PREFIX, settings
from app.db.session import get_session
from app.importers.common import upsert_source
from app.models import APPROVED, PENDING, PUBLIC_STATUSES, SUBMITTED, Concept, Form, Variety

EDITOR_SOURCE_NAME = "Dialectio editors"
EDITOR_SOURCE_URL = "https://github.com/gmisha777/dialectio"
# Own data stays closed until the project decides on an open license.
EDITOR_SOURCE_LICENSE = "All rights reserved (Dialectio)"
# Drafts proposed for review (e.g. generated); they become editor words once approved.
SUGGESTION_SOURCE_NAME = "Dialectio suggestions (draft)"
# Visitor submissions (see app.api.contribute)
CONTRIBUTOR_SOURCE_NAME = "Dialectio contributors"
OWN_SOURCES = (EDITOR_SOURCE_NAME, SUGGESTION_SOURCE_NAME, CONTRIBUTOR_SOURCE_NAME)

# Varieties shown as hints next to each concept in the editor (standard Ukrainian first,
# useful when editing dialects)
HINT_LANGUAGES = ("ukr", "eng", "pol", "deu", "rus")


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
    status: str
    source: str | None
    editable: bool
    # Visitor submissions: who sent it, from where, and their recording
    contributor: str | None = None
    place: str | None = None
    audio_urls: list[str] = []


class Submission(BaseModel):
    form: EditorForm
    concept_id: int
    concept_gloss_en: str
    concept_gloss_uk: str | None
    variety_code: str
    variety_name_en: str
    variety_name_uk: str | None


class EditorConcept(BaseModel):
    id: int
    wikidata_id: str | None
    gloss_en: str
    gloss_uk: str | None
    description_en: str | None
    description_uk: str | None
    hints: dict[str, str]
    forms: list[EditorForm]


class EditorVariety(BaseModel):
    code: str
    kind: str
    name_en: str
    name_uk: str | None
    parent_code: str | None


class NewForm(BaseModel):
    concept_id: int
    variety: str = Field(min_length=2, max_length=40)
    spelling: str = Field(min_length=1, max_length=200)
    ipa: str | None = Field(default=None, max_length=200)

    @field_validator("spelling", "ipa")
    @classmethod
    def strip(cls, value: str | None) -> str | None:
        value = value.strip() if value else value
        return value or None


def get_variety(session: Session, code: str) -> Variety:
    variety = session.scalar(select(Variety).where(Variety.code == code))
    if variety is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown variety {code}")
    return variety


def to_editor_form(form: Form) -> EditorForm:
    source = form.source.name if form.source else None
    return EditorForm(
        id=form.id,
        spelling=form.spelling,
        ipa=form.ipa,
        is_primary=form.is_primary,
        status=form.status,
        source=source,
        editable=source in OWN_SOURCES,
        contributor=form.contributor,
        place=form.note if form.status == SUBMITTED else None,
        audio_urls=[a.url for a in form.audio] if form.status == SUBMITTED else [],
    )


def has_approved_primary(session: Session, concept_id: int, variety_id: int) -> bool:
    return (
        session.scalar(
            select(Form.id).where(
                Form.concept_id == concept_id,
                Form.variety_id == variety_id,
                Form.is_primary,
                Form.status == APPROVED,
            )
        )
        is not None
    )


def get_own_form(session: Session, form_id: int) -> Form:
    form = session.get(Form, form_id)
    if form is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Form not found")
    if form.source is None or form.source.name not in OWN_SOURCES:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only editor words and drafts can be changed"
        )
    return form


@router.get("/varieties")
def list_varieties(session: SessionDep) -> list[EditorVariety]:
    """Languages and dialects that can be edited (dialect groups only group dialects)."""
    varieties = session.scalars(
        select(Variety)
        .where(Variety.kind != "dialect_group")
        .options(selectinload(Variety.parent))
        .order_by(Variety.code)
    )
    return [
        EditorVariety(
            code=v.code,
            kind=v.kind,
            name_en=v.name_en,
            name_uk=v.name_uk,
            parent_code=v.parent.code if v.parent else None,
        )
        for v in varieties
    ]


@router.get("/concepts")
def list_concepts(
    session: SessionDep, variety: Annotated[str, Query(min_length=2, max_length=40)] = "ukr"
) -> list[EditorConcept]:
    edited = get_variety(session, variety)
    hint_varieties = {
        v.id: v.code
        for v in session.scalars(select(Variety).where(Variety.code.in_(HINT_LANGUAGES)))
    }
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
            (f for f in concept.forms if f.variety_id == edited.id),
            key=lambda f: (f.status != APPROVED, not f.is_primary, f.spelling),
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
                forms=[to_editor_form(f) for f in forms],
            )
        )
    return result


@router.post("/forms", status_code=status.HTTP_201_CREATED)
def add_form(session: SessionDep, payload: NewForm) -> EditorForm:
    if session.get(Concept, payload.concept_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Concept not found")
    variety = get_variety(session, payload.variety)

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
        # A new word is added next to the existing ones; the main word only changes on
        # request (see set_primary).
        is_primary=not any(f.is_primary and f.status in PUBLIC_STATUSES for f in existing),
        status=APPROVED,
        source=source,
    )
    session.add(form)
    session.commit()
    return to_editor_form(form)


@router.get("/submissions")
def list_submissions(session: SessionDep) -> list[Submission]:
    """Words sent by visitors, waiting for review (oldest first)."""
    forms = session.scalars(
        select(Form)
        .where(Form.status == SUBMITTED)
        .options(
            selectinload(Form.concept),
            selectinload(Form.variety),
            selectinload(Form.source),
            selectinload(Form.audio),
        )
        .order_by(Form.id)
    )
    return [
        Submission(
            form=to_editor_form(f),
            concept_id=f.concept.id,
            concept_gloss_en=f.concept.gloss_en,
            concept_gloss_uk=f.concept.gloss_uk,
            variety_code=f.variety.code,
            variety_name_en=f.variety.name_en,
            variety_name_uk=f.variety.name_uk,
        )
        for f in forms
    ]


@router.post("/forms/{form_id}/approve")
def approve_form(session: SessionDep, form_id: int) -> EditorForm:
    form = get_own_form(session, form_id)
    if form.status not in (PENDING, SUBMITTED):
        raise HTTPException(status.HTTP_409_CONFLICT, "Only drafts and submissions can be approved")
    if form.status == PENDING:
        # A reviewed draft is an editor's word from now on.
        form.source = upsert_source(
            session, EDITOR_SOURCE_NAME, EDITOR_SOURCE_URL, EDITOR_SOURCE_LICENSE
        )
    # Visitor words keep their source (and the visitor's name) for attribution.
    others = session.scalars(
        select(Form).where(
            Form.concept_id == form.concept_id,
            Form.variety_id == form.variety_id,
            Form.id != form.id,
        )
    ).all()
    # An approved word is added as a variant; it only becomes the main word if there is none.
    form.is_primary = not any(o.is_primary and o.status in PUBLIC_STATUSES for o in others)
    form.status = APPROVED
    session.commit()
    return to_editor_form(form)


@router.post("/forms/{form_id}/primary")
def set_primary(session: SessionDep, form_id: int) -> EditorForm:
    """Make this word the main one for its concept and language (others become variants)."""
    form = get_own_form(session, form_id)
    if form.status not in PUBLIC_STATUSES:
        raise HTTPException(status.HTTP_409_CONFLICT, "Approve the submission first")
    others = session.scalars(
        select(Form).where(
            Form.concept_id == form.concept_id,
            Form.variety_id == form.variety_id,
            Form.id != form.id,
        )
    )
    for other in others:
        other.is_primary = False
    form.is_primary = True
    session.commit()
    return to_editor_form(form)


@router.delete("/forms/{form_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_form(session: SessionDep, form_id: int) -> None:
    form = get_own_form(session, form_id)
    was_primary = form.is_primary
    concept_id, variety_id = form.concept_id, form.variety_id
    # Visitors' recordings are our own files; imported audio points elsewhere.
    for audio in form.audio:
        if audio.url.startswith(f"{MEDIA_URL_PREFIX}/contrib/"):
            (MEDIA_DIR / audio.url.removeprefix(f"{MEDIA_URL_PREFIX}/")).unlink(missing_ok=True)
    session.delete(form)
    session.flush()
    if was_primary:
        # Promote another word (oldest id) so the concept keeps a primary form in this language.
        replacement = session.scalars(
            select(Form)
            .where(
                Form.concept_id == concept_id,
                Form.variety_id == variety_id,
                Form.status.in_(PUBLIC_STATUSES),
            )
            .order_by((Form.status == APPROVED).desc(), Form.id)
        ).first()
        if replacement:
            replacement.is_primary = True
    session.commit()
