"""SigmaDeepLook word lists per language, in one table (English, German, Serbian/Croatian/Bosnian in Latin letters and Cyrillic).

Speech claims, section turns, stated totals in a PDF and front / back matter of a book used to be English-only word lists, so a German or Serbian
film or document fell back to digits alone. The lists live here; a reader asks for the language it knows (the Whisper language code for speech) and
always gets English too, because numbers, brands and quotes in any language are often English. Adding a language is one more entry in LEX.

Stdlib only.
"""
import re

LEX = {
    "en": dict(
        numw="one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen twenty thirty forty fifty sixty hundred thousand "
             "million billion trillion half double triple",
        units=r"(?:mega|giga|tera|peta|exa|kilo)?(?:watts?|flops?|bytes?)|percent|[- ]?fold|times|dollars?|euros?|years?|tons?|miles?|km\b|meters?|hours?|"
              r"minutes?|cents?|per (?:second|minute|day|year|month)",
        noun=r"[a-z]{4,}s\b",
        ratio=r"-?fold|\btimes\b|spread|\bgap\b|ratio",
        turn="now next finally first second third last",
        partw="part chapter",
        notturn="here we i it you let",
        stated="grand total|sub-?total|total|sum|balance|amount due|amount|net|gross|revenue|income|profit|loss|cost|costs|expenses?|price|average|mean|median|"
               "count|number of|rate|margin|share|percent(?:age)?|growth|tax|vat|fee|budget|salary|ebitda",
        front=r"cover|title( page)?|half[- ]title|copyright|(?:table of )?contents|toc|dedication|epigraph|foreword|preface|praise|also by|other books|"
              r"about this (?:e)?book|front ?matter|imprint|list of (?:figures|tables|illustrations)",
        back=r"acknowledge?ments?|about the authors?|about the publisher|appendix|appendices|glossary|index|notes|endnotes|bibliography|references|colophon|"
             r"afterword|credits|back ?matter|further reading|reading group guide|discussion questions|copyright",
        tail=r"conclusion|epilogue|summary",
    ),
    "de": dict(
        numw="eins zwei drei vier fünf fuenf sechs sieben acht neun zehn elf zwölf zwoelf dreizehn vierzehn fünfzehn zwanzig dreißig dreissig "
             "vierzig fünfzig sechzig hundert tausend million millionen milliarde milliarden billion billionen halb doppelt dreifach",
        units=r"(?:mega|giga|tera|peta|exa|kilo)?(?:watt|flops?|bytes?)|prozent|[- ]?fach|mal|dollar|euro|jahre?n?|tonnen?|meilen?|kilometer|km\b|meter|"
              r"stunden?|minuten?|cents?|pro (?:sekunde|minute|tag|jahr|monat)",
        noun=r"[^\W\d_]{4,}\b",
        ratio=r"-?fach|\bmal\b|abstand|lücke|luecke|verhältnis|verhaeltnis",
        turn="jetzt nun danach dann schließlich schliesslich zuerst erstens zweitens drittens zuletzt",
        partw="teil kapitel",
        notturn="hier wir ich es sie du lass",
        stated="gesamtsumme|zwischensumme|gesamt|summe|saldo|betrag|netto|brutto|umsatz|einkommen|gewinn|verlust|kosten|ausgaben|preis|durchschnitt|"
               "mittelwert|median|anzahl|rate|marge|anteil|prozent|wachstum|steuer|mwst|gebühr|gebuehr|budget|gehalt|ebitda",
        front=r"umschlag|titel(?:seite)?|schmutztitel|impressum|inhalt(?:sverzeichnis)?|widmung|vorwort|geleitwort|einleitung|pressestimmen|vom selben autor|"
              r"abbildungsverzeichnis|tabellenverzeichnis",
        back=r"danksagung|über den autor|ueber den autor|über die autorin|anhang|glossar|register|sachregister|anmerkungen|endnoten|literatur(?:verzeichnis)?|"
             r"quellen(?:verzeichnis)?|nachwort|kolophon|weiterführende literatur|leseprobe",
        tail=r"fazit|schlusswort|schlussbetrachtung|zusammenfassung|epilog",
    ),
    "sr": dict(
        numw="jedan jedna jedno dva dve tri četiri cetiri pet šest sest sedam osam devet deset jedanaest dvanaest trinaest petnaest dvadeset trideset "
             "četrdeset pedeset šezdeset stotinu hiljadu hiljada milion miliona milijardu milijardi pola dvostruko trostruko "
             "један два три четири пет шест седам "
             "осам девет десет двадесет стотину "
             "хиљаду милион милијарду",
        units=r"procenata?|odsto|puta|dolar[a-z]*|evra?|eura|godin[a-z]*|tona|tone|milja|kilometara?|km\b|metara?|sati|sat\b|minuta|minut\b|centi|"
              r"po (?:sekundi|minuti|danu|godini|mesecu)|"
              r"процент[а-я]*|пута|долар[а-я]*|евра|"
              r"годин[а-я]*|тона|километара?|метара?|сати|минута",
        noun=r"[^\W\d_]{4,}\b",
        ratio=r"puta\b|razlika|odnos|jaz\b|пута\b|разлика|однос",
        turn="sada sad zatim potom konačno prvo drugo treće trece poslednje сада затим потом прво друго треће",
        partw="deo poglavlje део поглавље",
        notturn="ovde mi ja to ti hajde овде ми ја то ти",
        stated="ukupno|zbir|saldo|iznos|neto|bruto|prihod|dobit|profit|gubitak|trošak|troskovi|rashodi|cena|prosečan|prosek|medijana|broj|stopa|marža|"
               "udeo|procenat|rast|porez|pdv|naknada|budžet|plata|"
               "укупно|збир|износ|приход|добит|губитак|"
               "цена|просек|број|порез|плата",
        front=r"naslovna strana|naslov|impresum|sadržaj|sadrzaj|posveta|predgovor|uvod|"
              r"насловна страна|импресум|садржај|посвета|предговор",
        back=r"zahvalnica|o autoru|dodatak|rečnik|recnik|indeks|registar|napomene|beleške|beleske|literatura|izvori|pogovor|"
             r"захвалница|о аутору|додатак|речник|индекс|литература|поговор",
        tail=r"zaključak|zakljucak|epilog|закључак|епилог",
    ),
}
ALIASES = {"hr": "sr", "bs": "sr", "sh": "sr", "cnr": "sr", "mk": "sr", "de-at": "de", "de-ch": "de"}
_CACHE = {}


def langs(code):
    """Language codes to use for a Whisper / document language: that language first, English always."""
    c = (code or "en").lower().split("_")[0]
    c = ALIASES.get(c, c)
    return ("en",) if c == "en" or c not in LEX else (c, "en")


def _words(key, codes):
    return [w for c in codes for w in LEX[c][key].split()]


def numw(codes=("en",)):
    return r"(?:" + "|".join(re.escape(w) for w in dict.fromkeys(_words("numw", codes))) + r")"


def units(codes=("en",)):
    nw = numw(codes)
    noun = "(?:" + "|".join(LEX[c]["noun"] for c in codes) + ")"
    return "|".join([LEX[c]["units"] for c in codes] + [r"%|\$|€|\bx\b", r"\d[\d,.]* " + noun, r"\b" + nw + " " + noun])


def ratio(codes=("en",)):
    return "|".join([LEX[c]["ratio"] for c in codes] + [r"\d\s?x\b"])


def turn_re(codes=("en",)):
    one = "|".join(re.escape(w) for w in dict.fromkeys(_words("turn", codes)))
    two = "|".join(re.escape(w) + r"\s\w+" for w in dict.fromkeys(_words("partw", codes)))
    return re.compile(r"^(?:" + one + "|" + two + r")[, :]+((?:\w[\w'-]*\s?){1,4})[,.:;]", re.I)


def not_turn(codes=("en",)):
    return set(_words("notturn", codes))


def cached(kind, codes):
    key = (kind, tuple(codes))
    if key not in _CACHE:
        _CACHE[key] = {"numw": numw, "units": units, "ratio": ratio, "turn": turn_re, "notturn": not_turn}[kind](codes)
    return _CACHE[key]


def stated_re():
    """Words that mark a stated total, in every language (a PDF may mix them): one alternation."""
    return re.compile(r"(?i)\b(" + "|".join(LEX[c]["stated"] for c in LEX) + r")\b")


def front_re():
    return re.compile(r"^\s*(" + "|".join(LEX[c]["front"] for c in LEX) + r")\b", re.I)


def back_re(with_tail=False):
    parts = [LEX[c]["back"] for c in LEX] + ([LEX[c]["tail"] for c in LEX] if with_tail else [])
    return re.compile(r"^\s*(" + "|".join(parts) + r")\b", re.I)


def tail_re():
    """Closing sections that may or may not count as a chapter (conclusion, epilogue, summary)."""
    return re.compile(r"^\s*(" + "|".join(LEX[c]["tail"] for c in LEX) + r")\b", re.I)
