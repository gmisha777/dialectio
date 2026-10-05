from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Source

# Downloaded source files (git-ignored): <repo>/data/raw
RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"


def upsert_source(session: Session, name: str, url: str, license: str) -> Source:
    source = session.scalar(select(Source).where(Source.name == name))
    if source is None:
        source = Source(name=name)
        session.add(source)
    source.url = url
    source.license = license
    session.flush()
    return source
