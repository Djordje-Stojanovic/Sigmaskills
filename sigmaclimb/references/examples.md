# Examples: the seven parts, filled in

Examples, not a list of cases: a new goal does not need to fit a row. Each row fills the same seven parts. The noise,
budget and stop rule follow the defaults of `interview.md` unless the row says otherwise.

| Field | Target | Score | Guards | Measurer | Notes |
|---|---|---|---|---|---|
| Game frame rate | engine settings, shaders, the render code | frames per second on a fixed camera path; 1 % low frame time | a frame comparison against the start (seconds per check); input latency | a script that plays the path and reads frame times | warm the shader cache the same way for both sides; one probe uses a camera path made fresh each run |
| A film's look | the grade, the LUT, the denoise and sharpen steps | share of blind pairs the new look wins | runtime and resolution unchanged; no banding | the owner picks between two stills or clips, blind; a judge model only where he allows it | the interview question "which is better, and what did you look at?" becomes the fixed pair question |
| A book | one chapter's text, one change per pass | share of blind pairs a reader prefers | every fact of the source kept; length within 10 % | the owner, or a judge he accepts, reads pairs of the same passage | the guard against lost facts is a script that checks names, numbers and dates |
| Video file size at the same quality | encoder settings, the encode pipeline | bytes per minute of video (lower is better) | a perceptual quality metric (VMAF, SSIM) within the noise of the start; encode time | a script: encode, measure size, measure quality | size is the score, quality is the guard: the reverse of a speed loop, same seven parts |
| Video render time | the render pipeline, its settings and code | seconds per finished minute | the frames match the start within a pixel metric | a script that renders a fixed timeline | one probe renders a timeline it has never seen |
| A build | the build graph, caching, the compiler flags | wall time of a clean build and of a one-file change | the binaries pass the test suite; output size | a script that builds both ways | cold and warm builds are two probes, on purpose |
| A served model | the engine's launch recipe and its code | decode, prefill, parallel streams, agent turns, first-token time | the output stays the same within its noise (logprobs, a task suite) | the template's scripts | the worked example: `example-model-serving.md` |
