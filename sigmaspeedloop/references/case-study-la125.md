# Case study: la125 (Qwen3.8-Flash-Next 125B NVFP4 + MTP) on a Vast GB10, 2026-10-22 to 10-26

The project folder held `GOAL.md`, `PROGRESS.md`, `results.tsv`, `ruled_out.tsv`, `insights.md`, `champion/`, `docs/07-19` research.
Use it as a worked example and as a starting idea list for similar stacks: GB10 / DGX Spark, vLLM forks with b12x
kernels, hybrid GDN/attention MoE, MTP speculative decoding, n-gram (PLE) embedding tables on disk.

## Setup
- Model: nvidia/Qwen3.8-Flash-Next-FP4-Local @ b9ce18a + Loke abliterated shards (2 of 21), served as `qwen`.
- Image: eugr/spark-vllm-b12x:nightly-20261015. Box: Vast GB10, $0.29-0.39/h, 350 GB. Two boxes were used
  (the owner destroyed the first; the second needed a new baseline and new references).
- Invariants: GMU 0.75, max_model_len 262144, max_num_seqs 8, fp8 KV, sampling T1/0.95/20, thinking on.
- Owner use: coding agents + a chat web UI, 1-3 streams, 10k-200k context, effort low/medium (sometimes xhigh),
  max_tokens 65536. Priority: 1 stream > 2 > 3 > 4 agents; prefill = decode.

## Result: champion #9 after about 110 runs (evaluator v8), same box and weights, same quality gate
| Metric | Owner's home recipe | Champion #9 (median of 3 runs) | Change |
|---|---|---|---|
| short decode, 1 stream | 52.4 tok/s | 60.8 | +16 % |
| long thinking (64k, xhigh) | 36.4 tok/s | 47.4 | +30 % |
| prefill 64k | 1706 tok/s | 2249 | +32 % |
| first token at 128k | 78.0 s | 58.6 s | 25 % less time |
| 3 agents (aggregate) | 84.5 tok/s | 107.6 | +27 % (the probe swings about 10 %) |
| warm agent turn, first token | 4.48 s | 1.86 s | 58 % less time |
| warm prefix-cache hit rate | 0.924 | 0.973 | better |
| quality | ToolEvalBench 84/100, needles 4/4 | 83/100, needles 4/4 | equal, no empty or looping output |

On the owner's own Spark the same recipe measured short decode +9.7 %, long thinking +34 %, prefill +15 % and warm
agent first token -53 % against the home baseline (home io_uring and warm caches made that baseline faster).

Champion path: #1 page-cache PLE reads -> #2 allocator GC + mbt 4096 -> #3 CSF-inline MoE decode ->
#4 probabilistic MTP drafting -> #5 GDN deferred commit + 64k draft vocabulary -> #6 MTP n=5 ->
#7 recurrent-prefill tail stride 256 (fork PR #1034; warm agent TTFT 5.3 -> 2.6 s) -> #8 GDN commit async
(owner accepted 2 agents +9 % vs long thinking -3 %) -> #9 tail stride 32 (warm agent first token
another -13 %). `state/champion.md` lists each with its runs.

## What won, and why (general)
| Change | Effect | Numerics |
|---|---|---|
| PLE/n-gram table through the page cache (pread patch, O_DIRECT off) | prefill +17 %, replay +13 % | identical |
| allocator GC env + `--max-num-batched-tokens 4096` | prefill +15 % more | drift, owner accepted (tools up) |
| CSF-inline MoE decode patch | decode +5 % | bit-identical |
| probabilistic MTP drafting | long thinking +14 % | lossless |
| GDN deferred commit + 64k draft vocab | long +11 %, 3 agents +8 % | lossless |
| MTP drafts 4 -> 5 | replay +12 % | lossless |
| tail stride 256 | replay +11 %, warm TTFT halved | lossless |

## What lost
- Kernel work: roofline said matmuls sit at 81-95 % of the *measured* 240 GB/s ceiling. BF16 GEMV, shared-expert
  stream, MHC PDL, L2 prefetch, DFlash2 drafter (acceptance 0), history-copy drafts, depth controller: all
  rejected or neutral.
- Bundles of small lossless changes lost twice (replay -11 %, -9 %).
- Trades parked for the owner: block verification, attention-quant fusion, GDN verify flat (replay up, 3 streams
  or long thinking down).
- Flags already default-on in the image: CUDA graph mode, custom ops, three NVIDIA "speed" envs, FlashInfer
  sampler, async scheduling.
- `VLLM_USE_BREAKABLE_CUDAGRAPH=0` failed the quality gate.

## What it taught about process
Noise bands on 2-3 stream probes are about 10 %; every KEEP needed a confirmation; profiling found the 10 %
tail step in prefill that no guess would have found; the queue sorted by success probability; outside research
models gave the best kernel ideas; the owner steered with tables and rulings. See `lessons.md` part 2.

## Transfer notes for the owner's own machine
- Allocator env + mbt 4096: two recipe lines; fixes the home start crash at 4096.
- Page-cache PLE needs the patched reader; home uses io_uring (also O_DIRECT), so test it there separately.
- The home recipe's `B12X_W4A16_A4_PREFILL=1` was not the cause of the 4096 drift. Turning A4 off cost prefill -7 %.
