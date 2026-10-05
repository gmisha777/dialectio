"""Languages imported at country level (Stage 1).

`countries` are Natural Earth ADM0_A3 codes where the language is the main/official one.
`lemma_tag` is the Wikidata lemma language tag to use (filters out other scripts).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    wikidata_id: str
    iso639_3: str
    lemma_tag: str
    name_en: str
    name_uk: str
    countries: tuple[str, ...]


LANGUAGES: tuple[Language, ...] = (
    Language("Q8798", "ukr", "uk", "Ukrainian", "українська", ("UKR",)),
    Language(
        "Q1860", "eng", "en", "English", "англійська", ("GBR", "USA", "CAN", "AUS", "NZL", "IRL")
    ),
    Language("Q188", "deu", "de", "German", "німецька", ("DEU", "AUT", "CHE", "LIE")),
    Language("Q150", "fra", "fr", "French", "французька", ("FRA", "BEL", "CHE", "LUX", "MCO")),
    Language(
        "Q1321",
        "spa",
        "es",
        "Spanish",
        "іспанська",
        (
            "ESP",
            "MEX",
            "ARG",
            "COL",
            "PER",
            "VEN",
            "CHL",
            "ECU",
            "GTM",
            "CUB",
            "BOL",
            "DOM",
            "HND",
            "PRY",
            "SLV",
            "NIC",
            "CRI",
            "PAN",
            "URY",
        ),
    ),
    Language("Q652", "ita", "it", "Italian", "італійська", ("ITA", "SMR", "CHE")),
    Language("Q5146", "por", "pt", "Portuguese", "португальська", ("PRT", "BRA", "AGO", "MOZ")),
    Language("Q809", "pol", "pl", "Polish", "польська", ("POL",)),
    Language("Q9056", "ces", "cs", "Czech", "чеська", ("CZE",)),
    Language("Q9058", "slk", "sk", "Slovak", "словацька", ("SVK",)),
    Language("Q9091", "bel", "be", "Belarusian", "білоруська", ("BLR",)),
    Language("Q7737", "rus", "ru", "Russian", "російська", ("RUS",)),
    Language("Q7918", "bul", "bg", "Bulgarian", "болгарська", ("BGR",)),
    Language("Q9299", "srp", "sr", "Serbian", "сербська", ("SRB",)),
    Language("Q6654", "hrv", "hr", "Croatian", "хорватська", ("HRV",)),
    Language("Q9063", "slv", "sl", "Slovene", "словенська", ("SVN",)),
    Language("Q7913", "ron", "ro", "Romanian", "румунська", ("ROU", "MDA")),
    Language("Q9067", "hun", "hu", "Hungarian", "угорська", ("HUN",)),
    Language("Q7411", "nld", "nl", "Dutch", "нідерландська", ("NLD", "BEL")),
    Language("Q9027", "swe", "sv", "Swedish", "шведська", ("SWE",)),
    Language("Q25167", "nob", "nb", "Norwegian Bokmål", "норвезька (букмол)", ("NOR",)),
    Language("Q9035", "dan", "da", "Danish", "данська", ("DNK",)),
    Language("Q1412", "fin", "fi", "Finnish", "фінська", ("FIN",)),
    Language("Q9072", "est", "et", "Estonian", "естонська", ("EST",)),
    Language("Q9078", "lav", "lv", "Latvian", "латиська", ("LVA",)),
    Language("Q9083", "lit", "lt", "Lithuanian", "литовська", ("LTU",)),
    Language("Q36510", "ell", "el", "Greek", "грецька", ("GRC", "CYP")),
    Language("Q256", "tur", "tr", "Turkish", "турецька", ("TUR",)),
    Language("Q8108", "kat", "ka", "Georgian", "грузинська", ("GEO",)),
    Language("Q8785", "hye", "hy", "Armenian", "вірменська", ("ARM",)),
    Language("Q9288", "heb", "he", "Hebrew", "іврит", ("ISR",)),
    Language("Q9168", "fas", "fa", "Persian", "перська", ("IRN",)),
    Language("Q1568", "hin", "hi", "Hindi", "гінді", ("IND",)),
    Language("Q5287", "jpn", "ja", "Japanese", "японська", ("JPN",)),
    Language("Q9176", "kor", "ko", "Korean", "корейська", ("KOR", "PRK")),
)
