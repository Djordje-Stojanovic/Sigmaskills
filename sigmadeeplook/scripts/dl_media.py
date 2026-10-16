"""SigmaDeepLook: video, audio and still images.

Video method: machine facts first (ffprobe, one-pass black / freeze / silence / loudness), words with times, then sheets:
a few pictures with burned-in times, spoken words and flags. More coverage means more sheets (sweep), never more tiles.
Needs ffmpeg for video and audio detail; Pillow for sheets; faster-whisper (cached model) for words. All optional.
"""
import io
import json
import math
import os
import re
import struct
import sys
import threading
import wave
from array import array
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import dl_core as core
import dl_mediax

ASR_CAP_S = 900          # non-deep speech-to-text stops after 15 minutes of audio
SLOT_CANDIDATES = 5


# ================================================================= ffprobe and the one-pass checks
def ffprobe(look, path=None):
    fp = look.tool("ffprobe")
    if not fp:
        return None
    r, out, err = look.run_text([fp, "-v", "error", "-show_entries",
                                 "format=duration,bit_rate,format_name:stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels,duration:stream_disposition=attached_pic",
                                 "-of", "json", str(path or look.path)])
    if r is None:
        return None
    if r.returncode != 0 and not out.strip().startswith("{"):
        look.flag("FFPROBE-ERROR", "container", err.strip().splitlines()[-1][:160] if err.strip() else "ffprobe failed", "the container is damaged or truncated")
        return {}
    try:
        return json.loads(out or "{}")
    except ValueError:
        return {}


def fps_of(s):
    try:
        a, b = s.get("r_frame_rate", "0/1").split("/")
        return float(a) / float(b) if float(b) else 0.0
    except (ValueError, ZeroDivisionError):
        return 0.0


def duration_of(j):
    try:
        return float(j.get("format", {}).get("duration"))
    except (TypeError, ValueError):
        for s in j.get("streams", []):
            try:
                return float(s["duration"])
            except (KeyError, TypeError, ValueError):
                pass
    return 0.0


def one_pass_checks(look, has_v, has_a, dur):
    """black, freeze, silence, loudness in one ffmpeg run. -> dict with lists and the loudness numbers."""
    ff = look.tool("ffmpeg")
    key = f"onepass-{int(has_v)}{int(has_a)}{'q' if look.quick else 's'}"
    hit = core.cache_get(look, key)
    if hit is not None:
        return {k: [tuple(x) for x in v] if isinstance(v, list) else v for k, v in hit.items()}
    cmd = [ff, "-hide_banner", "-nostats"] + (["-skip_frame", "nokey"] if look.quick and has_v else []) + ["-i", str(look.path)]
    if has_v:   # the quick tier decodes keyframes only: black stretches are found, frozen pictures are not looked for
        cmd += ["-vf", "blackdetect=d=0.1:pix_th=0.10" + ("" if look.quick else ",freezedetect=n=-60dB:d=2")]
    else:
        cmd += ["-vn"]
    if has_a:
        cmd += ["-af", "silencedetect=n=-50dB:d=1,ebur128=peak=true:framelog=quiet"]
    else:
        cmd += ["-an"]
    cmd += ["-f", "null", "-"]
    r, _, err = look.run_text(cmd, timeout=core.TIMEOUT_DEEP if dur > 600 else 300)
    res = {"black": [], "freeze": [], "silence": [], "loud": {}}
    if r is None:
        return res
    for m in re.finditer(r"black_start:([\d.]+)\s+black_end:([\d.]+)\s+black_duration:([\d.]+)", err):
        res["black"].append((float(m.group(1)), float(m.group(2))))
    fs = [float(x) for x in re.findall(r"freeze_start:\s*([\d.]+)", err)]
    fe = [float(x) for x in re.findall(r"freeze_end:\s*([\d.]+)", err)]
    for i, s in enumerate(fs):
        res["freeze"].append((s, fe[i] if i < len(fe) else dur))
    ss = [float(x) for x in re.findall(r"silence_start:\s*(-?[\d.]+)", err)]
    se = [float(x) for x in re.findall(r"silence_end:\s*([\d.]+)", err)]
    for i, s in enumerate(ss):
        res["silence"].append((max(0.0, s), se[i] if i < len(se) else dur))
    tail = err[err.rfind("Summary:"):] if "Summary:" in err else ""
    for k2, rx in (("lufs", r"I:\s+(-?[\d.]+) LUFS"), ("lra", r"LRA:\s+(-?[\d.]+) LU"), ("peak", r"Peak:\s+(-?[\d.]+) dBFS")):
        m = re.search(rx, tail)
        if m:
            res["loud"][k2] = float(m.group(1))
    core.cache_put(look, key, res)
    return res


def report_checks(look, res, dur):
    look.silence_runs = list(res["silence"])
    dl_mediax.flag_runs(look, "BLACK", res["black"], 1.0, "of black", "a designed card or a defect? confirm with the tile at that time")
    dl_mediax.flag_runs(look, "FREEZE", res["freeze"], 2.0, "frozen picture", "still image or a stuck frame")
    dl_mediax.flag_runs(look, "SILENCE", res["silence"], 2.0, "below -50 dB", "pause, dropout or missing audio")
    if res["loud"]:
        l = res["loud"]
        look.fact("lufs", l.get("lufs"))
        look.fact("lra", l.get("lra"))
        look.fact("true_peak_dbfs", l.get("peak"))
        look.line(f"Loudness (EBU R128): integrated {l.get('lufs')} LUFS, range {l.get('lra')} LU, peak {l.get('peak')} dBFS (broadcast target -23 LUFS, peak at most -1).")
        if l.get("peak") is not None and l["peak"] > -1:
            look.flag("LOUD-PEAK", "whole file", f"{l['peak']} dBFS", "peak above -1 dBFS can clip when re-encoded")
    look.fact("black", [round(a, 2) for a, _ in res["black"]])
    look.fact("freeze", [round(a, 2) for a, _ in res["freeze"]])
    look.fact("silence", [[round(a, 2), round(b, 2)] for a, b in res["silence"]])
    if res["black"] or res["freeze"] or res["silence"]:
        def times(kind):
            ts = [core.mmss(a) for a, _ in res[kind]]
            return ", ".join(ts[:8]) + (f" and {len(ts) - 8} more ({len(ts)} in all)" if len(ts) > 8 else "")
        look.line("Machine checks: " + "; ".join(
            [f"black at {times('black')}"] * bool(res["black"]) +
            [f"frozen at {times('freeze')}"] * bool(res["freeze"]) +
            [f"silence at {times('silence')}"] * bool(res["silence"])))
    else:
        look.line("Machine checks: no black, frozen or silent stretch found." if not look.quick else "Machine checks: no black (keyframes) or silent stretch found; frozen pictures are not checked at the quick tier.")


# ================================================================= speech
def pick_model(look):
    order = ["large-v3", "medium", "small", "base"] if look.deep else ["base", "small", "tiny"]
    cache = Path(os.environ.get("HF_HOME") or os.path.expanduser("~/.cache/huggingface")) / "hub"
    for n in order + ["medium.en", "small.en", "base.en", "large-v2", "tiny.en"]:
        if (cache / f"models--Systran--faster-whisper-{n}").exists():
            return n
    return None


_WM_LOCK = threading.RLock()


def prefetch_whisper(look):
    """Import faster-whisper and load the model in the background while ffprobe and the one-pass checks run (the import alone takes seconds).
    The thread records nothing: a missing model becomes a 'Not looked at' row only when speech is really needed."""
    threading.Thread(target=lambda: whisper_model(look, record=False), daemon=True).start()


def whisper_model(look, record=True):
    """-> (model, name, version) loaded once per look, or None (the 'Not looked at' row is recorded here)."""
    with _WM_LOCK:
        if getattr(look, "_wm", None) is not None:
            return look._wm or None
        fw = look.mod("faster_whisper")
        if not fw:
            if record:
                look.skip("words with times (speech-to-text)", "faster-whisper not importable" if not look.no_tools else "disabled by --no-tools", "faster_whisper")
                look._wm = False
            return None
        name = pick_model(look)
        if not name:
            if record:
                look.skip("words with times (speech-to-text)", "no Whisper model is cached and downloads need --allow-network", "faster_whisper",
                          "run once with --allow-network, or: python -c \"from faster_whisper import WhisperModel; WhisperModel('base')\"")
                look._wm = False
            return None
        if not look.allow_network:
            os.environ["HF_HUB_OFFLINE"] = "1"
        try:
            look._wm = (fw.WhisperModel(name, device="cpu", compute_type="int8", local_files_only=not look.allow_network), name, getattr(fw, "__version__", ""))
        except Exception as e:
            if record:
                look.fail("words with times (speech-to-text)", "faster_whisper", e)
                look._wm = False
            return None
        return look._wm


def run_whisper(look, wav, beam=5, words=True, offset=0.0):
    """faster-whisper with VAD, no conditioning on previous text (the two settings that stop looping hallucinations).
    -> (segments, language) with times shifted by `offset`, or None."""
    wm = whisper_model(look)
    if wm is None:
        return None
    model, name, ver = wm
    try:
        segs, info = model.transcribe(str(wav), beam_size=beam, vad_filter=True, condition_on_previous_text=False, word_timestamps=words)
        out = []
        for s in segs:   # a generator: nothing runs until it is iterated
            out.append({"start": round(s.start + offset, 2), "end": round(s.end + offset, 2), "text": s.text.strip(),
                        "words": [{"w": w.word.strip(), "s": round(w.start + offset, 2), "e": round(w.end + offset, 2), "p": round(w.probability, 2)} for w in (s.words or [])] if words else []})
        look.fact("asr_model", name)
        look.fact("language", info.language)
        return out, info.language
    except Exception as e:
        look.fail("words with times (speech-to-text)", "faster_whisper", e)
        return None


def transcribe(look, wav, dur, name="speech"):
    """The whole audio (or its first ASR_CAP_S seconds) through Whisper, kept for the next run on the same bytes. -> (segments, language) or None."""
    wm = whisper_model(look)
    if wm is None:
        return None
    key = f"asr-{wm[1]}-{int(look.deep)}"
    hit = core.cache_get(look, key)
    if hit:
        look.step("speech to text (kept from an earlier run)", f"faster-whisper {wm[1]}", version=wm[2])
        look.fact("asr_model", wm[1])
        look.fact("language", hit["lang"])
        return hit["segs"], hit["lang"]
    got = run_whisper(look, wav)
    if got is None:
        return None
    look.step("speech to text", f"faster-whisper {wm[1]}", version=wm[2])
    core.cache_put(look, key, {"segs": got[0], "lang": got[1]})
    return got


SAMPLE_WINDOWS = ((0.08, 25.0), (0.50, 25.0), (0.88, 25.0))   # (position in the file, seconds) of the quick tier's speech samples


def sample_windows(dur):
    """Where the quick tier listens: the whole thing when it is short, else three 25-second windows. -> [(start, length)]"""
    if dur <= 90:
        return [(0.0, dur)]
    return [(max(0.0, min(dur - w, c * dur - w / 2)), w) for c, w in SAMPLE_WINDOWS]


def transcribe_sample(look, dur):
    """Quick tier: Whisper on a few short windows. -> (segments, language, windows) or None. Times are absolute; there are no word times."""
    if whisper_model(look) is None:
        return None
    wins = sample_windows(dur)
    key = "asr-sample-" + "-".join(f"{int(a)}" for a, _ in wins)
    hit = core.cache_get(look, key)
    if hit:
        return hit["segs"], hit["lang"], wins
    segs, lang = [], ""
    for a, w in wins:
        wav = extract_wav(look, look.path, w, f"_sample{int(a)}.wav", start=a)
        if not wav:
            continue
        got = run_whisper(look, wav, beam=1, words=False, offset=a)
        wav.unlink(missing_ok=True)
        if got:
            segs += got[0]
            lang = lang or got[1]
    look.step("speech samples", f"faster-whisper {whisper_model(look)[1]}")
    core.cache_put(look, key, {"segs": segs, "lang": lang})
    return segs, lang, wins


def gist_lines(segs, dur, sampled):  # sampled: None, or the [(start, length)] windows the segments came from
    """2-3 short quotes that say what the speech is about: the opening, then the longest sentence of the middle and of the end."""
    segs = [s for s in segs if len(s["text"].split()) >= 4]
    if not segs:
        return []

    def q(s, n=150):
        t = " ".join(s["text"].split())
        return f"[{core.mmss(s['start'])}] {t if len(t) <= n else t[:n - 1] + '…'}"
    if sampled:
        groups = [[s for s in segs if a - 1 <= s["start"] < a + w] for a, w in sampled]
        return [q(max(g, key=lambda s: min(len(s["text"]), 160))) for g in groups if g]
    out = [q(segs[0])] if len(segs[0]["text"]) >= 60 or len(segs) < 2 else [q({"start": segs[0]["start"], "text": segs[0]["text"] + " " + segs[1]["text"]})]
    rest = [s for s in segs if s["start"] > segs[0]["start"] + 20]
    for grp in _thirds(rest, 2):
        out.append(q(max(grp, key=lambda s: (s["text"][:1].isupper(), min(len(s["text"]), 160)))))
    return out


def _thirds(segs, parts):
    """Cut a list into `parts` consecutive groups (a group may be empty)."""
    n = len(segs)
    return [g for g in (segs[i * n // parts:(i + 1) * n // parts] for i in range(parts)) if g]


def write_transcript(look, segs, lang, dur, sampled=None):
    words = [w for s in segs for w in s["words"]]
    if not segs:
        look.line("Speech: none found (the voice-activity filter removed everything: music, noise or silence).")
        look.fact("words", 0)
        return []
    nwords = len(words) or sum(len(s["text"].split()) for s in segs)
    if words:
        look.write_text("words.json", json.dumps(words), "every word with start and end seconds and confidence", "json", inline=False)

    def ts(t):
        return f"{int(t // 3600):02d}:{int(t % 3600 // 60):02d}:{int(t % 60):02d},{int(t % 1 * 1000):03d}"
    srt = "\n\n".join(f"{i}\n{ts(s['start'])} --> {ts(s['end'])}\n{s['text']}" for i, s in enumerate(segs, 1))
    look.write_text("transcript.srt", srt, "transcript with times (SRT)" if not sampled else "speech samples with times (SRT)", inline=False)
    lines = [f"[{core.mmss(s['start'])}] {' '.join(s['text'].split())}" for s in segs]
    look.write_text("transcript.md" if not sampled else "speech-sample.md", "\n".join(lines),
                    "the speech, one line per segment with its start" if not sampled else "speech heard in the sampled windows, one line per segment", value=6)
    text = " ".join(s["text"] for s in segs)
    look.fact("transcript", text[:2000])
    look.fact("words", nwords)
    low = [s for s in segs if s["words"] and sum(w["p"] for w in s["words"]) / len(s["words"]) < 0.5]
    for s in low[:5]:
        look.flag("LOW-CONFIDENCE", f"{core.mmss(s['start'])} ({s['start']:.1f}s)", s["text"][:60], "words with low confidence: check by ear")
    dl_mediax.silence_hallucinations(look, segs)
    reps = [s["text"] for s in segs]
    if len(reps) >= 4 and max(reps.count(t) for t in set(reps)) >= 4:
        look.flag("REPEATED-LINE", "transcript", "a line repeats 4+ times", "typical Whisper hallucination over silence or music")
    gist = gist_lines(segs, dur, sampled)
    if sampled:
        head = f"Speech ({lang}), heard in {len(sampled)} sample(s) of {int(sampled[0][1])} s at " + ", ".join(core.mmss(a) for a, _ in sampled) + f" ({nwords} words); the rest is not transcribed at the quick tier"
    else:
        span = max(1.0, segs[-1]["end"] - segs[0]["start"])
        head = f"Speech ({lang}): {nwords} words, ~{nwords / span * 60:.0f} per minute"
    look.line(head + (". Gist: " + " / ".join(gist) if gist else "."), 83)
    return words


def extract_wav(look, src, seconds=None, name="audio.wav", start=None):
    ff = look.tool("ffmpeg")
    out = look.path_for(name)
    cmd = [ff, "-y", "-v", "error"] + (["-ss", f"{start:.2f}"] if start else []) + ["-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le"]
    if seconds:
        cmd += ["-t", str(seconds)]
    r = look.run(cmd + [str(out)])
    return out if r is not None and r.returncode == 0 and out.exists() and out.stat().st_size > 100 else None


# ================================================================= MP4 atoms (stdlib, no ffmpeg)
def mp4_facts(path):
    """Duration, size and stream kinds from the moov atom. Stdlib only. -> dict (may be empty)."""
    facts = {"streams": []}
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            def walk(start, end, depth, ctx):
                pos = start
                while pos + 8 <= end:
                    f.seek(pos)
                    h = f.read(8)
                    ln, typ = struct.unpack(">I4s", h)
                    hdr = 8
                    if ln == 1:
                        ln = struct.unpack(">Q", f.read(8))[0]
                        hdr = 16
                    elif ln == 0:
                        ln = end - pos
                    if ln < hdr or pos + ln > end + 1:
                        facts["truncated_atom"] = typ.decode("latin-1")
                        return
                    body = pos + hdr
                    if typ in (b"moov", b"trak", b"mdia", b"minf", b"stbl"):
                        walk(body, pos + ln, depth + 1, ctx if typ != b"trak" else {})
                        if typ == b"trak" and ctx is not None:
                            pass
                    elif typ == b"mvhd":
                        f.seek(body)
                        v = f.read(1)[0]
                        f.seek(body + 4 + (16 if v else 8))
                        ts, du = struct.unpack(">IQ" if v else ">II", f.read(12 if v else 8))
                        facts["duration"] = du / ts if ts else 0
                    elif typ == b"tkhd":
                        f.seek(body + ln - hdr - 8)
                        w, h2 = struct.unpack(">II", f.read(8))
                        facts["streams"].append({"w": w >> 16, "h": h2 >> 16})
                    elif typ == b"hdlr":
                        f.seek(body + 8)
                        kind = f.read(4).decode("latin-1")
                        if facts["streams"]:
                            facts["streams"][-1]["kind"] = {"vide": "video", "soun": "audio", "sbtl": "subtitle", "text": "subtitle", "tmcd": "timecode"}.get(kind, kind)
                    elif typ == b"stsd":
                        f.seek(body + 12)
                        facts["streams"][-1]["codec"] = f.read(4).decode("latin-1") if facts["streams"] else ""
                    elif typ == b"ftyp":
                        f.seek(body)
                        facts["brand"] = f.read(4).decode("latin-1")
                    pos += ln
            walk(0, size, 0, None)
    except (OSError, struct.error, IndexError):
        pass
    return facts


# ================================================================= fonts and drawing helpers
def font(px):
    from PIL import ImageFont
    for name in ("arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf", "C:/Windows/Fonts/arial.ttf"):
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=px)
    except TypeError:
        return ImageFont.load_default()


def fit_text(d, text, f, width):
    if d.textlength(text, font=f) <= width:
        return text
    while text and d.textlength(text + "...", font=f) > width:
        text = text[:-1]
    return text + "..."


def words_at(words, t, span=1.3, cap=10):
    got = [w["w"] for w in words if w["s"] - span <= t <= w["e"] + span]
    return " ".join(got[:cap])


# ================================================================= video
def look_video(look):
    if not look.no_tools:
        prefetch_whisper(look)
    ffp = ffprobe(look)
    if ffp is None:
        return video_bare(look)
    streams = ffp.get("streams", [])
    vs = [s for s in streams if s.get("codec_type") == "video" and not s.get("disposition", {}).get("attached_pic")]
    au = [s for s in streams if s.get("codec_type") == "audio"]
    sub = [s for s in streams if s.get("codec_type") == "subtitle"]
    if not vs and au:
        look.type = "audio"
        look.detector["note"] = "no video stream: treated as audio"
        return look_audio(look, ffp)
    if not streams:
        look.flag("NO-STREAMS", "container", "ffprobe found no readable stream", "damaged, truncated or not a media file")
        look.exit_code = 0
        facts = mp4_facts(look.path) if look.subtype == "mp4" else {}
        return video_bare(look, facts)
    dur = duration_of(ffp)
    v = vs[0]
    look.fact("duration", round(dur, 2))
    look.fact("width", v.get("width"))
    look.fact("height", v.get("height"))
    look.fact("fps", round(fps_of(v), 2))
    look.fact("video_codec", v.get("codec_name"))
    look.fact("audio_streams", len(au))
    look.fact("subtitle_streams", len(sub))
    look.headline = f"video {core.mmss(dur)}, {v.get('width')}x{v.get('height')}, {v.get('codec_name')}" + (", no audio" if not au else "")
    look.dims = f"{core.mmss(dur)}"
    look.line(f"Video: {core.mmss(dur)} ({dur:.1f} s), {v.get('width')}x{v.get('height')} at {fps_of(v):.2f} fps, {v.get('codec_name')}; "
              f"{len(au)} audio stream(s) ({', '.join(a.get('codec_name', '?') for a in au) or 'none'}), {len(sub)} subtitle stream(s).", 80)
    if not au:
        look.flag("NO-AUDIO", "container", "no audio stream", "silent video")
    if look.subtype == "mp4":
        cut = mp4_facts(look.path).get("truncated_atom")
        if cut:
            look.flag("TRUNCATED", "container", f"atom {cut} runs past the end of the file", "the file is cut short; playback stops early or breaks (the header is intact, so ffprobe still reports the full length)")
    look.write_text("probe.json", json.dumps(ffp, indent=1), "ffprobe facts (streams, codecs, sizes)", "json")
    def checks():
        r = one_pass_checks(look, True, bool(au), dur)
        report_checks(look, r, dur)
        look.step("black, freeze, silence, loudness (one pass)", "ffmpeg")
        return r
    words = []
    sub_text = None
    # the one-pass checks, the scene scan and the speech-to-text do not need each other: they run side by side
    with ThreadPoolExecutor(2) as ex:
        f_checks = ex.submit(checks)
        f_scenes = None
        if look.quick:
            look.skip("scene cuts and shot lengths", "skipped at the quick tier: run again with --tier standard", None, "")
        else:
            f_scenes = ex.submit(dl_mediax.scenes, look, dur)
        if sub:
            sub_text = extract_subtitles(look)
        if au:
            words = speech_for(look, dur, ready=f_checks)
        res = f_checks.result()
        if f_scenes is not None:
            f_scenes.result()
    if au:
        dl_mediax.bed_line(look, getattr(look, "speech_found", bool(words)))
    dl_mediax.chapters_line(look, ffp)
    if look.mod("PIL"):
        try:
            make_video_sheets(look, v, dur, words, res, au)
        except Exception as e:
            look.fail("contact sheets", "Pillow", e)
    else:
        ffmpeg_sheet(look, v, dur)
    if au:
        dl_mediax.loudness_line(look, audio_levels(look, dur), dur)
    dl_mediax.ocr_video(look, dur, dl_mediax.runs(res["black"], 1.0), lambda t, w: grab_png(look, t, w))
    dl_mediax.faces_row(look)
    if au:
        dl_mediax.audio_adapters(look, look.out / "audio.wav" if (look.out / "audio.wav").exists() else None, words, dur)
    if dur > 180:
        look.line(f"Long video: one overview sheet covers a tile per {dur / look.reader['cols'] / look.reader['rows']:.0f} s. Run `--mode sweep` for {math.ceil(dur / 180)} pages that cover every part, or `--at T --len S` to zoom.")
    look.ask_human("Is the black or silent stretch in Flags intended (a designed card) or a defect?",
                   "Which sound, voice or motion judgements need a human listening or watching (this look cannot hear or judge taste)?",
                   "Which moments or claims should be checked on a zoom window?")
    return None


def video_bare(look, facts=None):
    facts = facts or (mp4_facts(look.path) if look.subtype in ("mp4",) else {})
    if facts.get("duration"):
        look.fact("duration", round(facts["duration"], 2))
    vids = [s for s in facts.get("streams", []) if s.get("kind") == "video"]
    if vids:
        look.fact("width", vids[0]["w"])
        look.fact("height", vids[0]["h"])
    look.fact("audio_streams", sum(1 for s in facts.get("streams", []) if s.get("kind") == "audio"))
    look.fact("subtitle_streams", sum(1 for s in facts.get("streams", []) if s.get("kind") == "subtitle"))
    if facts.get("duration") or facts.get("streams"):
        look.line(f"Video container (read from the file's own atoms, brand {facts.get('brand', '?')}): " +
                  (f"{facts.get('duration', 0):.1f} s, " if facts.get("duration") else "") +
                  ", ".join(f"{s.get('kind', '?')} {s.get('codec', '')} {str(s['w']) + 'x' + str(s['h']) if s.get('w') else ''}".strip() for s in facts.get("streams", [])))
    else:
        look.line("Video file; the container could not be read without ffmpeg.")
    if facts.get("truncated_atom"):
        look.flag("TRUNCATED", "container", f"atom {facts['truncated_atom']} runs past the end of the file", "the file is cut short; playback stops early")
    if "duration" not in facts and look.subtype == "mp4":
        look.flag("NO-MOOV", "container", "no readable moov atom", "damaged or cut file: players cannot seek or play it")
    why = "disabled by --no-tools" if look.no_tools else "ffmpeg / ffprobe not found"
    for step in ("codec, frame rate and stream details", "black, frozen and silent stretches, loudness", "subtitle text", "words with times", "contact sheets (pictures)"):
        look.skip(step, why, "ffmpeg")
    look.ask_human("Can ffmpeg be installed so the picture and sound can be checked?")


def extract_subtitles(look):
    ff = look.tool("ffmpeg")
    out = look.path_for("subtitles.srt")
    r = look.run([ff, "-y", "-v", "error", "-i", str(look.path), "-map", "0:s:0", "-f", "srt", str(out)])
    if r is not None and r.returncode == 0 and out.exists() and out.stat().st_size > 0:
        txt = out.read_text(encoding="utf-8", errors="replace")
        look.add(out, "text", "embedded subtitle stream as SRT (used before speech-to-text)")
        look.fact("subtitle_text", re.sub(r"\d+\n[\d:,]+ --> [\d:,]+\n", "", txt).replace("\n", " ").strip()[:500])
        look.line("Embedded subtitles: " + look.facts["subtitle_text"][:200])
        look.step("embedded subtitles", "ffmpeg")
        return txt
    out.unlink(missing_ok=True)
    look.skip("embedded subtitle text", "the subtitle stream is a picture format or could not be converted to SRT", None, "")
    return None


def speech_for(look, dur, ready=None):
    """Speech for a video. `ready`: a future that must finish before the transcript is written (the silence runs it needs come from the one-pass checks)."""
    if look.quick:
        got = transcribe_sample(look, dur)
        if ready is not None:
            ready.result()
        if got is not None:
            write_transcript(look, got[0], got[1], dur, sampled=got[2])
            look.speech_found = bool(got[0])
        return []
    sec = None if look.deep else ASR_CAP_S
    wav = extract_wav(look, look.path, sec)
    if not wav:
        look.skip("words with times", "audio could not be extracted", None, "")
        return []
    got = transcribe(look, wav, dur)
    keep = wav.stat().st_size < 50 << 20
    if keep:
        look.add(wav, "internal", "16 kHz mono audio used for speech-to-text")
    else:
        wav.unlink(missing_ok=True)
    if got is None:
        return []
    if dur > ASR_CAP_S and not look.deep:
        look.flag("PARTIAL", "speech", f"first {ASR_CAP_S // 60} minutes only", "use --deep for the whole file")
    look.speech_found = bool(got[0])
    if ready is not None:
        ready.result()
    return write_transcript(look, got[0], got[1], dur)


def scenes_list(look, dur):
    ff = look.tool("ffmpeg")
    if not ff:
        return
    r, _, err = look.run_text([ff, "-hide_banner", "-nostats", "-i", str(look.path), "-an", "-vf", "select='gt(scene,0.4)',showinfo", "-fps_mode", "passthrough", "-f", "null", "-"], timeout=300)
    if r is None:
        return
    times = [float(x) for x in re.findall(r"pts_time:([\d.]+)", err)]
    look.fact("scene_cuts", len(times))
    if times:
        look.write_text("scenes.csv", "start_s\n0.0\n" + "\n".join(f"{t:.2f}" for t in times), f"{len(times)} scene cuts (ffmpeg scene score above 0.4)")
        look.line(f"Scene cuts: {len(times)} (list in scenes.csv).")
    else:
        look.line("Scene cuts: none above the 0.4 score (one continuous shot, or soft transitions).")


# ---------------------------------------------------------------- sheets
def grab_png(look, t, width):
    ff = look.tool("ffmpeg")
    r = look.run([ff, "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(look.path), "-frames:v", "1", "-an",
                  "-vf", f"scale={width}:-2:flags=bicubic", "-f", "image2pipe", "-vcodec", "png", "-"])
    return r.stdout if r is not None and r.returncode == 0 and r.stdout else None


def gray_probe(look, t):
    """A 64x36 gray frame as bytes, for sharpness. None when the seek fails."""
    ff = look.tool("ffmpeg")
    r = look.run([ff, "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(look.path), "-frames:v", "1", "-an",
                  "-vf", "scale=64:36:flags=fast_bilinear,format=gray", "-f", "rawvideo", "-"])
    return r.stdout if r is not None and len(r.stdout) == 64 * 36 else None


def sharp(g):
    s = sum(abs(g[i] - g[i + 1]) for i in range(0, len(g) - 1) if (i + 1) % 64) + sum(abs(g[i] - g[i + 64]) for i in range(0, len(g) - 64))
    return s / len(g)


def pick_times(look, lo, hi, n):
    """Slot centres (i+0.5)*D/n; in each slot the sharpest of a few nearby candidates wins (a blur or a half-faded frame loses)."""
    span = hi - lo
    slots = [(i, lo + (i + 0.5) * span / n) for i in range(n)]
    cands = {}
    ncand = 1 if look.quick else SLOT_CANDIDATES   # the quick tier takes the slot centre without hunting for the sharpest frame
    for i, c in slots:
        w = span / n
        cands[i] = [min(max(lo, c + k * w * 0.18), max(lo, hi - 0.05)) for k in range(-(ncand // 2), ncand // 2 + 1)]
    flat = [(i, t) for i, ts in cands.items() for t in ts]
    with ThreadPoolExecutor(8) as ex:
        probes = list(ex.map(lambda it: gray_probe(look, it[1]), flat))
    best = {}
    for (i, t), g in zip(flat, probes):
        if g is None:
            continue
        sc = sharp(g)
        mean = sum(g) / len(g)
        # a candidate nearer the slot centre wins ties; blank frames are allowed (a black card is a fact)
        sc = sc - abs(t - slots[i][1]) * 0.01
        if i not in best or sc > best[i][0]:
            best[i] = (sc, t)
    return [best[i][1] if i in best else slots[i][1] for i in range(n)]


def add_flag_tiles(times, res, lo, hi):
    """A black or frozen stretch that falls between two slots would never be seen: it takes the place of the nearest tile."""
    times = list(times)
    gap = (hi - lo) / max(1, len(times)) / 2
    for a, b in (res.get("black", []) + res.get("freeze", []))[:3]:
        if not (lo <= a <= hi) or any(a - 0.05 <= t <= b + 0.05 for t in times):
            if not (lo <= a <= hi):
                continue
            mid = (a + min(b, hi)) / 2
            i = min(range(len(times)), key=lambda k: abs(times[k] - mid))
            times[i] = mid
    return sorted(times)


def make_video_sheets(look, v, dur, words, res, au):
    mode = getattr(look.opts, "mode", "overview")
    at = getattr(look.opts, "at", None)
    n = look.reader["cols"] * look.reader["rows"]
    jobs = []
    if at is not None:
        ln = float(getattr(look.opts, "length", 10.0))
        lo, hi = max(0.0, at), min(dur, at + ln)
        jobs.append((f"sheet-window-{int(at)}s.jpg", lo, hi, f"window {core.mmss(lo)}-{core.mmss(hi)}"))
    elif mode == "sweep":
        pages = max(1, math.ceil(dur / 180))
        for k in range(pages):
            jobs.append((f"sheet-sweep-{k + 1}.jpg", dur * k / pages, dur * (k + 1) / pages, f"sweep page {k + 1}/{pages}"))
    else:
        jobs.append(("sheet-overview.jpg", 0.0, dur, "overview"))
    levels = audio_levels(look, dur) if au else None
    for name, lo, hi, title in jobs:
        times = add_flag_tiles(pick_times(look, lo, hi, n), res, lo, hi)
        render_sheet(look, name, title, times, words, res, v, levels, dur, lo, hi)
    look.step("contact sheets", "ffmpeg + Pillow")


def audio_levels(look, dur, step=0.5):
    """dB per `step` seconds, from 4 kHz mono samples (stdlib array; first 30 minutes). Computed once per look."""
    if getattr(look, "_levels", None) is None:
        look._levels = _audio_levels(look, dur, step) or False
    return look._levels or None


def _audio_levels(look, dur, step=0.5):
    ff = look.tool("ffmpeg")
    r = look.run([ff, "-v", "error", "-i", str(look.path), "-vn", "-ac", "1", "-ar", "4000", "-t", "1800", "-f", "s16le", "-"], timeout=300)
    if r is None or not r.stdout:
        return None
    a = array("h")
    a.frombytes(r.stdout[: len(r.stdout) // 2 * 2])
    if sys.byteorder == "big":
        a.byteswap()
    w = int(4000 * step)
    out = []
    for i in range(0, len(a) - w + 1, w):
        ch = a[i:i + w]
        rms = math.sqrt(sum(x * x for x in ch) / w) / 32768 + 1e-6
        out.append(20 * math.log10(rms))
    return out


def render_sheet(look, name, title, times, words, res, v, levels, dur, lo, hi):
    from PIL import Image, ImageDraw
    cols, rows, W = look.reader["cols"], look.reader["rows"], look.reader["width"]
    pad = 8
    tw = (W - pad * (cols + 1)) // cols
    vw, vh = v.get("width") or 16, v.get("height") or 9
    th = int(round(tw * vh / vw))
    cap_h = 44
    strip_h = 54 if levels else 0
    head_h = 34
    fn, fs, fc = font(22), font(15), font(17)
    tiles = []
    with ThreadPoolExecutor(8) as ex:
        pngs = list(ex.map(lambda t: grab_png(look, t, tw), times))
    H = head_h + rows * (th + cap_h + pad) + pad + strip_h
    sheet = Image.new("RGB", (W, H), (18, 18, 18))
    d = ImageDraw.Draw(sheet)
    d.text((pad, 6), f"{look.path.name}  |  {title}  |  {core.mmss(dur)}  |  {look.reader['name']} {cols}x{rows}", font=fc, fill=(235, 235, 235))
    tags = {}
    for t in times:
        k = []
        if any(a <= t <= b for a, b in res.get("black", [])):
            k.append("BLACK")
        if any(a <= t <= b for a, b in res.get("freeze", [])):
            k.append("FROZEN")
        if any(a <= t <= b for a, b in res.get("silence", [])):
            k.append("SILENT")
        tags[t] = k
    for i, (t, png) in enumerate(zip(times, pngs)):
        c, r = i % cols, i // cols
        x, y = pad + c * (tw + pad), head_h + r * (th + cap_h + pad)
        if png:
            im = Image.open(io.BytesIO(png)).convert("RGB").resize((tw, th))
            sheet.paste(im, (x, y))
        else:
            d.rectangle([x, y, x + tw, y + th], outline=(120, 120, 120))
        lab = core.mmss(t)
        d.rectangle([x, y, x + 8 + d.textlength(lab, font=fn), y + 28], fill=(0, 0, 0))
        d.text((x + 4, y + 2), lab, font=fn, fill=(255, 235, 59))
        if tags[t]:
            d.rectangle([x, y, x + tw - 1, y + th - 1], outline=(230, 40, 40), width=4)
            tg = " ".join(tags[t])
            d.rectangle([x + tw - 12 - d.textlength(tg, font=fs), y, x + tw, y + 22], fill=(200, 30, 30))
            d.text((x + tw - 8 - d.textlength(tg, font=fs), y + 3), tg, font=fs, fill=(255, 255, 255))
        sp = words_at(words, t)
        d.text((x + 2, y + th + 4), fit_text(d, sp or "(no words)", fs, tw - 4), font=fs, fill=(210, 210, 210) if sp else (110, 110, 110))
    if levels:
        y0 = H - strip_h
        d.rectangle([pad, y0, W - pad, y0 + strip_h - 8], fill=(30, 30, 30))
        x0, x1 = pad, W - pad
        step = 0.5
        i0, i1 = int(lo / step), max(int(lo / step) + 1, int(hi / step))
        seg = levels[i0:i1] or [-60]
        for j, db in enumerate(seg):
            x = x0 + (x1 - x0) * j / len(seg)
            h = max(1, int((max(-60, min(0, db)) + 60) / 60 * (strip_h - 12)))
            d.line([x, y0 + strip_h - 9, x, y0 + strip_h - 9 - h], fill=(80, 190, 190), width=max(1, (x1 - x0) // len(seg)))
        for t in times:
            x = x0 + (x1 - x0) * (t - lo) / max(hi - lo, 1e-6)
            d.line([x, y0, x, y0 + strip_h - 8], fill=(255, 235, 59), width=1)
        for a, b in res.get("silence", []):
            if b > lo and a < hi:
                xa, xb = x0 + (x1 - x0) * (max(a, lo) - lo) / (hi - lo), x0 + (x1 - x0) * (min(b, hi) - lo) / (hi - lo)
                d.rectangle([xa, y0, xb, y0 + 5], fill=(220, 50, 50))
        d.text((x0 + 4, y0 + 2), "loudness (teal) | tile centres (yellow) | silence (red)", font=fs, fill=(190, 190, 190))
    edge = look.reader["edge"]
    if max(sheet.size) > edge:
        k = edge / max(sheet.size)
        sheet = sheet.resize((int(sheet.width * k), int(sheet.height * k)), Image.LANCZOS)
    p = look.path_for(name)
    sheet.save(p, quality=88)
    look.add(p, "image", f"contact sheet: {title}, {cols * rows} tiles with M:SS, spoken words and flags")


def ffmpeg_sheet(look, v, dur):
    """No Pillow: ffmpeg alone makes the sheet (fps sampling, drawtext, tile)."""
    ff = look.tool("ffmpeg")
    look.skip("Pillow sheet with words and loudness strip", "Pillow not importable" if not look.no_tools else "disabled by --no-tools", "PIL")
    fontfile = None
    for p in (r"C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"):
        if os.path.exists(p):
            fontfile = p
            break
    n = look.reader["cols"] * look.reader["rows"]
    cols, rows = look.reader["cols"], look.reader["rows"]
    tw = (look.reader["width"] - 4 * (cols + 1)) // cols
    S = dur / (2 * n)
    dt = ""
    if fontfile:
        ff_esc = fontfile.replace(":", r"\:")
        dt = f",drawtext=fontfile='{ff_esc}':text='%{{pts\\:hms\\:{S:.3f}}}':x=6:y=6:fontsize=22:fontcolor=yellow:box=1:boxcolor=black@0.6"
    out = look.path_for("sheet-overview.jpg")
    vf = f"fps={n}/{dur:.3f},scale={tw}:-2{dt},tile={cols}x{rows}:padding=4:color=black"
    r = look.run([ff, "-y", "-v", "error", "-ss", f"{S:.3f}", "-i", str(look.path), "-vf", vf, "-frames:v", "1", "-q:v", "3", str(out)])
    if r is not None and r.returncode == 0 and out.exists():
        look.add(out, "image", "contact sheet made by ffmpeg alone (times burned in; no spoken words)")
        look.step("contact sheet (ffmpeg only)", "ffmpeg")
    else:
        look.fail("contact sheet", "ffmpeg", RuntimeError((r.stderr.decode("utf-8", "replace")[-120:] if r is not None else "failed")))


# ================================================================= audio
def look_audio(look, ffp=None):
    if not look.no_tools and ffp is None:
        prefetch_whisper(look)
    ffp = ffp if ffp is not None else ffprobe(look)
    if ffp is None:
        return audio_bare(look)
    streams = [s for s in ffp.get("streams", []) if s.get("codec_type") == "audio"]
    if not streams:
        look.flag("NO-AUDIO", "container", "ffprobe found no audio stream", "damaged file or not audio")
        return audio_bare(look)
    dur = duration_of(ffp)
    a = streams[0]
    look.fact("duration", round(dur, 2))
    look.fact("codec", a.get("codec_name"))
    look.fact("sample_rate", int(a.get("sample_rate", 0) or 0))
    look.fact("channels", a.get("channels"))
    look.headline = f"audio {core.mmss(dur)}, {a.get('codec_name')}, {a.get('sample_rate')} Hz, {a.get('channels')} ch"
    look.dims = f"{core.mmss(dur)}"
    look.line(f"Audio: {core.mmss(dur)} ({dur:.1f} s), {a.get('codec_name')}, {a.get('sample_rate')} Hz, {a.get('channels')} channel(s).", 80)
    look.write_text("probe.json", json.dumps(ffp, indent=1), "ffprobe facts", "json")
    res = one_pass_checks(look, False, True, dur)
    report_checks(look, res, dur)
    look.step("loudness and silence", "ffmpeg")
    ff = look.tool("ffmpeg")
    w = look.path_for("waveform.png")
    r = look.run([ff, "-y", "-v", "error", "-i", str(look.path), "-filter_complex", "showwavespic=s=2000x400:colors=#2a9d8f", "-frames:v", "1", str(w)])
    if r is not None and r.returncode == 0 and w.exists():
        look.add(w, "image", "waveform over the whole file (2000 px wide: time runs left to right)")
    s = look.path_for("spectrogram.png")
    r = look.run([ff, "-y", "-v", "error", "-i", str(look.path), "-lavfi", "showspectrumpic=s=2000x800:legend=0", "-frames:v", "1", str(s)])
    if r is not None and r.returncode == 0 and s.exists():
        look.add(s, "image", "spectrogram (frequency up, time right)")
    words = []
    found = False
    if look.quick:
        got = transcribe_sample(look, dur)
        if got is not None:
            write_transcript(look, got[0], got[1], dur, sampled=got[2])
            found = bool(got[0])
    else:
        wav = extract_wav(look, look.path, None if look.deep else ASR_CAP_S)
        if wav:
            got = transcribe(look, wav, dur)
            if got:
                words = write_transcript(look, got[0], got[1], dur)
                found = bool(got[0])
            if wav.stat().st_size < 50 << 20:
                look.add(wav, "internal", "16 kHz mono audio")
            else:
                wav.unlink(missing_ok=True)
    look.speech_found = found
    dl_mediax.bed_line(look, found)
    if not found:
        music_facts(look, dur)
    else:
        look.skip("tempo and key (music)", "speech found; run again on a music file for beat tracking", None, "")
    dl_mediax.loudness_line(look, audio_levels(look, dur), dur)
    dl_mediax.chapters_line(look, ffp)
    dl_mediax.audio_adapters(look, look.out / "audio.wav" if (look.out / "audio.wav").exists() else None, words, dur)
    look.skip("stems and notes (source separation, pitch tracking)", "not built: demucs and basic-pitch are not part of this version", None, "")
    look.ask_human("What language is it, and how many speakers?", "Is the tempo half or double what was found (music)?",
                   "Judgements of taste, voice quality or mix need a human listening: this look cannot hear.")


def music_facts(look, dur):
    lb = look.mod("librosa")
    if not lb:
        look.skip("tempo (beat tracking)", "librosa not importable" if not look.no_tools else "disabled by --no-tools", "librosa")
        return
    try:
        import warnings
        warnings.filterwarnings("ignore")
        y, sr = lb.load(str(look.path), sr=22050, mono=True, duration=60 if look.quick else 600)
        tempo, beats = lb.beat.beat_track(y=y, sr=sr, units="time")
        t = float(tempo[0] if hasattr(tempo, "__len__") else tempo)
        look.fact("tempo_bpm", round(t, 1))
        look.fact("beats", int(len(beats)))
        look.line(f"Music: tempo about {t:.0f} bpm ({len(beats)} beats found). Beat trackers often return half or double time: confirm by ear.")
        look.step("tempo", "librosa")
    except Exception as e:
        look.fail("tempo (beat tracking)", "librosa", e)


def audio_bare(look):
    """No ffmpeg: WAV header facts and a Pillow waveform from the PCM; other formats get a Not-looked-at row."""
    if look.subtype == "wav":
        try:
            with wave.open(str(look.path), "rb") as w:
                n, sr, ch, sw = w.getnframes(), w.getframerate(), w.getnchannels(), w.getsampwidth()
                dur = n / sr
                look.fact("duration", round(dur, 2))
                look.fact("sample_rate", sr)
                look.fact("channels", ch)
                look.line(f"WAV audio (header read with the standard library): {dur:.1f} s, {sr} Hz, {ch} channel(s), {sw * 8}-bit.")
                if sw == 2 and n < 60 * sr * 10:
                    data = array("h")
                    data.frombytes(w.readframes(n))
                    if ch > 1:
                        data = data[::ch]
                    pil = look.mod("PIL")
                    if pil:
                        draw_pcm_wave(look, data, sr, dur)
                    silent = silence_from_pcm(data, sr)
                    look.fact("silence", [[round(a, 2), round(b, 2)] for a, b in silent])
                    for a, b in silent:
                        look.flag("SILENCE", f"{core.mmss(a)} ({a:.1f}s)", f"{b - a:.1f}s near zero", "pause, dropout or missing audio")
        except (wave.Error, OSError, EOFError) as e:
            look.flag("WAV-ERROR", "header", str(e)[:100], "")
    elif look.subtype == "flac":
        try:
            with open(look.path, "rb") as fh:
                head = fh.read(42)
            if head[:4] == b"fLaC" and len(head) >= 42:
                v = int.from_bytes(head[18:26], "big")
                sr, ch, bps, total = v >> 44, ((v >> 41) & 7) + 1, ((v >> 36) & 31) + 1, v & ((1 << 36) - 1)
                if sr and total:
                    dur = total / sr
                    look.fact("duration", round(dur, 2))
                    look.fact("sample_rate", sr)
                    look.fact("channels", ch)
                    look.line(f"FLAC audio (STREAMINFO header read with the standard library): {dur:.1f} s, {sr} Hz, {ch} channel(s), {bps}-bit.")
        except OSError:
            pass
        if "duration" not in look.facts:
            look.line("Audio file (flac); details need ffmpeg.")
    else:
        look.line(f"Audio file ({look.subtype}); details need ffmpeg.")
    why = "disabled by --no-tools" if look.no_tools else "ffmpeg / ffprobe not found"
    for step, tool in (("loudness (LUFS), codec details", "ffmpeg"), ("spectrogram", "ffmpeg"), ("words with times (speech-to-text)", "faster_whisper"), ("tempo (music)", "librosa")):
        look.skip(step, why, tool)


def silence_from_pcm(data, sr, thresh=300, min_s=1.0):
    win = sr // 10
    out, start = [], None
    for i in range(0, len(data) - win + 1, win):
        ch = data[i:i + win]
        quiet = max(abs(min(ch)), abs(max(ch))) < thresh
        t = i / sr
        if quiet and start is None:
            start = t
        elif not quiet and start is not None:
            if t - start >= min_s:
                out.append((start, t))
            start = None
    if start is not None and len(data) / sr - start >= min_s:
        out.append((start, len(data) / sr))
    return out


def draw_pcm_wave(look, data, sr, dur):
    from PIL import Image, ImageDraw
    W, H = 2000, 400
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    n = len(data)
    for x in range(W):
        ch = data[x * n // W:(x + 1) * n // W + 1]
        if ch:
            lo, hi = min(ch), max(ch)
            d.line([x, H / 2 - hi / 32768 * H / 2, x, H / 2 - lo / 32768 * H / 2], fill=(42, 157, 143))
    p = look.path_for("waveform.png")
    im.save(p)
    look.add(p, "image", "waveform drawn from the PCM samples (no ffmpeg)")


# ================================================================= images
def look_image(look):
    if look.subtype == "psd":
        import dl_adapt
        dl_adapt.psd_extras(look)
    wh = core.image_size(look.path)
    st = look.subtype
    if st == "svg":
        return image_svg(look)
    pil = look.mod("PIL")
    if wh:
        look.fact("width", wh[0])
        look.fact("height", wh[1])
    if not pil:
        look.line(f"Image ({st}): {wh[0]}x{wh[1]} px (header read with the standard library)." if wh else f"Image ({st}); size unreadable without Pillow.")
        why = "disabled by --no-tools" if look.no_tools else "Pillow not importable"
        if wh and wh[0] * wh[1] > 2 * 89478485:
            look.flag("DECOMPRESSION-BOMB?", "header", f"{wh[0]}x{wh[1]} = {wh[0] * wh[1] / 1e6:.0f} megapixels", "the header claims a huge picture; it was not decoded")
        for step, tool in (("pixels: normalised picture, tiles, frames", "PIL"), ("EXIF details", "PIL"), ("text in the picture (OCR)", "tesseract")):
            look.skip(step, why, tool)
        look.ask_human("Can Pillow be installed (pip install pillow) so the picture can be resized for the model?")
        return
    from PIL import Image, ImageOps
    px = (wh[0] * wh[1]) if wh else 0
    if px > 2 * Image.MAX_IMAGE_PIXELS:
        look.flag("DECOMPRESSION-BOMB?", "header", f"{wh[0]}x{wh[1]} = {px / 1e6:.0f} megapixels", "the header claims a huge picture; it was not decoded")
        look.line(f"Image header claims {wh[0]}x{wh[1]} px ({px / 1e9:.1f} gigapixels): not decoded.")
        return
    try:
        with Image.open(look.path) as im:
            fmt, mode, size = im.format, im.mode, im.size
            frames = getattr(im, "n_frames", 1)
            look.fact("format", fmt)
            look.fact("mode", mode)
            look.fact("width", size[0])
            look.fact("height", size[1])
            look.fact("frames", frames)
            exif = im.getexif()
            look.line(f"Image {fmt}: {size[0]}x{size[1]} px, mode {mode}, {frames} frame(s).")
            info = exif_facts(look, exif)
            norm = ImageOps.exif_transpose(im.convert("RGBA" if "A" in mode else "RGB")) if exif.get(274, 1) != 1 or True else im
            if frames > 1:
                frame_sheet(look, im, frames)
            save_view(look, norm)
    except Image.DecompressionBombError as e:
        look.flag("DECOMPRESSION-BOMB?", "decode", str(e)[:100], "the picture is too large to decode safely")
        return
    except Exception as e:
        look.flag("IMAGE-ERROR", "decode", f"{type(e).__name__}: {e}"[:120], "the file is damaged or in an unsupported variant")
        return
    ocr_image(look)
    look.ask_human("Is the orientation right, and are any numbers or names in the picture going to be quoted (they must be checked by a person)?",
                   "May the EXIF details (device, time, location) be shared?" if look.facts.get("exif_private") else "What do you need to know about the picture?")


GPS_TAG = 34853


def exif_facts(look, exif):
    names = {271: "Make", 272: "Model", 305: "Software", 306: "DateTime", 274: "Orientation", 36867: "DateTimeOriginal", 42036: "LensModel", 42033: "BodySerialNumber"}
    priv = {}
    for k, label in names.items():
        v = exif.get(k)
        if v is None:
            try:
                v = exif.get_ifd(0x8769).get(k)
            except Exception:
                v = None
        if v is not None:
            priv[label] = str(v)
    gps = {}
    try:
        gps = dict(exif.get_ifd(GPS_TAG))
    except Exception:
        pass
    if gps:
        priv["GPS"] = {str(k): str(v) for k, v in gps.items()}
        look.flag("GPS", "EXIF", "location data present", "values are in look.json only; ask the owner before quoting or sharing them")
    if priv.get("Orientation") and priv["Orientation"] != "1":
        look.fact("exif_orientation", int(priv["Orientation"]))
        look.line(f"EXIF orientation {priv['Orientation']}: the picture was rotated upright before sending.")
        look.flag("ROTATED", "EXIF", f"orientation {priv['Orientation']}", "viewers differ; the saved view.png is upright")
    if priv:
        look.fact("exif_private", priv)
        look.line("EXIF present: " + ", ".join(k for k in priv if k != "GPS") + (" and GPS (values in look.json only)" if gps else "") + ".")
    et = look.tool("exiftool")
    if et:
        r, out, _ = look.run_text([et, "-j", "-G1", "-n", str(look.path)])
        if r is not None and out.strip():
            look.write_text("exif.json", out, "exiftool metadata (contains private details if present)", "json")
    else:
        look.skip("full metadata (exiftool)", "exiftool not found" if not look.no_tools else "disabled by --no-tools", "exiftool")
    return priv


def save_view(look, im):
    """Upright PNG, never upscaled, long edge at most the reader's edge; tiles when the original is bigger."""
    from PIL import Image
    edge = look.reader["edge"]
    w, h = im.size
    big = max(w, h) > edge
    v = im.copy()
    if big:
        k = edge / max(w, h)
        v = v.resize((max(1, int(w * k)), max(1, int(h * k))), Image.LANCZOS)
    p = look.path_for("view.png")
    v.save(p)
    look.add(p, "image", "upright picture" + (f", scaled down from {w}x{h} to fit {edge} px" if big else " at full size"))
    if big:
        look.flag("DOWNSCALED", "view.png", f"{w}x{h} -> {v.size[0]}x{v.size[1]}", "small text may be lost; read the tiles")
        tiles_of(look, im)


def tiles_of(look, im):
    w, h = im.size
    T, ov = 1400, 140
    out, idx = [], 0
    for y in range(0, h, T - ov):
        for x in range(0, w, T - ov):
            box = (x, y, min(w, x + T), min(h, y + T))
            t = im.crop(box)
            p = look.path_for(f"tiles/t{idx:03d}.png")
            t.save(p)
            out.append({"file": f"tiles/t{idx:03d}.png", "box": list(box)})
            look.add(p, "internal", "tile")
            idx += 1
            if idx >= 60:
                break
        if idx >= 60:
            break
    look.write_text("tiles.json", json.dumps(out), f"{len(out)} full-resolution tiles with their pixel boxes (10 % overlap)", "json")


def frame_sheet(look, im, frames):
    from PIL import Image
    n = min(9, frames)
    picks = [int(i * frames / n) for i in range(n)]
    ims = []
    for i in picks:
        im.seek(i)
        ims.append(im.convert("RGB").copy())
    tw = 600
    cols = 3
    th = int(tw * ims[0].height / ims[0].width)
    rows = math.ceil(n / cols)
    sheet = Image.new("RGB", (tw * cols, th * rows), "white")
    from PIL import ImageDraw
    d = ImageDraw.Draw(sheet)
    for i, f in enumerate(ims):
        x, y = (i % cols) * tw, (i // cols) * th
        sheet.paste(f.resize((tw, th)), (x, y))
        d.text((x + 6, y + 4), f"frame {picks[i]}", fill="red")
    p = look.path_for("frames.jpg")
    sheet.save(p, quality=88)
    look.add(p, "image", f"{n} of {frames} animation frames")
    im.seek(0)


def ocr_image(look):
    view = look.out / "view.png"
    tess = look.tool("tesseract")
    if tess and view.exists():
        r, out, _ = look.run_text([tess, str(view), "stdout", "--psm", "3", "tsv"])
        if r is not None and out.strip():
            look.write_text("ocr.tsv", out, "OCR words with confidence (tesseract, tsv)")
            words = [ln.split("\t") for ln in out.splitlines()[1:] if ln.count("\t") >= 11]
            text = " ".join(w[11] for w in words if len(w) > 11 and w[11].strip())
            low = [w for w in words if len(w) > 11 and w[11].strip() and float(w[10]) < 60]
            look.write_text("ocr.txt", text, "OCR text")
            look.fact("ocr_text", text[:1500])
            look.line(f"OCR (tesseract): {len(text.split())} words; {len(low)} below 60 % confidence. Numbers and symbols can be misread: confirm any quoted figure.")
            look.step("OCR", "tesseract")
            return
    rapid = look.mod("rapidocr_onnxruntime") or look.mod("rapidocr")
    if rapid and view.exists():
        try:
            eng = rapid.RapidOCR()
            res = eng(str(view))
            txt = " ".join(x[1] for x in (res[0] or [])) if isinstance(res, tuple) else ""
            look.write_text("ocr.txt", txt, "OCR text (rapidocr)")
            look.fact("ocr_text", txt[:1500])
            look.step("OCR", "rapidocr")
            return
        except Exception as e:
            look.fail("OCR", "rapidocr", e)
            return
    look.skip("text in the picture (OCR)", "tesseract and rapidocr not found" if not look.no_tools else "disabled by --no-tools", "tesseract")


def image_svg(look):
    text = open(look.path, "rb").read(2 << 20).decode("utf-8", "replace")
    m = re.search(r"viewBox=\"([\d.\s,-]+)\"", text)
    texts = re.findall(r">([^<>]{2,})<", text)
    vb = m.group(1) if m else ""
    look.fact("viewBox", vb)
    look.line(f"SVG vector picture, viewBox {vb or 'none'}; {len(re.findall('<path', text))} paths, {len(re.findall('<text', text))} text elements.")
    visible = [t.strip() for t in texts if t.strip() and not t.strip().startswith(("/*", "<!--"))]
    if visible:
        look.fact("svg_text", visible[:20])
        look.line("Text in the SVG: " + " | ".join(visible[:8]))
    if re.search(r"<script|onload=|javascript:", text, re.I):
        look.flag("ACTIVE-CONTENT", "svg", "script or event handler", "an SVG can run code in a browser; it was not rendered")
    core.scan_injection(look, text, look.path.name)
    look.write_text("svg.txt", text[:200000], "the SVG source as text")
    look.skip("rendered picture of the SVG", "no SVG renderer (cairosvg, inkscape, resvg) found; scripts in an SVG are never run", "cairosvg")
