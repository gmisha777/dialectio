"""Generate synthetic pronunciations (TTS) for words that have no recorded audio.

Uses Piper (https://github.com/OHF-Voice/piper1-gpl) as an external program: install it once
as an isolated tool with `uv tool install piper-tts` (Piper is GPL; it is only run as a
separate process and is not part of this codebase). Only voices whose license allows
commercial use are configured below. Audio is saved as MP3 under data/media/tts and marked
is_synthetic.

Run from backend/ (after every Wikidata import, which recreates forms):
    uv run python -m app.importers.tts [iso639_3 ...]
"""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

import httpx2
import lameenc
from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session

from app.config import MEDIA_DIR, MEDIA_URL_PREFIX
from app.db.session import SessionLocal
from app.importers.common import RAW_DIR, upsert_source
from app.models import APPROVED, Audio, Form, Variety

VOICES_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
VOICE_DIR = RAW_DIR / "piper"
SOURCE_NAME = "Piper TTS"
SOURCE_URL = "https://github.com/OHF-Voice/piper1-gpl"
MP3_BITRATE_KBPS = 48


@dataclass(frozen=True)
class Voice:
    key: str  # e.g. "uk_UA-ukrainian_tts-medium"
    license: str

    @property
    def path(self) -> str:
        lang, name, quality = self.key.split("-")
        return f"{lang.split('_')[0]}/{lang}/{name}/{quality}/{self.key}"

    @property
    def name(self) -> str:
        return self.key.split("-")[1]


# One voice per language, chosen among voices whose model card states a license that allows
# commercial use (CC0, public domain, CC BY 4.0). Languages without such a voice are absent.
# Lithuanian (lt_LT-reginute1, CC BY 4.0) needs a custom phonemizer Piper 1.8 doesn't have.
VOICES: dict[str, Voice] = {
    "ukr": Voice("uk_UA-ukrainian_tts-medium", "CC0"),
    "eng": Voice("en_GB-cori-medium", "Public domain"),
    "deu": Voice("de_DE-thorsten-medium", "CC0"),
    "fra": Voice("fr_FR-siwis-medium", "CC BY 4.0"),
    "spa": Voice("es_ES-davefx-medium", "CC0"),
    "ita": Voice("it_IT-serena-medium", "CC BY 4.0"),
    "por": Voice("pt_BR-cadu-medium", "CC0"),
    "pol": Voice("pl_PL-gosia-medium", "CC0"),
    "ces": Voice("cs_CZ-jirka-medium", "CC0"),
    "slk": Voice("sk_SK-lili-medium", "CC0"),
    "rus": Voice("ru_RU-denis-medium", "CC0"),
    "bul": Voice("bg_BG-dimitar-medium", "CC0"),
    "slv": Voice("sl_SI-artur-medium", "CC BY 4.0"),
    "ron": Voice("ro_RO-mihai-medium", "CC0"),
    "hun": Voice("hu_HU-anna-medium", "CC0"),
    "nld": Voice("nl_NL-pim-medium", "CC0"),
    "swe": Voice("sv_SE-nst-medium", "CC0"),
    "nob": Voice("no_NO-talesyntese-medium", "CC0"),
    "dan": Voice("da_DK-talesyntese-medium", "CC0"),
    "fin": Voice("fi_FI-harri-medium", "CC0"),
    "est": Voice("et_EE-news-medium", "CC BY 4.0"),
    "lav": Voice("lv_LV-aivars-medium", "CC0"),
    "ell": Voice("el_GR-rapunzelina-medium", "CC0"),
    "fas": Voice("fa_IR-amir-medium", "CC0"),
}


def piper_executable() -> str:
    found = shutil.which("piper") or str(Path.home() / ".local" / "bin" / "piper.exe")
    if not Path(found).exists():
        raise SystemExit("Piper not found: install it with `uv tool install piper-tts`")
    return found


def download_voice(voice: Voice) -> Path:
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    model = VOICE_DIR / f"{voice.key}.onnx"
    for suffix in (".onnx", ".onnx.json"):
        target = VOICE_DIR / f"{voice.key}{suffix}"
        if target.exists():
            continue
        print(f"  downloading {target.name} ...")
        with httpx2.stream(
            "GET", f"{VOICES_URL}/{voice.path}{suffix}", follow_redirects=True, timeout=300
        ) as response:
            response.raise_for_status()
            partial = target.with_suffix(target.suffix + ".part")
            with partial.open("wb") as out:
                for chunk in response.iter_bytes():
                    out.write(chunk)
            partial.replace(target)
    return model


def speech_text(spelling: str) -> str:
    # Some voices only know lowercase letters; pronunciation does not depend on case.
    return spelling.strip().lower()


def media_path(iso639_3: str, voice: Voice, text: str) -> Path:
    # Content-addressed, so re-running (e.g. after a re-import) reuses existing files.
    digest = hashlib.sha1(f"{voice.key}\n{text}".encode()).hexdigest()[:20]
    return Path("tts") / iso639_3 / f"{digest}.mp3"


def wav_to_mp3(wav_path: Path) -> bytes:
    with wave.open(str(wav_path)) as wav:
        encoder = lameenc.Encoder()
        encoder.set_bit_rate(MP3_BITRATE_KBPS)
        encoder.set_in_sample_rate(wav.getframerate())
        encoder.set_channels(wav.getnchannels())
        encoder.set_quality(2)
        frames = wav.readframes(wav.getnframes())
    return encoder.encode(frames) + encoder.flush()


def synthesize(voice: Voice, model: Path, texts: list[str], targets: dict[str, Path]) -> None:
    """Run Piper once for all texts of a language and store each result as MP3."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        (tmp_dir / "input.txt").write_text("\n".join(texts) + "\n", encoding="utf-8")
        out_dir = tmp_dir / "wav"
        out_dir.mkdir()
        subprocess.run(
            [
                piper_executable(),
                "-m",
                str(model),
                "-i",
                str(tmp_dir / "input.txt"),
                "--output-dir",
                str(out_dir),
                "--output-dir-naming",
                "text",
            ],
            check=True,
            capture_output=True,
            # Piper reads the input file with Python's default encoding; force UTF-8 (Windows).
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        for text in texts:
            wav_path = out_dir / f"{text}.wav"
            if not wav_path.exists():
                print(f"  warning: no audio produced for {text!r}")
                continue
            target = MEDIA_DIR / targets[text]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(wav_to_mp3(wav_path))


def forms_needing_audio(session: Session, variety_id: int) -> list[Form]:
    """Approved primary forms without a recorded (non-synthetic) pronunciation."""
    recorded = exists().where(Audio.form_id == Form.id, Audio.is_synthetic.is_(False))
    return list(
        session.scalars(
            select(Form).where(
                Form.variety_id == variety_id,
                Form.is_primary,
                Form.status == APPROVED,
                ~recorded,
            )
        )
    )


def generate(session: Session, iso639_3: str) -> int:
    voice = VOICES[iso639_3]
    variety = session.scalar(select(Variety).where(Variety.iso639_3 == iso639_3))
    if variety is None:
        return 0
    forms = forms_needing_audio(session, variety.id)
    if not forms:
        return 0

    targets = {
        speech_text(f.spelling): media_path(iso639_3, voice, speech_text(f.spelling)) for f in forms
    }
    missing = sorted(t for t, path in targets.items() if not (MEDIA_DIR / path).exists())
    if missing:
        model = download_voice(voice)
        print(f"  synthesizing {len(missing)} words ...")
        synthesize(voice, model, missing, targets)

    source = upsert_source(session, SOURCE_NAME, SOURCE_URL, "Per voice (see audio)")
    form_ids = [f.id for f in forms]
    session.execute(delete(Audio).where(Audio.form_id.in_(form_ids), Audio.is_synthetic))
    added = 0
    for form in forms:
        path = targets[speech_text(form.spelling)]
        if not (MEDIA_DIR / path).exists():
            continue
        session.add(
            Audio(
                form=form,
                url=f"{MEDIA_URL_PREFIX}/{path.as_posix()}",
                speaker=f"Piper voice “{voice.name}”",
                is_synthetic=True,
                license=f"Synthetic; voice {voice.license}",
                source=source,
            )
        )
        added += 1
    session.commit()
    return added


def main(*languages: str) -> None:
    selected = languages or tuple(VOICES)
    unknown = [lang for lang in selected if lang not in VOICES]
    if unknown:
        raise SystemExit(f"No TTS voice configured for: {', '.join(unknown)}")
    total = 0
    with SessionLocal() as session:
        for iso639_3 in selected:
            print(f"{iso639_3} ({VOICES[iso639_3].key}):")
            try:
                added = generate(session, iso639_3)
            except subprocess.CalledProcessError as error:
                session.rollback()
                stderr = error.stderr.decode("utf-8", "replace").strip().splitlines()
                print(f"  error: Piper failed: {stderr[-1] if stderr else error}")
                continue
            print(f"  {added} words have synthetic audio")
            total += added
    print(f"Done: {total} synthetic pronunciations.")


if __name__ == "__main__":
    main(*sys.argv[1:])
