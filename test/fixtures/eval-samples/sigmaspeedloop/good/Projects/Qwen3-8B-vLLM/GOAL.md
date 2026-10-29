# GOAL.md - Qwen3-8B speed loop on Vast.ai (run file: re-read at the start of EVERY turn)

Host: Claude Code /goal. Stop line: the owner destroys the Vast instance. Spec: `SPEC_DRAFT.md`.

## Mission
Make Qwen3-8B on vLLM faster (decode, prefill, agent turns, parallel requests) on one rented RTX 4090, with zero
loss in quality, measured under the owner's real settings. One change per pass; keep it only if
`scripts/bench/verdict.py` says KEEP and a confirmation run agrees.
