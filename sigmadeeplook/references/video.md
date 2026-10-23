# Video

Claude and Codex take pictures, not video. Only Gemini accepts a video file. So `look.py` turns the video into machine facts, a timed transcript and a few pictures, all kept on disk. You read them in small steps.

## When look.py is not enough

- Sound judgement (voice quality, music taste, mix) and motion judgement (smoothness, a fast cut) need ears and eyes on motion. This look cannot hear or watch. Say so under Limits and ask the human, or use a model that takes audio and video, only with the human's yes because the file leaves the machine.
- One sheet covers one tile per `duration / 9` seconds. For anything over 3 minutes run `--mode sweep` (more sheets, never more tiles per sheet), then `--at T --len S` on every flagged or doubtful span.
- Text smaller than about 30 px on a 1080p frame is lost in a 3x3 sheet. Use a zoom window for text.

## Pipeline

1. Facts, no AI: `ffprobe` JSON (`probe.json`): duration, streams, codecs, fps, size. A `Stream table` line gives each stream's container id (PID of a transport stream, track id of an MP4), type, codec, language and bit rate; `Tone per audio stream` gives the steady pitch of every audio stream. Without ffprobe a transport stream's PAT and PMT are read with the standard library, so the PIDs are still printed. No ffprobe: container atoms read with the standard library (duration, streams, a cut file).
2. One ffmpeg pass: `blackdetect`, `freezedetect`, `silencedetect`, `ebur128` (integrated LUFS, range, peak) become Flags with times. A black or silent stretch is a hint, not a verdict. A `Clock:` line gives the container start, every stream start and the first video frame; black and frozen spans are told from the first video frame (with the container time beside them), silence spans from the container start.
3. Words: embedded subtitle streams first (`subtitles.srt`), else faster-whisper offline from a cached model with `vad_filter=True` and `condition_on_previous_text=False` (`words.json`, `transcript.srt`). A model that is not cached becomes a Not-looked-at row, never a download.
4. Cuts: ffmpeg scene score above 0.4 (`scenes.csv`); PySceneDetect when installed. Scene starts are extra tile sources.
5. Sheet: tiles at slot centres `(i+0.5)*D/N`, the sharpest frame near each slot, a burned M:SS and the spoken words under each tile, a loudness strip, flagged stretches as extra tiles. Default 3x3 at 2000 px, full detail (`sheet-overview.jpg`): about 1.6k tokens on the standard vision tier, about 3.5k on the high-resolution tier. `--query "words"` moves the slots toward where those words are spoken, and a third of the tiles stay evenly spread. No Pillow: an ffmpeg `fps=` and `tile` sheet.
6. `--mode sweep` writes `sheet-sweep-N.jpg`, one page per 3 minutes. `--at T --len S` writes `sheet-window-<T>s.jpg` for that span with finer tiles.

## Failure modes

- `select='not(mod(t,5))'` returns one frame on a 29.97 fps clip; sampling uses `fps=N/D`. `-vsync` no longer exists in recent ffmpeg; `-fps_mode` is used.
- Keyframe spacing, not content, decides how many I-frames a clip has, so I-frame sampling is never used alone.
- A cut file with an intact header (`moov` first) still reports its full length. The container check flags `TRUNCATED` when an atom runs past the end.
- Whisper writes lines such as "Thank you for watching" over silence. The voice-activity filter removes most of them; treat a line with no sound under it as suspect.
- Never judge from one frame or one transcript line. A claim about a range needs tiles from both ends and the middle.
- Long-video benchmarks are often answerable from one frame, so a confident description of a long video is not proof. Spot-check.

## Show the human

The Flags list (time, kind, value) with the tile that confirms each; the sheet path; the transcript lines behind each claim; the reader preset and image sizes used; which judgements need ears or motion. Ask: is a black or silent stretch a designed card or a defect; which moments or claims need a zoom window; which reader (`claude`, `claude-hires`, `gemini`, `small`) is in use.

## Install (Win/Linux/macOS)

- ffmpeg and ffprobe: `winget install Gyan.FFmpeg` / `sudo apt install ffmpeg` / `brew install ffmpeg`.
- Pillow: `pip install pillow`. Speech: `pip install faster-whisper` (the model must already be in the local cache; first download needs `--allow-network` and the human's yes).
- Optional: `pip install scenedetect[opencv]`.
- `python look.py doctor` lists what this machine has.
