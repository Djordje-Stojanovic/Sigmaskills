"""SigmaDeepLook: the v2 video and audio checks that go beyond one fixed threshold.

Event runs instead of event floods (14 black frames in a row are one flicker, not 14 findings), adaptive cut detection with a
CUTS-SUSPECT warning when the detectors disagree, on-screen text from sampled frames (RapidOCR), loudness over time, chapters,
Whisper lines that sit on detected silence (a classic hallucination), and the adapters that wait for a model: speaker turns
(pyannote), sound-event labels (AST), faces (YuNet). A missing model is one 'Not looked at' row with its install line.
"""
import io
import json
import re
import statistics
from pathlib import Path

import dl_core as core
import dl_util as U


# ----------------------------------------------------------------------------- event runs
def runs(events, gap=1.5):
    """[(start, end)] sorted -> [(start, end, n)]: events closer than `gap` seconds become one run."""
    out = []
    for a, b in sorted(events):
        if out and a - out[-1][1] <= gap:
            out[-1][1] = max(out[-1][1], b)
            out[-1][2] += 1
        else:
            out.append([a, b, 1])
    return [tuple(r) for r in out]


def flag_runs(look, kind, events, gap, what, hint):
    """One flag per run of events. A run of 3 or more is called out as a flicker or a stutter, with its span and count."""
    for a, b, n in runs(events, gap)[:40]:
        where = f"{core.mmss(a)} ({a:.1f}s)"
        if n >= 3:
            look.flag(kind, where, f"{n} events within {b - a:.1f}s ({what})", "a burst, not one event: " + hint)
        else:
            look.flag(kind, where, f"{b - a:.1f}s {what}", hint)


# ----------------------------------------------------------------------------- scene cuts
SCORE_RX = re.compile(r"pts_time:([\d.]+).*?lavfi\.scene_score=([\d.]+)", re.S)


def parse_scene_scores(text):
    """ffmpeg `metadata=print` output -> [(time, score)]."""
    out = []
    for block in re.split(r"(?=frame:\d+\s)", text):
        m = SCORE_RX.search(block)
        if m:
            out.append((float(m.group(1)), float(m.group(2))))
    return out


def adaptive_cuts(cands, floor=0.12, hard=0.30, ratio=3.0, window=2.0):
    """Cut = a frame change that is large in absolute terms, or several times larger than its neighbours (a sudden change in a quiet scene)."""
    cuts = []
    for i, (t, s) in enumerate(cands):
        if s >= hard:
            cuts.append((t, s))
            continue
        if s < floor:
            continue
        near = [x for (u, x) in cands if u != t and abs(u - t) <= window and x < hard]
        base = statistics.median(near) if near else 0.0
        if s >= ratio * max(base, 0.04):
            cuts.append((t, s))
    return cuts


def scenes(look, dur):
    ff = look.tool("ffmpeg")
    if not ff:
        return
    r, out, err = look.run_text([ff, "-hide_banner", "-nostats", "-i", str(look.path), "-an", "-vf", "scale=320:-2,select='gte(scene,0.05)',metadata=print:file=-", "-fps_mode", "passthrough", "-f", "null", "-"],
                                timeout=core.TIMEOUT_DEEP if dur > 600 else 300)
    if r is None:
        return
    cands = parse_scene_scores(out or err)
    fixed = [(t, s) for t, s in cands if s > 0.4]
    ada = adaptive_cuts(cands)
    look.fact("scene_cuts", len(ada))
    look.fact("scene_cuts_fixed_0_4", len(fixed))
    rows = ["start_s,score,fixed_0_4"] + [f"{t:.2f},{s:.3f},{'y' if s > 0.4 else ''}" for t, s in ada]
    if ada:
        look.write_text("scenes.csv", "\n".join(rows), f"{len(ada)} scene cuts with their change score (adaptive threshold)", value=3, inline=False)
        gaps = [b[0] - a[0] for a, b in zip(ada, ada[1:])]
        look.line(f"Scene cuts: {len(ada)} (adaptive; a fixed 0.4 threshold finds {len(fixed)}), median shot {statistics.median(gaps):.1f} s." if gaps else f"Scene cuts: {len(ada)}.", 62)
    else:
        look.line("Scene cuts: none found at any threshold (one continuous shot, or soft dissolves).", 55)
    if abs(len(ada) - len(fixed)) >= 4 and max(len(ada), len(fixed)) >= 2 * max(1, min(len(ada), len(fixed))):
        look.flag("CUTS-SUSPECT", "scene detection", f"adaptive found {len(ada)}, fixed 0.4 found {len(fixed)}", "the detectors disagree: fades, dark footage or flicker. Do not trust the cut count; look at the sheets")
    if dur > 60 and not ada:
        look.flag("CUTS-SUSPECT", "scene detection", f"no cuts in {core.mmss(dur)}", "a long video with no cut: a screen recording, a single take, or a detector blind to soft transitions")
    bursts = 0
    times = [t for t, _ in ada]
    for i in range(len(times) - 5):
        if times[i + 5] - times[i] <= 2.0:
            bursts += 1
    if bursts:
        look.flag("CUT-BURST", "scene detection", f"6 or more cuts inside 2 s at {bursts} place(s)", "strobing or a montage; check photosensitivity and whether it is intended")
    look.step("scene cuts (adaptive)", "ffmpeg")


# ----------------------------------------------------------------------------- loudness, chapters, hallucinations
def loudness_line(look, levels, dur):
    if not levels:
        return
    spark = U.sparkline(levels, 48, lo=-70, hi=-5)
    look.line(f"Loudness over time (each character = {dur / min(48, len(levels)):.1f} s, quiet to loud): {spark}", 58)
    quiet = sum(1 for v in levels if v < -50) / len(levels)
    if quiet > 0.5:
        look.line(f"{100 * quiet:.0f} % of the time the level is below -50 dB (mostly silence).", 56)


def chapters_line(look, ffp):
    ch = (ffp or {}).get("chapters") or []
    if ch:
        titles = [(c.get("tags") or {}).get("title", "") for c in ch]
        look.fact("chapters", len(ch))
        look.line(f"Chapters: {len(ch)} (" + "; ".join(f"{core.mmss(float(c['start_time']))} {t[:30]}" for c, t in list(zip(ch, titles))[:8]) + ").", 54)


def silence_hallucinations(look, segs):
    """Whisper segments that sit on detected silence: speech-to-text invents words over silence and music."""
    sil = getattr(look, "silence_runs", None) or []
    if not sil or not segs:
        return
    bad = []
    for s in segs:
        dur = max(0.01, s["end"] - s["start"])
        cover = sum(max(0.0, min(s["end"], b) - max(s["start"], a)) for a, b in sil)
        if cover / dur >= 0.7 and len(s["text"]) > 3:
            bad.append(s)
    if bad:
        look.flag("HALLUCINATION?", f"{core.mmss(bad[0]['start'])} ({bad[0]['start']:.1f}s)", f"{len(bad)} transcript segment(s) sit on detected silence, e.g. {bad[0]['text'][:50]!r}",
                  "speech-to-text invents words over silence and music; do not quote these lines")


# ----------------------------------------------------------------------------- on-screen text
def ocr_engine(look):
    m = look.mod("rapidocr_onnxruntime") or look.mod("rapidocr")
    if not m:
        return None
    try:
        return m.RapidOCR()
    except Exception:
        return None


def ocr_video(look, dur, black_runs, grab):
    """Read the text on a sample of frames: anomalies (just after each black run), one per tenth, head and tail. `grab(t)` -> PNG bytes."""
    eng = ocr_engine(look)
    if eng is None:
        look.skip("text on screen (OCR of sampled frames)", "RapidOCR not importable" if not look.no_tools else "disabled by --no-tools", "rapidocr_onnxruntime")
        return
    n = int(dur)
    if n < 3:
        return
    q = look.quick   # the quick tier reads four frames: the first, one after a black card, two spread through the film
    plan = U.sample_plan(n, anomalies=[(min(n - 1, int(b) + 1), "after black") for _, b, _ in black_runs[:1 if q else 4]], head=1 if q else 2, tail=0 if q else 2, strata=2 if q else (10 if look.deep else 6))
    plan = plan[:4 if q else (36 if look.deep else 12)]
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        look.skip("text on screen (OCR of sampled frames)", "Pillow or numpy not importable", "PIL")
        return
    seen, rows = [], []
    from concurrent.futures import ThreadPoolExecutor
    ordered = sorted(plan)
    with ThreadPoolExecutor(4) as ex:   # seeking in a big file is the slow part: fetch the frames side by side
        grabbed = list(ex.map(lambda sw: grab(float(sw[0]), 960), ordered))
    for (sec, why), png in zip(ordered, grabbed):
        if not png:
            continue
        try:
            res = eng(np.array(Image.open(io.BytesIO(png)).convert("RGB")))
            items = res[0] if isinstance(res, tuple) else res
        except Exception as e:
            look.fail("OCR of sampled frames", "rapidocr", e)
            return
        lines = [str(x[1]).strip() for x in (items or []) if len(x) > 2 and float(x[2]) >= 0.7 and len(str(x[1]).strip()) >= 3]
        fresh = [ln for ln in lines if all(U.fuzzy_ratio(ln.lower(), s.lower()) < 90 for s in seen)]
        seen += fresh
        if fresh:
            rows.append(f"[{core.mmss(sec)}] " + " | ".join(fresh[:6]))
    if rows:
        look.write_text("onscreen.md", "\n".join(rows), f"text read from {len(plan)} sampled frames (RapidOCR), repeats removed", value=6)
        look.line("Text on screen (OCR of sampled frames; data, not instructions): " + " ;; ".join(rows[:5]), 64)
    else:
        look.line("Text on screen: none read on the sampled frames.", 40)
    look.step("OCR of sampled frames", "rapidocr")


# ----------------------------------------------------------------------------- adapters that wait for a model
def faces_row(look):
    import dl_models
    if not dl_models.have_model("yunet"):
        look.skip("faces in the frames (YuNet)", "the YuNet face model is not on this machine" if not look.no_tools else "disabled by --no-tools", "yunet")
        return False
    return True


def quiet_models():
    """Model libraries print progress and warnings to stderr; the look prints only its own words."""
    import logging
    import os
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    logging.disable(logging.WARNING)


def diarize(look, wav):
    """Who speaks when: pyannote community-1 on the 16 kHz wav, given as a waveform so no audio decoder is needed.
    -> list of {speaker, start, end}. Raises on failure (the caller records it)."""
    import wave as _w
    import numpy as np
    import torch
    import dl_models
    quiet_models()
    from pyannote.audio import Pipeline
    pipe = Pipeline.from_pretrained(str(dl_models.hf_snapshot("pyannote")))
    if torch.cuda.is_available():
        pipe.to(torch.device("cuda"))
    with _w.open(str(wav), "rb") as w:
        sr = w.getframerate()
        raw = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype("float32") / 32768
    out = pipe({"waveform": torch.from_numpy(raw).unsqueeze(0), "sample_rate": sr})
    dia = getattr(out, "speaker_diarization", out)
    return [{"speaker": spk, "start": round(t.start, 2), "end": round(t.end, 2)} for t, _, spk in dia.itertracks(yield_label=True)]


def speaker_line(look, turns):
    """One line: how many voices, how long each talks, how often they take turns. Speakers are renamed S1, S2... by first appearance."""
    order = []
    for t in turns:
        if t["speaker"] not in order:
            order.append(t["speaker"])
    names = {s: f"S{i + 1}" for i, s in enumerate(order)}
    for t in turns:
        t["speaker"] = names[t["speaker"]]
    talk = {}
    for t in turns:
        talk[t["speaker"]] = talk.get(t["speaker"], 0.0) + t["end"] - t["start"]
    total = sum(talk.values()) or 1.0
    changes = sum(1 for a, b in zip(turns, turns[1:]) if a["speaker"] != b["speaker"])
    look.fact("speakers", len(talk))
    if len(talk) == 1:
        look.line(f"Speakers: 1 voice (S1) over {core.mmss(turns[-1]['end'])}; it talks {total:.0f} s in all. Drill down with --speaker S1.", 82)
    else:
        look.line(f"Speakers: {len(talk)} voices; " + ", ".join(f"{s} {100 * v / total:.0f}% ({v:.0f} s)" for s, v in sorted(talk.items(), key=lambda kv: -kv[1])[:6]) + f"; {changes} changes of speaker. Drill down with --speaker S1.", 82)


def audio_adapters(look, wav, words, dur):
    """Speaker turns (pyannote) and sound-event labels (AST). With the models absent: one row each with the install line."""
    import dl_models
    if look.quick and not look.no_tools:
        look.skip("speaker turns and sound-event labels (models)", "skipped at the quick tier (model start-up takes seconds): run again with --tier standard", None, "")
        return
    if not dl_models.have_model("pyannote") and look.allow_network and not look.no_tools:
        dl_models.download("pyannote")
    if not dl_models.have_model("pyannote"):
        look.skip("who speaks when (speaker turns)", "the pyannote speaker model is not cached on this machine" if not look.no_tools else "disabled by --no-tools", "pyannote")
    elif wav is not None and not look.no_tools:
        key = "speakers"
        try:
            turns = core.cache_get(look, key)
            if turns is None:
                turns = diarize(look, wav)
                core.cache_put(look, key, turns)
            if turns:
                speaker_line(look, turns)   # renames the speakers S1, S2... in place
                look.write_text("speakers.json", json.dumps(turns), "speaker turns: who speaks when", "json", value=5, inline=False, slice_cmd="--speaker S1")
            else:
                look.line("Speakers: none found by the diarization model.", 60)
            look.step("speaker turns", "pyannote")
        except Exception as e:
            look.fail("who speaks when (speaker turns)", "pyannote", e)
    if not dl_models.have_model("ast"):
        look.skip("sound-event labels (speech, music, applause, siren...)", "the AST audio-tagging model is not cached on this machine" if not look.no_tools else "disabled by --no-tools", "ast")
    elif wav is not None and not look.no_tools:
        try:
            quiet_models()
            from transformers import pipeline
            clf = pipeline("audio-classification", model=str(dl_models.hf_snapshot("ast")), top_k=3)
            import wave as _w
            import numpy as np
            with _w.open(str(wav), "rb") as w:
                sr, n = w.getframerate(), w.getnframes()
                raw = np.frombuffer(w.readframes(n), dtype=np.int16).astype("float32") / 32768
            picks = U.sample_plan(max(1, int(n / sr // 10)), head=1, tail=1, strata=4)
            out, both, musicy = [], 0, 0
            for i, _ in sorted(picks[:6]):
                seg = raw[i * 10 * sr:(i + 1) * 10 * sr]
                if len(seg) > sr:
                    allp = sorted(clf({"raw": seg, "sampling_rate": sr}), key=lambda x: -x["score"])
                    top = [x for x in allp[:3] if x["score"] >= 0.08]
                    sc = {x["label"].lower(): x["score"] for x in allp}
                    sp = sc.get("speech", 0) + sc.get("narration, monologue", 0)
                    mu = max((v for k, v in sc.items() if "music" in k), default=0)
                    both += sp >= 0.15 and mu >= 0.15
                    musicy += mu >= 0.15
                    out.append(f"[{core.mmss(i * 10)}] " + ", ".join(f"{x['label']} {x['score']:.2f}".replace(" 0.", " .") for x in top))
            verdict = (f"speech with music together in {both} of {len(out)} samples" if both else f"music in {musicy} of {len(out)} samples, none with speech" if musicy else "no music heard in the samples")
            look.fact("ast_music_samples", musicy)
            look.line(f"Sound events (AST, 10 s samples): {verdict}. " + " ; ".join(out), 82)
            if both and not any(f["kind"] == "MUSIC-BED?" for f in look.flags):
                look.flag("MUSIC-BED?", "AST samples", f"speech and music together in {both} of {len(out)} samples", "confirmed by the audio tagger")
            look.step("sound-event labels", "ast")
        except Exception as e:
            look.fail("sound-event labels", "ast", e)


# ----------------------------------------------------------------------------- speech over a music bed (level and spectrum test)
BED_SECONDS = 600


def pcm_16k(look, seconds=BED_SECONDS):
    """First `seconds` of the audio as 16 kHz mono 16-bit samples (bytes), through ffmpeg. None when it cannot be decoded."""
    ff = look.tool("ffmpeg")
    if not ff:
        return None
    r = look.run([ff, "-v", "error", "-i", str(look.path), "-vn", "-ac", "1", "-ar", "16000", "-t", str(seconds), "-f", "s16le", "-"], timeout=300)
    return r.stdout if r is not None and r.returncode == 0 and len(r.stdout) > 32000 else None


def bed_features(raw):
    """Loudness of 100 ms frames and the spectrum of the quietest ones -> dict(floor, active, gap, flat, low) or None.

    floor = median level of the quietest 20 % of frames (the pauses between words), active = median of the loudest 40 %,
    flat = spectral flatness of the pauses (1 = noise, near 0 = tones), low = share of their energy below 500 Hz. With numpy
    the spectrum is measured; without it only the levels are (flat and low are None).
    """
    import math
    from array import array
    a = array("h")
    a.frombytes(raw[:len(raw) - len(raw) % 2])
    n = 1600
    m = len(a) // n
    if m < 30:
        return None
    try:
        import numpy as np
    except ImportError:
        np = None
    if np is not None:
        x = np.frombuffer(a, dtype=np.int16).astype("float32") / 32768
        fr = x[:m * n].reshape(m, n)
        db = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-6)
        order = np.argsort(db)
        lo = order[:max(3, m // 5)]
        hi = order[-max(3, int(m * 0.4)):]
        floor, act = float(np.median(db[lo])), float(np.median(db[hi]))
        win = np.hanning(n)
        freqs = np.fft.rfftfreq(n, 1 / 16000)[5:]
        flat, low = [], []
        for i in lo[:200]:
            S = np.abs(np.fft.rfft(fr[i] * win)) ** 2 + 1e-12
            S = S[5:]
            flat.append(float(np.exp(np.log(S).mean()) / S.mean()))
            low.append(float(S[freqs < 500].sum() / S.sum()))
        return dict(floor=floor, active=act, gap=act - floor, flat=sum(flat) / len(flat), low=sum(low) / len(low), peak=float(np.percentile(db, 95)))
    db = []
    for k in range(m):
        seg = a[k * n:(k + 1) * n:4]
        db.append(20 * math.log10(math.sqrt(sum(v * v for v in seg) / len(seg)) / 32768 + 1e-6))
    s = sorted(db)
    floor, act = s[len(s) // 10], s[int(len(s) * 0.8)]
    return dict(floor=floor, active=act, gap=act - floor, flat=None, low=None, peak=s[int(len(s) * 0.95)])


def bed_verdict(f, speech):
    """-> 'bed' | 'clean' | 'music' | 'unsure' from the features of bed_features(). Thresholds come from measured voice-only, voice-over-music and music-only files."""
    if f is None:
        return "unsure"
    if not speech and f["gap"] < 14:
        return "music"
    tonal = f["flat"] is None or f["flat"] < 0.075
    bassy = f["low"] is None or f["low"] > 0.6
    if f["floor"] > -46 and tonal and bassy:
        return "bed"
    if f["floor"] <= -46 or (f["flat"] is not None and f["flat"] >= 0.09):
        return "clean"
    return "unsure"


def bed_line(look, speech):
    """One line (and one flag) saying whether the sound under the voice is silence or a steady bed such as music. A level and spectrum test, not a tagger."""
    cached = core.cache_get(look, "bed")
    if cached is not None:
        f = cached.get("f")
    else:
        raw = pcm_16k(look)
        f = bed_features(raw) if raw else None
        core.cache_put(look, "bed", {"f": f})
    if f is None:
        return
    v = bed_verdict(f, speech)
    look.fact("sound_bed", v)
    look.fact("pause_level_db", round(f["floor"], 1))
    spec = "" if f["flat"] is None else f"; pauses are tonal (flatness {f['flat']:.2f}) and bass-heavy"
    if v == "bed":
        if look.headline and look.type in ("audio", "video"):
            look.headline += ", speech over a music bed"
        look.line(f"Under the voice: a steady bed, probably music. The pauses between words sit at {f['floor']:.0f} dB, only {f['gap']:.0f} dB below the speech{spec}.", 84)
        look.flag("MUSIC-BED?", "whole file", f"speech over a continuous bed (pauses at {f['floor']:.0f} dB)", "level and spectrum test; an audio tagger (AST) would confirm music, not noise or hum")
    elif v == "music":
        look.line(f"Sound is continuous with little dynamic range ({f['gap']:.0f} dB between loud and quiet): music or a steady sound, no speech pauses.", 84)
    elif v == "clean":
        look.line(f"Under the voice: nothing steady. Pauses drop to {f['floor']:.0f} dB, so it is speech without a music bed.", 70 if speech else 50)
    else:
        look.line(f"Under the voice: pauses sit at {f['floor']:.0f} dB, {f['gap']:.0f} dB below the speech; a bed is possible but the spectrum does not settle it.", 60)
