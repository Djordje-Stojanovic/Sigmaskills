"""SigmaDeepLook: proper names in a transcript, with their uncertainty (fix round 5). Stdlib only.

Speech-to-text writes a spelling for every name it hears, and a wrong spelling then reads like a fact. Whisper gives each word a
probability; a name below NAME_LOW is a guess. This module

- marks every such name `Name(?)` in the transcript text people read (transcript.md, the gist), the raw words stay in words.json;
- lists the uncertain names with their times and confidence;
- groups names that sound alike (a phonetic key: c/k/q, ph/f, z/s and doubled letters fold together, vowels after the first
  letter drop, then at most one edit apart) so one spoken name written two ways shows its alternatives, and flags a name spelled
  more than one way even when each spelling was heard with confidence.

It never picks the right spelling: it says which spellings were heard, how sure the model was, and that the audio decides.
"""
import re

NAME_LOW = 0.6
WORD_RE = re.compile(r"[^\W\d_][\w'’.-]*", re.UNICODE)
NOT_NAMES = {"i", "i'm", "i'll", "i've", "i'd", "ok", "okay", "mr", "mrs", "ms", "dr", "tv", "uh", "um"}


def phonetic_key(w):
    """A rough sound key for names: Catherine, Kathryn and Katharine fold together; Jon and John too."""
    s = re.sub(r"[^a-z]", "", w.lower())
    if not s:
        return ""
    for a, b in (("ph", "f"), ("ck", "k"), ("qu", "kw"), ("q", "k"), ("x", "ks"), ("z", "s"), ("c", "k"), ("y", "i"), ("w", "v"),
                 ("th", "t"), ("dt", "t"), ("gh", "g")):
        s = s.replace(a, b)
    head, tail = s[0], re.sub(r"[aeiouh]", "", s[1:])
    s = head + tail
    return re.sub(r"(.)\1+", r"\1", s)


def _near(a, b):
    """At most one insert, delete or change between two keys."""
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = j = d = 0
    while i < len(a) and j < len(b):
        if a[i] == b[j]:
            i += 1
            j += 1
            continue
        d += 1
        if d > 1:
            return False
        if len(a) == len(b):
            i += 1
        j += 1
    return d + (len(b) - j) + (len(a) - i) <= 1


def name_tokens(segs):
    """-> [(segment index, word index, clean word, probability, start)] for words that look like proper names: capitalised inside a
    sentence, or capitalised at a sentence start when the same word also appears capitalised inside a sentence or never in lower case."""
    out, mid_caps, lower = [], set(), set()
    flat = []
    for si, s in enumerate(segs):
        prev_end = True
        for wi, w in enumerate(s.get("words") or []):
            raw = w.get("w", "")
            m = WORD_RE.search(raw)
            if not m:
                prev_end = raw.rstrip().endswith((".", "!", "?"))
                continue
            word = m.group(0).rstrip(".'’-")
            starts = prev_end
            prev_end = raw.rstrip().endswith((".", "!", "?"))
            if not word:
                continue
            if word[:1].isupper():
                flat.append((si, wi, word, w.get("p", 1.0), w.get("s", s.get("start", 0.0)), starts))
                if not starts:
                    mid_caps.add(word)
            else:
                lower.add(word.lower())
    for si, wi, word, p, st, starts in flat:
        if word.lower() in NOT_NAMES or len(word) < 2:
            continue
        if starts and word not in mid_caps and (word.lower() in lower or p >= NAME_LOW):
            continue
        out.append((si, wi, word, p, st))
    return out


def name_report(segs, low=NAME_LOW):
    """-> dict(marked: {segment index: text with uncertain names marked}, uncertain: [entries], variants: [groups])
    entry = (word, start, lowest probability, [(other spelling, start, probability)], (start, probability) of the same spelling heard clearly or None)."""
    toks = name_tokens(segs)
    groups = []   # [key, {spelling: [(start, p)]}]
    for _, _, word, p, st in toks:
        k = phonetic_key(word)
        g = next((g for g in groups if _near(g[0], k) and (len(k) >= 3 or g[0] == k)), None)
        if g is None:
            g = [k, {}]
            groups.append(g)
        g[1].setdefault(word, []).append((st, p))
    marked = {}
    unc = []
    low_at = {(si, wi) for si, wi, _, p, _ in toks if p < low}
    for si, s in enumerate(segs):
        ws = s.get("words") or []
        if any((si, wi) in low_at for wi in range(len(ws))):
            parts = []
            for wi, w in enumerate(ws):
                t = w.get("w", "").strip()
                if (si, wi) in low_at:
                    t = re.sub(r"([^\W\d_][\w'’-]*)", r"\1(?)", t, count=1)
                parts.append(t)
            marked[si] = " ".join(parts)
    seen = set()
    for si, wi, word, p, st in toks:
        if p >= low or word in seen:
            continue
        seen.add(word)
        g = next(g for g in groups if word in g[1])
        alts = [(o, occ[0][0], max(q for _, q in occ)) for o, occ in g[1].items() if o != word]
        same = [(t, q) for t, q in g[1][word] if q >= low]
        unc.append((word, st, min(q for _, q in g[1][word]), alts, max(same, key=lambda x: x[1]) if same else None))
    variants = [g[1] for g in groups if len(g[1]) > 1]
    return {"marked": marked, "uncertain": unc, "variants": variants}


def report(look, segs, mmss):
    """Print the names lines; -> {segment index: marked text} for the transcript writer."""
    r = name_report(segs)
    if r["uncertain"]:
        parts = []
        for word, st, p, alts, same in r["uncertain"][:25]:
            s = f"{word}(?) at {mmss(st)} (confidence {p:.2f})"
            if same:
                s += f", the same spelling heard clearly at {mmss(same[0])} ({same[1]:.2f})"
            if alts:
                s += "; also written " + ", ".join(f"{o} at {mmss(t)} ({q:.2f})" for o, t, q in alts[:3])
            parts.append(s)
        look.fact("uncertain_names", [{"heard": w, "at": round(st, 2), "p": round(p, 2), "alternatives": [o for o, _, _ in a]} for w, st, p, a, _ in r["uncertain"][:100]])
        look.line(f"Names heard with low confidence ({len(r['uncertain'])}; the spelling is the speech model's guess, not a fact: confirm by ear or from a written source; "
                  f"alternatives are similar-sounding spellings elsewhere in this transcript): " + "; ".join(parts)
                  + (f"; +{len(r['uncertain']) - 25} more" if len(r["uncertain"]) > 25 else ""), 90, "names")
    for g in r["variants"][:5]:
        sp = sorted(g.items(), key=lambda kv: -len(kv[1]))
        look.flag("NAME-SPELLING", ", ".join(f"{w} x{len(o)}" for w, o in sp), "one spoken name may be written " + str(len(sp)) + " ways",
                  "the audio decides the spelling; quote it with (?) until checked")
    return r["marked"]
