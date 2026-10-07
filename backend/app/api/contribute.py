"""Visitor contributions: "how do you say it where you live?" with an optional recording.

Submissions are stored with status "submitted" and stay hidden until an editor approves
them. Contributors grant Dialectio permission to use and publish the word and recording.
Spam protection: a honeypot field and a per-IP rate limit (kept in memory only).
"""

import time
import uuid
from collections import defaultdict, deque
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.editor import CONTRIBUTOR_SOURCE_NAME
from app.config import MEDIA_DIR, MEDIA_URL_PREFIX
from app.db.session import get_session
from app.importers.common import upsert_source
from app.models import SUBMITTED, Audio, Concept, Variety
from app.models import Form as WordForm

router = APIRouter(prefix="/api", tags=["contribute"])

SessionDep = Annotated[Session, Depends(get_session)]

CONTRIBUTOR_SOURCE_URL = "https://github.com/gmisha777/dialectio"
CONTRIBUTOR_LICENSE = "Contributor permission to Dialectio"

MAX_AUDIO_BYTES = 1_000_000  # ~10 s of compressed speech is well under this
AUDIO_TYPES = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "m4a",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
}
RATE_LIMIT = 10  # submissions per IP ...
RATE_WINDOW_SECONDS = 3600  # ... per hour

_recent: dict[str, deque[float]] = defaultdict(deque)


def check_rate_limit(ip: str) -> None:
    now = time.monotonic()
    window = _recent[ip]
    while window and now - window[0] > RATE_WINDOW_SECONDS:
        window.popleft()
    if len(window) >= RATE_LIMIT:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many submissions")
    window.append(now)


class PublicVariety(BaseModel):
    code: str
    kind: str
    name_en: str
    name_uk: str | None
    parent_code: str | None
    region_codes: list[str]


@router.get("/varieties")
def list_varieties(session: SessionDep) -> list[PublicVariety]:
    """Languages and dialects a visitor can contribute to."""
    varieties = session.scalars(
        select(Variety)
        .where(Variety.kind != "dialect_group")
        .options(selectinload(Variety.parent), selectinload(Variety.regions))
        .order_by(Variety.code)
    )
    return [
        PublicVariety(
            code=v.code,
            kind=v.kind,
            name_en=v.name_en,
            name_uk=v.name_uk,
            parent_code=v.parent.code if v.parent else None,
            region_codes=sorted(r.code for r in v.regions),
        )
        for v in varieties
    ]


@router.post("/contributions", status_code=status.HTTP_201_CREATED)
async def contribute(
    request: Request,
    session: SessionDep,
    concept_id: Annotated[int, Form()],
    variety: Annotated[str, Form(min_length=2, max_length=40)],
    spelling: Annotated[str, Form(min_length=1, max_length=200)],
    consent: Annotated[bool, Form()],
    place: Annotated[str, Form(max_length=200)] = "",
    contributor: Annotated[str, Form(max_length=100)] = "",
    # Honeypot: hidden in the form, so only bots fill it in.
    website: Annotated[str, Form()] = "",
    audio: Annotated[UploadFile | None, File()] = None,
) -> dict[str, str]:
    if website:
        # Pretend success so bots don't learn about the trap.
        return {"status": "received"}
    if not consent:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Consent is required")
    check_rate_limit(request.client.host if request.client else "unknown")

    spelling = spelling.strip()
    if not spelling:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Word is empty")
    concept = session.get(Concept, concept_id)
    target = session.scalar(select(Variety).where(Variety.code == variety))
    if concept is None or target is None or target.kind == "dialect_group":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown concept or variety")

    duplicate = session.scalar(
        select(WordForm.id).where(
            WordForm.concept_id == concept.id,
            WordForm.variety_id == target.id,
            WordForm.spelling == spelling,
        )
    )
    if duplicate is not None:
        # Already known (or sent twice): nothing to review, but no error for the visitor.
        return {"status": "exists"}

    source = upsert_source(
        session, CONTRIBUTOR_SOURCE_NAME, CONTRIBUTOR_SOURCE_URL, CONTRIBUTOR_LICENSE
    )
    form = WordForm(
        concept=concept,
        variety=target,
        spelling=spelling,
        note=place.strip() or None,
        contributor=contributor.strip() or None,
        is_primary=False,
        status=SUBMITTED,
        source=source,
    )

    if audio is not None and audio.filename:
        content_type = (audio.content_type or "").split(";")[0].strip()
        extension = AUDIO_TYPES.get(content_type)
        if extension is None:
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Unsupported audio")
        data = await audio.read(MAX_AUDIO_BYTES + 1)
        if len(data) > MAX_AUDIO_BYTES:
            raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Recording is too long")
        path = f"contrib/{uuid.uuid4().hex}.{extension}"
        (MEDIA_DIR / "contrib").mkdir(parents=True, exist_ok=True)
        (MEDIA_DIR / path).write_bytes(data)
        form.audio.append(
            Audio(
                url=f"{MEDIA_URL_PREFIX}/{path}",
                speaker=contributor.strip() or None,
                is_synthetic=False,
                license=CONTRIBUTOR_LICENSE,
                source=source,
            )
        )

    session.add(form)
    session.commit()
    return {"status": "received"}
