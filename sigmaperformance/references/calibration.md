# Calibration contract

## Contents

1. Rules
2. Batch 1 — authority and safety
3. Batch 2 — performance and workload

## Rules

Ask two concise batches with recommended defaults and free-text override. Do not inspect or execute the repository beyond resolving its identity before Batch 1. Agent topology is the first question; until answered, use one agent.

## Batch 1 — authority and safety

Ask at most four grouped questions:

1. **Agent topology**
   - A — Single agent ⭐
   - B — Bounded specialist subagents under primary ownership
   - C — Custom named topology and concurrency
2. **Execution mode**
   - A — Source-led
   - B — Existing safe environment; install nothing ⭐
   - C — Isolated measured execution using project-declared dependencies
   - D — Custom
3. **Stress and external evidence**
   - Stress: none ⭐ / existing suite / bounded resource-capped local probe / exact user-defined load
   - Evidence: repository only / supplied sanitized artifacts ⭐ / separately authorized read-only systems / custom
4. **Forbidden actions and limits**
   - production/shared systems, paid APIs, network, installation, containers, secrets;
   - maximum runtime, cost, CPU/GPU/memory/storage use;
   - any repository-specific prohibition.

Explain that isolated execution does not authorize stress testing, external effects, production access, or uncontrolled cost.

## Batch 2 — performance and workload

Tailor this batch to Batch 1, then ask at most four grouped questions:

1. **Priority ranking:** latency/responsiveness ⭐, capacity, resource-pressure reliability, CPU/GPU/memory/I/O, cost, startup, frontend, build/CI.
2. **Primary workflow:** supplied by user / infer / user target plus repository-wide discovery ⭐.
3. **Scale and environment:** representative dataset; normal/peak concurrency; target hardware, OS/runtime/deployment; cold/warm/cache expectations; forbidden workloads.
4. **Budgets and evidence:** p50/p95/p99 or other budgets; capacity/resource/cost budgets; known complaints; available profiles/traces/plans/benchmarks; permission to infer gaps.

Construct four workload tiers: Primary, Critical, Representative, and Stress boundary. The stress tier is a model unless separately authorized for execution. After the answer, state a compact resolved contract and begin autonomously.
