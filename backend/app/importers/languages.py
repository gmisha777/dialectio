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
    Language("Q9299", "srp", "sr", "Serbian", "сербська", ("SRB", "MNE")),
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
    # European languages added later (mostly covered by concept labels, few lexemes)
    Language("Q8748", "sqi", "sq", "Albanian", "албанська", ("ALB",)),
    Language("Q9296", "mkd", "mk", "Macedonian", "македонська", ("MKD",)),
    Language("Q9303", "bos", "bs", "Bosnian", "боснійська", ("BIH",)),
    Language("Q294", "isl", "is", "Icelandic", "ісландська", ("ISL",)),
    Language("Q9142", "gle", "ga", "Irish", "ірландська", ("IRL",)),
    Language("Q9166", "mlt", "mt", "Maltese", "мальтійська", ("MLT",)),
    Language("Q9051", "ltz", "lb", "Luxembourgish", "люксембурзька", ("LUX",)),
    Language("Q7026", "cat", "ca", "Catalan", "каталанська", ("AND",)),
    Language("Q397", "lat", "la", "Latin", "латина", ("VAT",)),
    # Indigenous language of Ukraine; country level until regions (Crimea) are on the map
    Language("Q33357", "crh", "crh", "Crimean Tatar", "кримськотатарська", ("UKR",)),
    # Neighbouring regions
    Language("Q9252", "kaz", "kk", "Kazakh", "казахська", ("KAZ",)),
    Language("Q9292", "aze", "az", "Azerbaijani", "азербайджанська", ("AZE",)),
    Language("Q9264", "uzb", "uz", "Uzbek", "узбецька", ("UZB",)),
    Language("Q9267", "tuk", "tk", "Turkmen", "туркменська", ("TKM",)),
    Language("Q9255", "kir", "ky", "Kyrgyz", "киргизька", ("KGZ",)),
    Language("Q9260", "tgk", "tg", "Tajik", "таджицька", ("TJK",)),
    Language("Q9246", "mon", "mn", "Mongolian", "монгольська", ("MNG",)),
    Language(
        "Q13955",
        "ara",
        "ar",
        "Arabic",
        "арабська",
        tuple(
            "EGY SAU DZA MAR TUN LBY IRQ SYR JOR LBN YEM OMN ARE QAT KWT BHR SDN PSX MRT".split()
        ),
    ),
)
