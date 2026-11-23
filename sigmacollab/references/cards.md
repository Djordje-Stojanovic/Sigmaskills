# Cards and prices: Colab rates, the one-minute test, Vast

What one Google AI Ultra account saw. A dated record, not a promise: Colab changes cards, rates and capacity without notice, so read `colab --auth adc usage` live and add what you measure here.

Units per hour: the change in `usage`'s rate when the runtime started. Start: from `colab new` to a ready runtime. Test: one minute of device list and a timed matrix multiply per card, then `stop` and `colab sessions` without the name. 23 Nov 2026, Vienna, with six runtimes of other jobs on the account; 24 Nov 2026 for the cards marked so. On 24 Nov `usage` listed every card as eligible (GPUs H100, G4, A100, L4, T4; TPUs V6E1, V5E1), balance 2559.91 units.

| Card | Units/h | Started | Start | Memory | One minute |
|---|---:|---|---:|---|---|
| CPU | 0.08 | yes | 19.7 s | 2 cores, 12 GiB | 48 GFLOP/s fp32 |
| CPU High-RAM | 0.26 | yes | 7.9 s | 8 cores, 50 GiB | 319 GFLOP/s fp32 |
| T4 | 1.15 | yes | 7.8 s | 15 GiB GPU, 12 GiB host | 22.3 TFLOP/s fp16 |
| T4 High-RAM | 1.57 | yes (24 Nov) | 6 s | | 21.8 TFLOP/s fp16 |
| L4 | 1.94 | yes (24 Nov) | 6 s | | 54.6 TFLOP/s fp16 |
| A100 40 GB | 6.73 | no (24 Nov): "Service Unavailable", gave up at 196 s, also with `--public-api` | | | |
| A100 High-RAM (`--high-mem`) | 8.88 | no (24 Nov): "Service Unavailable", gave up at 196 s, also with `--public-api` | | | |
| A100 80 GB | | not tried | | | |
| H100 | unknown | no (24 Nov): "Service Unavailable", gave up at 196 s, also with `--public-api` | | | |
| G4 (RTX PRO 6000 Blackwell) | 10.05 | yes (24 Nov) | 6 s | 95 GiB GPU | 404.5 TFLOP/s fp16 |
| TPU v5e-1 | 3.09 | yes | 277 s | 15.7 GiB HBM, 47 GiB host | 177.5 TFLOP/s bf16 |
| TPU v6e-1 | 5.09 | no (24 Nov): no answer in 330 s; with a 300 s request timeout, "Bad Gateway" after 493 s | | | |

The A100s and the H100 look like capacity, not the plan: unproven. The CLI can hang for minutes on a card that does not come: give the request a long timeout, and pick a second card before you start. Rates of A100 40 GB, A100 High-RAM and v6e-1 are from 20 Nov 2026 runs on the same account. The four cards that started on 23 Nov cost about 0.34 units together.

## vast.ai

Seen in October 2026, a speed loop on one GB10 (`cpu_arch=arm64`): $0.28-0.42 per hour; a 40-minute experiment cost about $0.20. Read live prices with `vastai search offers ... -o dph_total`.
