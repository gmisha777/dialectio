"""Core lexical model.

Data is organized around a Concept (a meaning). A Form is how one language variety
expresses that concept; a Variety is a language, dialect group or local dialect
(hierarchical via parent_id) and is spoken in one or more Regions.
"""

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    SmallInteger,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

APPROVED = "approved"
PENDING = "pending"

variety_region = Table(
    "variety_region",
    Base.metadata,
    Column("variety_id", ForeignKey("variety.id", ondelete="CASCADE"), primary_key=True),
    Column("region_id", ForeignKey("region.id", ondelete="CASCADE"), primary_key=True),
)


class Source(Base):
    __tablename__ = "source"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    url: Mapped[str | None] = mapped_column(String(500))
    license: Mapped[str] = mapped_column(String(100))


class Concept(Base):
    __tablename__ = "concept"

    id: Mapped[int] = mapped_column(primary_key=True)
    gloss_en: Mapped[str] = mapped_column(String(200))
    gloss_uk: Mapped[str | None] = mapped_column(String(200))
    description_en: Mapped[str | None] = mapped_column(String(500))
    description_uk: Mapped[str | None] = mapped_column(String(500))
    wikidata_id: Mapped[str | None] = mapped_column(String(20), unique=True)
    # URL path segment of the concept's page, e.g. "water" or "bark-q38681"
    slug: Mapped[str | None] = mapped_column(String(120), unique=True)
    category: Mapped[str | None] = mapped_column(String(50))

    forms: Mapped[list["Form"]] = relationship(back_populates="concept")


class Variety(Base):
    __tablename__ = "variety"

    id: Mapped[int] = mapped_column(primary_key=True)
    name_en: Mapped[str] = mapped_column(String(200))
    name_uk: Mapped[str | None] = mapped_column(String(200))
    # language / dialect_group / dialect
    kind: Mapped[str] = mapped_column(String(20), default="language")
    iso639_3: Mapped[str | None] = mapped_column(String(3), index=True)
    glottocode: Mapped[str | None] = mapped_column(String(8), unique=True)
    wikidata_id: Mapped[str | None] = mapped_column(String(20), unique=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("variety.id"))

    parent: Mapped["Variety | None"] = relationship(remote_side=[id])
    regions: Mapped[list["Region"]] = relationship(
        secondary=variety_region, back_populates="varieties"
    )


class Region(Base):
    __tablename__ = "region"
    __table_args__ = (UniqueConstraint("level", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name_en: Mapped[str] = mapped_column(String(200))
    name_uk: Mapped[str | None] = mapped_column(String(200))
    # country / adm1 / adm2
    level: Mapped[str] = mapped_column(String(10))
    # ISO 3166-1 alpha-3 for countries, geoBoundaries shapeID for subdivisions
    code: Mapped[str] = mapped_column(String(50))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("region.id"))
    geom = mapped_column(Geometry("MULTIPOLYGON", srid=4326, spatial_index=True))
    # Where to put the region's map label (curated by the source, e.g. Natural Earth LABEL_X/Y)
    label_point = mapped_column(Geometry("POINT", srid=4326, spatial_index=False))
    # Label importance, lower = more important (Natural Earth LABELRANK)
    label_rank: Mapped[int | None] = mapped_column(SmallInteger)

    varieties: Mapped[list[Variety]] = relationship(
        secondary=variety_region, back_populates="regions"
    )


class Form(Base):
    __tablename__ = "form"
    __table_args__ = (UniqueConstraint("concept_id", "variety_id", "spelling"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("concept.id"), index=True)
    variety_id: Mapped[int] = mapped_column(ForeignKey("variety.id"), index=True)
    spelling: Mapped[str] = mapped_column(String(200), index=True)
    ipa: Mapped[str | None] = mapped_column(String(200))
    transliteration: Mapped[str | None] = mapped_column(String(200))
    note: Mapped[str | None] = mapped_column(Text)
    # The main word for this concept in this variety; others are synonyms or rarer variants.
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # "approved" forms are public; "pending" ones are drafts waiting for an editor's review.
    status: Mapped[str] = mapped_column(String(10), default=APPROVED, server_default=APPROVED)
    # Id in the source dataset, e.g. a Wikidata lexeme "L2071"
    external_id: Mapped[str | None] = mapped_column(String(50))
    source_id: Mapped[int | None] = mapped_column(ForeignKey("source.id"))

    concept: Mapped[Concept] = relationship(back_populates="forms")
    variety: Mapped[Variety] = relationship()
    source: Mapped[Source | None] = relationship()
    audio: Mapped[list["Audio"]] = relationship(back_populates="form")


class Audio(Base):
    __tablename__ = "audio"
    __table_args__ = (UniqueConstraint("form_id", "url"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    form_id: Mapped[int] = mapped_column(ForeignKey("form.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(500))
    speaker: Mapped[str | None] = mapped_column(String(200))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    license: Mapped[str] = mapped_column(String(100))
    source_id: Mapped[int | None] = mapped_column(ForeignKey("source.id"))

    form: Mapped[Form] = relationship(back_populates="audio")
    source: Mapped[Source | None] = relationship()
