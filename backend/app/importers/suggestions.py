"""Load generated words for concepts that have no word in a language.

    uv run python -m app.importers.suggestions [code]            (default: ukr)
        data/suggestions_<code>.json -> drafts (status "pending") reviewed in the editor
    uv run python -m app.importers.suggestions --machine <code> [...]
        data/machine/<code>.json -> public right away, marked unverified ("≈" on the site)

Files map Wikidata items to words: {"<Wikidata item>": "<word>"}. Concepts that already
have any word in that language are skipped, so real data always wins.
"""

import json
import sys

from sqlalchemy import select

from app.api.editor import EDITOR_SOURCE_LICENSE, EDITOR_SOURCE_URL, SUGGESTION_SOURCE_NAME
from app.api.lexicon import MACHINE_SOURCE_NAME
from app.db.session import SessionLocal
from app.importers.common import upsert_source
from app.importers.wikidata_lexemes import DATA_DIR
from app.models import APPROVED, PENDING, Concept, Form, Variety


def main(*args: str) -> None:
    if args and args[0] == "--machine":
        for code in args[1:]:
            load(code, machine=True)
    else:
        load(args[0] if args else "ukr", machine=False)


def load(code: str, machine: bool) -> None:
    path = (
        DATA_DIR / "machine" / f"{code}.json" if machine else DATA_DIR / f"suggestions_{code}.json"
    )
    suggestions: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
    suggestions.pop("_comment", None)

    with SessionLocal() as session:
        variety = session.scalar(select(Variety).where(Variety.code == code))
        if variety is None:
            raise SystemExit(f"Unknown variety {code}")
        source = upsert_source(
            session,
            MACHINE_SOURCE_NAME if machine else SUGGESTION_SOURCE_NAME,
            EDITOR_SOURCE_URL,
            EDITOR_SOURCE_LICENSE,
        )
        concepts = {
            c.wikidata_id: c
            for c in session.scalars(
                select(Concept).where(Concept.wikidata_id.in_(list(suggestions)))
            )
        }
        has_word = set(
            session.scalars(select(Form.concept_id).where(Form.variety_id == variety.id))
        )

        added = skipped = 0
        for qid, word in suggestions.items():
            concept = concepts.get(qid)
            if concept is None:
                print(f"  unknown concept {qid} ({word}), skipped")
                continue
            if concept.id in has_word:
                skipped += 1
                continue
            session.add(
                Form(
                    concept=concept,
                    variety=variety,
                    spelling=word.strip(),
                    # Only concepts without any word in this variety get one, so it's the main word.
                    is_primary=True,
                    status=APPROVED if machine else PENDING,
                    source=source,
                )
            )
            added += 1
        session.commit()

    kind = "unverified machine words" if machine else "draft words for review"
    print(f"{code}: added {added} {kind}, skipped {skipped} concepts that have a word.")


if __name__ == "__main__":
    main(*sys.argv[1:])
