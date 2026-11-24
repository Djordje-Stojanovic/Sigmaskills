# Long jobs on Colab: big uploads, streamed output, Windows programs

Seen in one run, 23 to 24 Nov 2026, on CPU High-RAM (0.26 units per hour; 1 h 45 min cost 0.40 units). A dated record, not a promise: check `colab <command> --help` before you rely on it.

## Files in

- The target path of `colab upload` starts with `content/` (`colab upload -s NAME local.zip content/local.zip`); without it the file lands somewhere else.
- `colab upload` can exit 0 and still print `Upload failed:`. Check the text, not only the exit code.
- A 1.6 GB archive failed as one plain upload. Split into 16 MiB parts, it went up in parallel, each part retried on failure, then joined on the runtime.
- A private repo goes up as a `git bundle`: no token reaches the runtime, so it cannot clone.

## Output back

`colab exec` returns what the cell prints. A long child process has to be streamed through the cell's stdout, or nothing comes back:

```python
p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
for line in p.stdout:
    sys.stdout.write(line); sys.stdout.flush()
```

## A Windows program under Wine

A Windows game from 2001 reached its menu in 10.2 s under Wine 9.0 on Ubuntu 24.04 with:

- `vc_redist.x86` (for `mfc140.dll`);
- `libgl1:i386` and `libgl1-mesa-dri:i386` (DirectDraw), and the DirectDraw renderer set to `gdi` (`HKCU\Software\Wine\Direct3D`, `DirectDrawRenderer`);
- a PulseAudio null sink as the default sink (DirectSound), with Wine's audio driver set to `pulse`;
- `Xvfb :N -screen 0 1024x768x16`, and the program started in `wine explorer /desktop=NAME,1024x768`.

## A Windows test suite on Linux

Take a baseline on the runtime before the first change. One suite gave 589 passed on Windows and 311 passed, 275 skipped, 3 failed on the runtime: 275 tests needed Windows binaries, 1 compared paths with backslashes, 2 depended on the order the tests ran in. Name each such test once as `windows-only` with its reason, then compare every later run against that baseline.
