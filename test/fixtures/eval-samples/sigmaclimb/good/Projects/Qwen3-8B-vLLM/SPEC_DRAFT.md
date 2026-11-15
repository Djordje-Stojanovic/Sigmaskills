# SPEC_DRAFT - Qwen3-8B on vLLM, one RTX 4090 (Vast.ai)

## What faster means
1 stream short decode first, then warm agent turns, then long thinking, then prefill. Weights in project.json.

## What no quality loss means
Same weights, same precision, the owner's sampler. The fidelity gate rejects drift beyond the A/A band.

Ruling: the recommended answers were taken for every question - offline eval, no question round.
