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
    plan = U.sample_plan(n, anomalies=[(min(n - 1, int(b) + 1), "after black") for _, b, _ in black_runs[:4]], head=2, tail=2, strata=10 if look.deep else 6)
    plan = plan[:36 if look.deep else 12]
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        look.skip("text on screen (OCR of sampled frames)", "Pillow or numpy not importable", "PIL")
        return
    seen, rows = [], []
    for sec, why in sorted(plan):
        png = grab(float(sec), 960)
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


def audio_adapters(look, wav, words, dur):
    """Speaker turns (pyannote) and sound-event labels (AST). With the models absent: one row each with the install line."""
    import dl_models
    if not dl_models.have_model("pyannote"):
        look.skip("who speaks when (speaker turns)", "the pyannote speaker model is not cached on this machine" if not look.no_tools else "disabled by --no-tools", "pyannote")
    elif wav is not None and not look.no_tools:
        try:
            from pyannote.audio import Pipeline
            pipe = Pipeline.from_pretrained(str(dl_models.hf_snapshot("pyannote")))
            dia = pipe(str(wav))
            turns = [{"speaker": spk, "start": round(t.start, 2), "end": round(t.end, 2)} for t, _, spk in dia.itertracks(yield_label=True)]
            look.write_text("speakers.json", json.dumps(turns), "speaker turns: who speaks when", "json", value=5, inline=False, slice_cmd="--speaker S")
            who = sorted({t["speaker"] for t in turns})
            look.line(f"Speakers: {len(who)} ({', '.join(who[:6])}); {len(turns)} turns. Drill down with --speaker NAME.", 68)
            look.step("speaker turns", "pyannote")
        except Exception as e:
            look.fail("who speaks when (speaker turns)", "pyannote", e)
    if not dl_models.have_model("ast"):
        look.skip("sound-event labels (speech, music, applause, siren...)", "the AST audio-tagging model is not cached on this machine" if not look.no_tools else "disabled by --no-tools", "ast")
    elif wav is not None and not look.no_tools:
        try:
            from transformers import pipeline
            clf = pipeline("audio-classification", model=str(dl_models.hf_snapshot("ast")), top_k=3)
            import wave as _w
            import numpy as np
            with _w.open(str(wav), "rb") as w:
                sr, n = w.getframerate(), w.getnframes()
                raw = np.frombuffer(w.readframes(n), dtype=np.int16).astype("float32") / 32768
            picks = U.sample_plan(max(1, int(n / sr // 10)), head=1, tail=1, strata=4)
            out = []
            for i, _ in picks[:6]:
                seg = raw[i * 10 * sr:(i + 1) * 10 * sr]
                if len(seg) > sr:
                    top = clf({"raw": seg, "sampling_rate": sr})
                    out.append(f"[{core.mmss(i * 10)}] " + ", ".join(f"{x['label']} {x['score']:.2f}" for x in top))
            look.line("Sound events (AST on 10-second samples): " + " ;; ".join(out), 60)
            look.step("sound-event labels", "ast")
        except Exception as e:
            look.fail("sound-event labels", "ast", e)
