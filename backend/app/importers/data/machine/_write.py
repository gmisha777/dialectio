"""Helper used while drafting: merge "Q123 word|Q456 word" text into machine/<iso>.json."""

import json
from pathlib import Path

HERE = Path(__file__).parent


def write(iso: str, text: str) -> None:
    pairs = {}
    for item in text.split("|"):
        item = item.strip()
        if not item:
            continue
        qid, word = item.split(" ", 1)
        pairs[qid] = word.strip()
    path = HERE / f"{iso}.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
    else:
        comment = f"Unverified machine-drafted words ({iso}) for concepts without data."
        existing = {"_comment": comment}
    existing.update(pairs)
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(iso, len(existing) - 1)
