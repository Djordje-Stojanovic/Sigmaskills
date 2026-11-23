# Cards and prices: Colab rates, the one-minute test, Vast

What one Google AI Ultra account saw. A dated record, not a promise: Colab changes cards, rates and capacity without notice, so read `colab --auth adc usage` live and add what you measure here.

Units per hour: the change in `usage`'s rate when the runtime started. Start: from `colab new` to a ready runtime. Test, 23 Nov 2026, Vienna: one minute of device list and a timed matrix multiply per card, then `stop` and `colab sessions` without the name. Six runtimes of other jobs ran on the account at the same time.

| Card | Units/h | Started | Start | Memory | One minute |
|---|---:|---|---:|---|---|
| CPU | 0.08 | yes | 19.7 s | 2 cores, 12 GiB | 48 GFLOP/s fp32 |
| CPU High-RAM | 0.26 | yes | 7.9 s | 8 cores, 50 GiB | 319 GFLOP/s fp32 |
| T4 | 1.15 | yes | 7.8 s | 15 GiB GPU, 12 GiB host | 22.3 TFLOP/s fp16 |
| T4 High-RAM | 1.57 | not tested | | | |
| L4 | 1.94 | no: "Allocation refused (precondition failed)", then "Service Unavailable" | | | |
| A100 40 GB | 6.73 | no: "Service Unavailable" twice | | | |
| A100 80 GB / High-RAM | 8.88 | not tested | | | |
| H100 | unknown | no: "Service Unavailable" twice | | | |
| G4 (RTX PRO 6000) | unknown | no: "Service Unavailable" twice | | | |
| TPU v5e-1 | 3.09 | yes | 277 s | 15.7 GiB HBM, 47 GiB host | 177.5 TFLOP/s bf16 |
| TPU v6e-1 | 5.09 | no: the CLI's request timed out (120 s, then 600 s) | | | |

Rates of cards that did not start today (L4, both A100s, T4 High-RAM, v6e-1) are from 20 Nov 2026 runs on the same account. The four cards that started cost about 0.34 units together.

## vast.ai

Seen in October 2026, a speed loop on one GB10 (`cpu_arch=arm64`): $0.28-0.42 per hour; a 40-minute experiment cost about $0.20. Read live prices with `vastai search offers ... -o dph_total`.
