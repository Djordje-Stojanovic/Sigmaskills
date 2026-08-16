---
name: la284 Entrpi cutover
overview: Overwrite the old May antirez `la284` tree on gx10-c956 with Entrpi ds4 v0.5.6.3 + DeepSeek-V4-Flash-0731, keep public model id `qwen` at `:8000` for Pi, smoke-test only. Benches and Q4 are out of scope for this cutover.
todos:
  - id: wipe-install
    content: Stop la122, wipe Test-Deepseek-V4-Flash, install Entrpi v0.5.6.3 + 0731 + DSpark into that root
    status: completed
  - id: qwen-cuda-spark
    content: Apply qwen alias patch; rebuild with make cuda-spark; rewrite live la284 to -c 262144 + DSpark
    status: completed
  - id: smoke
    content: la284 + lawait; confirm /v1/models id qwen; one Pi chat turn
    status: completed
isProject: false
---

# la284 Entrpi 0731 cutover (smoke-only)

## Decisions locked

- **Engine:** [Entrpi/ds4](https://github.com/Entrpi/ds4) **v0.5.6.3** via [ds4-on-spark](https://github.com/Entrpi/ds4-on-spark) installer (not stock antirez).
- **Weights:** ship **0731 IQ2XXS** + matching **DSpark** drafter (~91 GiB). Full Q4 / MXFP4 do not fit one 128 GB Spark; issue #41’s Q4 dream stays a later follow-up.
- **Layout:** **overwrite** — delete old `~/Test-Deepseek-V4-Flash` contents; reinstall into that root (keep `LA284_ROOT` / `la284` name).
- **Context:** Entrpi Spark default **`-c 262144`**.
- **Public model id:** **`qwen`** via the existing string rewrite in `ds4_server.c` (alias only; model is still DeepSeek Flash).
- **Done gate:** smoke only (`/v1/models` + one Pi turn). Albond / tool-eval later if you want.
- **Live now:** Spark is on **la122** (vLLM). Cutover stops it for the install window.

## What “qwen patch” does (kept)

Entrpi advertises `deepseek-v4-flash`. Pi expects `qwen`. After install, re-run the same approach as today’s `_la_patch_ds4_qwen` in [`lazy_toolkits/spark-gx10-c956.bashrc`](https://github.com/Djordje-Stojanovic/Thinkcenter_Setup/blob/main/lazy_toolkits/spark-gx10-c956.bashrc): replace `deepseek-v4-flash` → `qwen` in `ds4_server.c`, then rebuild with **`make cuda-spark`** (not plain `make … CUDA_ARCH=sm_121` — that was the slow path).

## Cutover steps (Spark)

1. **Stop serving:** `lastopall` (frees RAM from la122).
2. **Wipe old tree:** remove `~/Test-Deepseek-V4-Flash` contents (old May antirez binary + pre-0731 81G GGUF + kv).
3. **Install Entrpi** with env pointing at that root, e.g. `DS4_SRC_DIR=…/code/ds4`, `DS4_GGUF_DIR=…/gguf`, pin `DS4_REF=v0.5.6.3`, run official `install.sh` (omit `--start` if you want to patch before first serve). Expect long download.
4. **Verify build:** boot log / `cuobjdump` shows Spark path (`sm_121a` / aligned Q8 artifacts). Rebuild with `make cuda-spark` if the install landed generic CUDA.
5. **Apply qwen alias + rebuild** (`make cuda-spark`).
6. **Rewrite live `la284` start** so it:
   - loads `…-imatrix-0731.gguf` + DSpark drafter (via `ds4-serve` or equiv. `DS4_CONT_DSPARK` / `DS4_DSPARK_MODEL`)
   - uses `-c 262144 --host 0.0.0.0 --port 8000`
   - keeps disk KV under `$root/kv` if still useful
   - runs the qwen patch before start
7. **Smoke:** `la284 && lawait` → `curl …/v1/models` shows **`qwen`** → one Pi chat turn against existing `qwen` provider.
8. **Leave benches optional** — you run `labenchmarkalbond` / `labenchmarktooleval --mini30` when you want.

## Toolkit / docs (minimal for this gate)

- Update **live** `~/.bashrc` `la284` path so smoke works.
- **Do not block** on committing Thinkcenter_Setup tracked bashrc/docs for gate A; sync later when you want `lasynctoolkit` to match (recommended soon after so the May antirez launcher cannot resurrect).

## Explicitly out of scope

- Q4 / MXFP4 on one Spark
- Albond / tool-eval / SWE-bench
- Changing Pi model configs (kept via `qwen` alias)
- Switching daily default off la122 permanently (this only upgrades the retained `la284` lane)

## Success criteria

- `ds4-server` / `ds4-serve --version` reports Entrpi **v0.5.6.3** (or installer pin).
- Weights are **0731** + DSpark drafter present.
- `GET :8000/v1/models` → id **`qwen`**.
- One Pi turn completes without client config changes.
