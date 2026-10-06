from app.importers.wikidata_lexemes import Lexeme, english_gloss, pick_primary


def lexeme(lid: str, lemma: str, audio: bool = False, ipa: bool = False) -> Lexeme:
    return Lexeme(lid, lemma, ipas=["x"] if ipa else [], audio_files=["a.ogg"] if audio else [])


def test_primary_prefers_word_matching_the_concept_label_over_slang_with_audio() -> None:
    slang = lexeme("L100", "тыква", audio=True)
    standard = lexeme("L200", "голова")
    assert pick_primary([slang, standard], "голова") is standard


def test_primary_accepts_a_word_of_a_longer_label() -> None:
    other = lexeme("L1", "собака", audio=True)
    dog = lexeme("L2", "пес")
    assert pick_primary([other, dog], "пес свійський") is dog


def test_primary_without_label_falls_back_to_audio_ipa_then_oldest() -> None:
    old = lexeme("L1", "a")
    with_ipa = lexeme("L2", "b", ipa=True)
    with_audio = lexeme("L3", "c", audio=True)
    assert pick_primary([old, with_ipa, with_audio]) is with_audio
    assert pick_primary([old, with_ipa]) is with_ipa
    assert pick_primary([lexeme("L9", "x"), old]) is old


def test_english_gloss_replaces_latin_taxon_names() -> None:
    assert english_gloss("Camelus", "camel") == "camel"
    assert english_gloss("January", "January") == "January"
    assert english_gloss("church building", "church") == "church building"
    assert english_gloss(None, "one") == "one"


def test_primary_never_prefers_a_styled_sense() -> None:
    slang = lexeme("L1", "бубен", audio=True)
    slang.styled_for.add("Q37017")
    plain = lexeme("L2", "лицо")
    assert pick_primary([slang, plain], "лицо", "Q37017") is plain
    assert pick_primary([slang, lexeme("L3", "морда")], None, "Q37017").lemma == "морда"


def test_primary_matches_inflected_label() -> None:
    fish = lexeme("L1", "риба")
    assert pick_primary([lexeme("L0", "карась", audio=True), fish], "риби") is fish


def test_label_wins_when_no_lexeme_resembles_it() -> None:
    assert (
        pick_primary([lexeme("L1", "бабло", audio=True), lexeme("L2", "капуста")], "деньги") is None
    )
    # multi-word labels are not used as words
    assert pick_primary([lexeme("L1", "cop")], "police officer").lemma == "cop"
