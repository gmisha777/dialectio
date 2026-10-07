"""Site-wide numbers and the list of data sources (About and Sources pages)."""

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from app.api.lexicon import SessionDep
from app.models import PUBLIC_STATUSES, Audio, Concept, Form, Source, Variety

router = APIRouter(prefix="/api", tags=["stats"])


class SourceStats(BaseModel):
    name: str
    url: str | None
    license: str
    words: int
    recordings: int


class Stats(BaseModel):
    concepts: int
    languages: int
    dialects: int
    words: int
    recordings: int
    synthetic_recordings: int
    sources: list[SourceStats]


@router.get("/stats")
def get_stats(session: SessionDep) -> Stats:
    public_forms = select(Form.id).where(Form.status.in_(PUBLIC_STATUSES))
    words_by_source = dict(
        session.execute(
            select(Form.source_id, func.count())
            .where(Form.status.in_(PUBLIC_STATUSES))
            .group_by(Form.source_id)
        ).all()
    )
    audio_by_source = dict(
        session.execute(
            select(Audio.source_id, func.count())
            .where(Audio.form_id.in_(public_forms))
            .group_by(Audio.source_id)
        ).all()
    )
    audio_by_kind = dict(
        session.execute(
            select(Audio.is_synthetic, func.count())
            .where(Audio.form_id.in_(public_forms))
            .group_by(Audio.is_synthetic)
        ).all()
    )
    kinds = dict(session.execute(select(Variety.kind, func.count()).group_by(Variety.kind)).all())

    return Stats(
        concepts=session.scalar(select(func.count()).select_from(Concept)) or 0,
        languages=kinds.get("language", 0),
        dialects=kinds.get("dialect", 0),
        words=sum(words_by_source.values()),
        recordings=audio_by_kind.get(False, 0),
        synthetic_recordings=audio_by_kind.get(True, 0),
        sources=[
            SourceStats(
                name=source.name,
                url=source.url,
                license=source.license,
                words=words_by_source.get(source.id, 0),
                recordings=audio_by_source.get(source.id, 0),
            )
            for source in session.scalars(select(Source).order_by(Source.id))
        ],
    )
