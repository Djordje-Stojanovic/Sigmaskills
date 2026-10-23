"""SigmaDeepLook --ask: the question words of each language, in one table (English, German, Serbian/Croatian/Bosnian in Latin letters or Cyrillic).

The operation of a question (count, total, average, highest, lowest, distinct), its "per X" and "which X" parts, its comparisons ("over 100") and
its filler words were an English list. A German or Serbian question got no operation, or the wrong one. The lists are here; the question is folded
first (lower case, no accents, Serbian Cyrillic written in Latin letters, ß -> ss, đ -> dj), so every pattern below is plain ASCII and a question
typed without diacritics matches too. The language is the one whose marker words the question contains most (English when none). Column names are
folded the same way, so a Cyrillic or accented column still matches its question word. Adding a language is one more entry in LANGS.

Stdlib only.
"""
import re
import unicodedata

_CYR = dict(zip("абвгдђежзијклљмнњопрстћуфхцчџш", "a b v g d dj e z z i j k l lj m n nj o p r s t c u f h c c dz s".split()))
_CYR.update({"є": "e", "ї": "i", "ґ": "g", "ё": "e", "ы": "y", "э": "e", "ю": "ju", "я": "ja", "щ": "s", "ь": "", "ъ": ""})   # Ukrainian and Russian letters the Serbian table lacks
_SPECIAL = {"ß": "ss", "đ": "dj", "ø": "o", "ł": "l", "ı": "i", "æ": "ae", "œ": "oe"}


def fold(s):
    """Lower case, no accents, Serbian Cyrillic in Latin letters, ß -> ss, đ -> dj. ASCII text comes back unchanged apart from the case."""
    s = str(s).lower()
    if s.isascii():
        return s
    s = "".join(_CYR.get(c) or _SPECIAL.get(c) or c for c in s)
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


QUOTES = "\"'`\u2018\u2019\u201a\u201b\u201c\u201d\u201e\u201f\u00ab\u00bb\u2039\u203a"
_QUOTED_NUM = re.compile("[" + QUOTES + r"]+\s*(-?\d[\d.]*(?:\s*[,;/]\s*-?\d[\d.]*)*)\s*[" + QUOTES + "]+")


def unquote_numbers(q):
    """A number the question wrote in quotes ("3287", `23`, curly or angle quotes, "336,519") is the same number without them, so the index,
    coordinate and key readers see 3287 and 336,519. Quotes around words are left alone."""
    return _QUOTED_NUM.sub(r" \1 ", q)


LANGS = {
    "en": dict(
        marks="the of is are how what which who many much per by with and in for total average",
        stop="""a an the of in on at to for from by with and or is are was were be been being what which who whom whose how many much does do did
has have had this that these those there it its as per each than then all any me give tell show list find please file document data
table row rows record records entry entries value values field fields column columns sheet i we you they he she my our your their
would could should can will shall about into over under above below more less most least than between during after before when where
number count total sum average mean highest lowest largest smallest biggest maximum minimum max min distinct unique different
combined overall altogether made make makes get got say says said top peak greatest fewest cheapest longest shortest earliest latest first last whole every""",
        ops=[("count", r"\bhow many\b|\bnumber of\b|\bcount\b|\bhow often\b"),
             ("mean", r"\b(average|mean|avg)\b"),
             ("sum", r"\b(total|sum|combined|altogether|overall|how much)\b"),
             ("max", r"\b(highest|largest|biggest|greatest|maximum|max|most expensive|longest|top|peak|most|latest)\b"),
             ("min", r"\b(lowest|smallest|least|minimum|min|cheapest|shortest|fewest|earliest)\b"),
             ("distinct", r"\b(distinct|unique|different)\b")],
        group=r"\b(?:per|by|for each|each)\s+([\w-]+)",
        which=r"\s*(?:which|what|who)\s+([\w-]+)",
        howmany=r"\bhow (?:many|much)\s+(?:of\s+(?:the\s+)?)?([^\W\d_]+)",
        cmp={">": "over|above|more than|greater than|exceeding", ">=": "at least", "<": "under|below|less than|fewer than", "<=": "at most|not more than"},
        first=r"\bfirst\b", last=r"\blast\b",
    ),
    "de": dict(
        marks="der die das den dem ist sind wie viele viel welche welcher welches wer was pro je nach und oder mit von im in wieviele gibt es insgesamt",
        stop="""ein eine einen einem einer eines der die das den dem des und oder ist sind war waren wie was welche welcher welches welchen welchem wer wo wann
viele viel wieviele gibt es hat haben hatte hatten in im am an auf aus bei mit nach von vom zu zum zur fur uber unter pro je bitte mir sag sage zeig zeige
liste finde alle alles jede jeder jedes jedem insgesamt gesamt gesamte gesamten summe anzahl zahl durchschnitt durchschnittlich mittelwert hochste hochster
hochstes hochsten grosste grosster niedrigste niedrigster kleinste kleinster maximale minimale meisten meiste mehr weniger als mindestens hochstens ich wir
sie er dass nicht auch noch nur datei dokument daten tabelle zeile zeilen datensatz datensatze eintrage wert werte spalte spalten blatt erste ersten erster
letzte letzten letzter verschiedene verschiedenen eindeutige unterschiedliche ueber unterschiedlich""",
        ops=[("count", r"\bwie ?viele\b|\banzahl\b|\bzahl der\b|\bwie oft\b|\bzahle\w*"),
             ("mean", r"\bdurchschnitt\w*|\bmittelwert\w*|\bim schnitt\b|\bmittlere\w*"),
             ("sum", r"\b(gesamt\w*|summe|insgesamt|zusammen|wie ?viel)\b"),
             ("max", r"\b((?:hochst|hoechst)(?:e|er|es|en|em)|gro(?:e)?sst\w*|maximal\w*|maximum|meist\w*|teuerst\w*|laengst\w*|langst\w*|neuest\w*|spaetest\w*|spatest\w*|top|spitze)\b"),
             ("min", r"\b(niedrigst\w*|kleinst\w*|geringst\w*|minimal\w*|minimum|wenigst\w*|billigst\w*|kuerzest\w*|kurzest\w*|fruehest\w*|fruhest\w*|aeltest\w*|altest\w*)\b"),
             ("distinct", r"\b(verschieden\w*|eindeutig\w*|einzigartig\w*|unterschiedlich\w*)\b")],
        group=r"\b(?:pro|je|nach|fur jede[rsmn]?|fuer jede[rsmn]?|jede[rsmn]?)\s+([\w-]+)",
        which=r"\s*(?:welche[rsmn]?|wer|was fur (?:ein|eine)|was fuer (?:ein|eine))\s+([\w-]+)",
        howmany=r"\bwie ?(?:viele|viel)\s+([^\W\d_]+)",
        cmp={">": "uber|ueber|mehr als|grosser als|groesser als|oberhalb", ">=": "mindestens|wenigstens|ab", "<": "unter|weniger als|kleiner als|unterhalb",
             "<=": "hochstens|hoechstens|maximal|bis zu|nicht mehr als"},
        first=r"\berste\w*", last=r"\bletzte\w*",
    ),
    "sr": dict(
        marks="koliko je su ima ukupno po za svaki svaka koji koja koje ko sta prosek prosecan najvisi najveci najmanji u od i ili",
        stop="""je su sam smo ste bio bila bilo i ili u na za od do po sa iz kod koji koja koje koga ko sta koliko kako gde kada ima imaju svi sve svaki svaka svako
ukupno ukupan zbir suma sveukupno zajedno prosek prosecan prosecna srednja najvisi najveci najnizi najmanji najvisa najveca najniza najmanja najskuplji
najjeftiniji najduzi najkraci broj redova red redovi zapisa zapis vrednost vrednosti kolona kolone tabela tabele fajl datoteka dokument podaci molim reci
pokazi prikazi nadji lista preko ispod iznad vise manje mi ja ti vi ono to taj ta te mu joj im razlicit razlicitih jedinstven jedinstvenih prvi prva prvo poslednji
poslednja poslednje zadnji maksimalno minimalno""",
        ops=[("count", r"\bkoliko\b|\bbroj\b|\bpreb\w+"),
             ("mean", r"\bprosec\w*|\bprosek\b|\bsrednj\w*"),
             ("sum", r"\b(ukupn\w*|zbir\w*|suma|sveukupno|zajedno)\b"),
             ("max", r"\b(najvis\w*|najvec\w*|maksimaln\w*|maksimum|najskuplj\w*|najduz\w*|najnovij\w*|najcesc\w*|vrh)\b"),
             ("min", r"\b(najniz\w*|najmanj\w*|minimaln\w*|minimum|najjeftinij\w*|najkrac\w*|najstarij\w*)\b"),
             ("distinct", r"\b(razlicit\w*|jedinstven\w*)\b")],
        group=r"\b(?:po|prema|za svak\w+|svak\w+)\s+([\w-]+)",
        which=r"\s*(?:koji|koja|koje|koga|ko)\s+([\w-]+)",
        howmany=r"\bkoliko\s+(?:ima\s+|je\s+)?([^\W\d_]+)",
        cmp={">": "preko|vise od|veci od|veca od|iznad", ">=": "najmanje|barem|bar", "<": "ispod|manje od|manji od|manja od", "<=": "najvise|ne vise od|maksimalno"},
        first=r"\bprv\w+", last=r"\b(?:poslednj\w+|zadnj\w+)",
    ),
}
_NUM = r"([-+]?\d[\d,]*(?:\.\d+)?)"
_CACHE = {}


def detect(folded_question):
    """The language code whose marker words the question holds most; English when none match."""
    ws = set(re.findall(r"[^\W\d_]+", folded_question))
    best, code = 0, "en"
    for c, spec in LANGS.items():
        n = len(ws & set(spec["marks"].split()))
        if n > best:
            best, code = n, c
    return code


def compiled(code):
    """The patterns of one language, compiled once: operations, group, which, how many, comparisons, first, last, stop words."""
    if code not in _CACHE:
        spec = LANGS[code]
        words = {}
        for op, alts in spec["cmp"].items():
            for w in alts.split("|"):
                words[w] = op
        rx = "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
        _CACHE[code] = dict(
            ops=[(n, re.compile(r)) for n, r in spec["ops"]],
            group=re.compile(spec["group"]), which=re.compile(spec["which"]), howmany=re.compile(spec["howmany"]),
            cmp=re.compile(r"\b(" + rx + r")\s+" + _NUM + r"|(>=|<=|>|<|=)\s*" + _NUM), cmpwords=words,
            first=re.compile(spec["first"]), last=re.compile(spec["last"]), stop=set(spec["stop"].split()))
    return _CACHE[code]
