"""Dialect varieties (Stage 2): Ukrainian dialect groups (наріччя) and dialects (говори).

Territories are approximated by oblasts (ISO 3166-2 codes); an oblast can host several
dialects, e.g. Ivano-Frankivsk: Hutsul, Pokuttia-Bukovyna and Boyko.

Run from backend/ after the regions importers:  uv run python -m app.importers.dialects
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Region, Variety


@dataclass(frozen=True)
class Dialect:
    code: str
    parent: str  # variety code
    kind: str  # "dialect_group" or "dialect"
    name_en: str
    name_uk: str
    regions: tuple[str, ...] = ()


DIALECTS: tuple[Dialect, ...] = (
    # Dialect groups (наріччя); their territory is the union of their dialects'.
    Dialect("ukr-north", "ukr", "dialect_group", "Northern Ukrainian dialects", "північне наріччя"),
    Dialect(
        "ukr-southwest",
        "ukr",
        "dialect_group",
        "South-Western Ukrainian dialects",
        "південно-західне наріччя",
    ),
    Dialect(
        "ukr-southeast",
        "ukr",
        "dialect_group",
        "South-Eastern Ukrainian dialects",
        "південно-східне наріччя",
    ),
    # Northern (Polissian) dialects
    Dialect(
        "ukr-polissia-west",
        "ukr-north",
        "dialect",
        "West Polissian dialect",
        "західнополіський говір",
        ("UA-07", "UA-56"),
    ),
    Dialect(
        "ukr-polissia-central",
        "ukr-north",
        "dialect",
        "Central Polissian dialect",
        "середньополіський говір",
        ("UA-18", "UA-32"),
    ),
    Dialect(
        "ukr-polissia-east",
        "ukr-north",
        "dialect",
        "East Polissian dialect",
        "східнополіський говір",
        ("UA-74", "UA-59"),
    ),
    # South-Western dialects
    Dialect(
        "ukr-volhynian",
        "ukr-southwest",
        "dialect",
        "Volhynian dialect",
        "волинський говір",
        ("UA-07", "UA-56", "UA-68"),
    ),
    Dialect(
        "ukr-podillian",
        "ukr-southwest",
        "dialect",
        "Podillian dialect",
        "подільський говір",
        ("UA-05", "UA-68"),
    ),
    Dialect(
        "ukr-dniester",
        "ukr-southwest",
        "dialect",
        "Dniester dialect",
        "наддністрянський говір",
        ("UA-46", "UA-61"),
    ),
    Dialect(
        "ukr-pokuttia-bukovyna",
        "ukr-southwest",
        "dialect",
        "Pokuttia-Bukovyna dialect",
        "покутсько-буковинський говір",
        ("UA-77", "UA-26"),
    ),
    Dialect(
        "ukr-hutsul",
        "ukr-southwest",
        "dialect",
        "Hutsul dialect",
        "гуцульський говір",
        ("UA-26", "UA-77", "UA-21"),
    ),
    Dialect(
        "ukr-boyko",
        "ukr-southwest",
        "dialect",
        "Boyko dialect",
        "бойківський говір",
        ("UA-46", "UA-26"),
    ),
    Dialect(
        "ukr-transcarpathian",
        "ukr-southwest",
        "dialect",
        "Transcarpathian dialect",
        "закарпатський говір",
        ("UA-21",),
    ),
    # South-Eastern dialects
    Dialect(
        "ukr-middle-dnieper",
        "ukr-southeast",
        "dialect",
        "Middle Dnieper dialect",
        "середньонаддніпрянський говір",
        ("UA-32", "UA-30", "UA-71", "UA-53"),
    ),
    Dialect(
        "ukr-slobozhan",
        "ukr-southeast",
        "dialect",
        "Slobozhan dialect",
        "слобожанський говір",
        ("UA-63", "UA-59", "UA-09"),
    ),
    Dialect(
        "ukr-steppe",
        "ukr-southeast",
        "dialect",
        "Steppe dialect",
        "степовий говір",
        ("UA-51", "UA-48", "UA-65", "UA-23", "UA-12", "UA-14", "UA-35"),
    ),
)


def upsert_dialects(session: Session) -> int:
    regions = {r.code: r for r in session.scalars(select(Region))}
    varieties = {v.code: v for v in session.scalars(select(Variety))}
    for dialect in DIALECTS:  # parents come first in DIALECTS
        variety = varieties.get(dialect.code)
        if variety is None:
            variety = Variety(code=dialect.code)
            session.add(variety)
            varieties[dialect.code] = variety
        variety.name_en = dialect.name_en
        variety.name_uk = dialect.name_uk
        variety.kind = dialect.kind
        variety.iso639_3 = None
        variety.parent = varieties[dialect.parent]
        missing = [code for code in dialect.regions if code not in regions]
        if missing:
            print(f"  warning: no region for {dialect.code}: {missing}")
        variety.regions = [regions[code] for code in dialect.regions if code in regions]
    session.flush()
    return len(DIALECTS)


def main() -> None:
    with SessionLocal() as session:
        count = upsert_dialects(session)
        session.commit()
    print(f"Upserted {count} dialect varieties.")


if __name__ == "__main__":
    main()
