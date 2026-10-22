# Audio

An agent cannot hear. `look.py` turns audio into numbers, text and two pictures. Do not claim "sounds good", a voice's quality or a music taste from them. On the MMAU benchmark audio-language models scored about 53 percent against 82 for humans, lowest on music.

## When look.py is not enough

- Taste, voice identity, mix balance, emotion: a human listens, or a model that takes audio (Gemini) does, with the human's yes because the file leaves the machine.
- Speakers (who said what), overlapping speech and a language other than the first guess: ask the human for the language and a glossary of names; diarization needs a gated model and a token, which this skill never downloads.
- Music beyond tempo (key, chords, stems, notes): not in v1. Say so under Limits.
- Sound effects: no label model is bundled. Describe the waveform and spectrogram, and ask.

A `Sound activity` line counts the bursts of sound over the quiet floor (beeps, knocks, alarms, words): how many, when each starts and ends, the strongest frequency of each, and when the last one ends. Sun/NeXT `.au` files are read from their own header. Over 30 minutes it says it read the first 30 and flags `PARTIAL`.

## Pipeline

1. Facts: `ffprobe` (codec, rate, channels, bit rate, tags). No ffprobe: WAV header and FLAC STREAMINFO read with the standard library, plus a PCM waveform drawn with Pillow.
2. Loudness and gaps in one ffmpeg pass: integrated LUFS, loudness range and true peak, with the EBU R128 target as the yardstick (-23 LUFS, peak at most -1 dBTP). `silencedetect` (-50 dB, 2 s) gives SILENCE flags with times. A peak near 0 dBFS gives a LOUD-PEAK flag.
3. Pictures at 2000 px: `waveform.png` and `spectrogram.png` (frequency up, time right). A spectrogram shows a cut-off at 16 kHz, a hum line, a dropout band, clipping.
4. Speech: faster-whisper offline (`vad_filter=True`, `condition_on_previous_text=False`, word times) writes `words.json` and `transcript.srt`. The model must be cached.
5. Music: librosa `beat_track` with `sr=None` writes the tempo. A tempo is a guess: it is often half or double the felt one.

## Failure modes

- Whisper invents "Thank you for watching" over silence and repeats one line forty times when conditioning is on. Both are switched off; still treat a line over a silent stretch as suspect.
- Utterance times can be wrong by seconds; tokens like "2014." or "13.60" get no word time.
- Tempo octave errors (60 vs 120 bpm). Report the tempo with "may be half or double".
- librosa resamples to 22,050 Hz unless `sr=None`; a sample-rate mismatch silently lowers any classifier.
- A transcript from a noisy phone recording can be fluent and wrong. Quote it with its time, and ask before using a number or name from it.

## Show the human

The transcript with times; low-confidence or repeated lines; proper names heard below 0.6 confidence marked `Name(?)` in every text you read, listed with time, confidence and the similar-sounding spellings elsewhere in the transcript (`NAME-SPELLING` when one name is written two ways): quote such a name with its `(?)` until the audio or a written source confirms it; the silence stretches; the loudness table; the language and probability; the tempo with its octave caveat; the waveform and spectrogram. Ask: the language, the number of speakers, a glossary, which stretch to listen to (give three: the quietest, the loudest, a random one), and whether sound judgement is needed.

## Install (Win/Linux/macOS)

- ffmpeg: `winget install Gyan.FFmpeg` / `sudo apt install ffmpeg` / `brew install ffmpeg`.
- Pillow: `pip install pillow`. Speech: `pip install faster-whisper`. Tempo: `pip install librosa`.
- `python look.py doctor` lists what is present.
