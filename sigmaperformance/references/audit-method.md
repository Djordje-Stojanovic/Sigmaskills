# SigmaPerformance audit method

## Contents

1. Frame and inventory
2. Journey and bottleneck map
3. Measurement plan
4. Ten investigation lenses
5. Falsification and synthesis
6. SigmaOptimize handoff

## 1. Frame and inventory

Record repository/ref/SHA, languages, size, packages, runtime entry points, deployments, data stores, queues/caches, external services, user surfaces, tests/benchmarks, telemetry hooks, CI/build, hardware assumptions, generated/vendor/binary surfaces, and complete tracked-file accounting.

Read requirements, README, ADRs, schemas, routes, manifests, deployment configuration, benchmark history, performance incidents, and current official documentation needed for versioned claims. Documentation is evidence, not truth.

## 2. Journey and bottleneck map

Trace each primary/critical journey:

```text
user or caller → frontend/CLI/device → client work → network/protocol
→ routing/middleware → application logic → database/cache/queue/external service
→ serialization/response → render/commit/completed outcome
```

For each edge record work, waiting, data volume, fan-out, resource ownership, synchronization, caching, failure/retry, observability, and measurement point. Identify whether the limiting resource is latency, throughput, CPU, accelerator, memory, storage, network, database, contention, external quota, cost, startup, or coordination.

## 3. Measurement plan

Match evidence to the question:

- End-to-end latency/throughput: representative journey benchmark or trace.
- CPU/GPU: sampling/instrumented profiler and hardware counters where justified.
- Memory: allocation/retention profile, peak/RSS/device memory, lifetime.
- Database: query count, timings, plans, cardinality, locks, pool metrics.
- Frontend: field telemetry when supplied; controlled lab traces otherwise.
- Distributed systems: traces, queue/service metrics, saturation curves.
- Startup/build/CI: cold controlled wall/CPU/I/O and critical-path analysis.

Define baseline, workload, controls, trials, correctness oracle, metrics, uncertainty, stop condition, and permitted resources before executing. Never change methodology between comparisons.

## 4. Ten investigation lenses

### 1 — Algorithmic work and data movement

Find repeated scans/parsing/serialization/hashing/copying; pathological complexity; unbounded collections; eager work; poor data structures; unnecessary materialization; oversized payloads; missing batching, streaming, pagination, or backpressure. Prove bounds and reachability.

### 2 — Database and persistence

Find N+1/loop queries, round trips, bad/missing indexes, plan/cardinality problems, overfetch, long transactions/connections, pool exhaustion, lock contention, chatty ORM patterns, ineffective pagination, write amplification, migration-induced cost, and cache/database inconsistency overhead.

### 3 — Concurrency, async, queues, and distributed paths

Find independent operations serialized unnecessarily, excessive fan-out, sync work in async paths, critical-section inflation, contention, head-of-line blocking, retry amplification, queue growth, missing flow control, thread/task/process churn, and coordination overhead. Never recommend concurrency without ordering, resource, and failure analysis.

### 4 — CPU, accelerator, and hardware efficiency

Inspect hot instructions/functions, vectorization, branching, allocation, kernel launch, transfers, synchronization, batching, occupancy/utilization, precision, locality/NUMA, memory bandwidth, device placement, and thermal/power modes. Preserve numerical quality and determinism contracts.

### 5 — Memory and resource lifetime

Inspect leaks/retention, unbounded caches/queues/maps, avoidable large objects, copies, fragmentation, GC pressure, buffering, descriptors/handles/connections, peak versus steady state, device memory, and memory preventing startup/scale.

### 6 — Network, I/O, files, protocols, and external services

Inspect round trips, handshake/reconnect, blocking I/O, small operations, buffering, compression, payload/schema bloat, file rereads, fsync, logging volume, DNS/TLS, rate limits, external latency/cost, timeout/retry, and partial responses.

### 7 — Cache and deferred work

Inspect key quality, hit/miss evidence, invalidation, TTL, stampede, negative caching, serialization cost, authorization sensitivity, prefetch, memoization, lazy loading, background work, and whether caching merely hides a wrong algorithm.

### 8 — Frontend and perceived performance

Inspect LCP/INP/CLS, main-thread blocking, hydration, rerenders, state subscriptions, layout/style thrash, waterfall requests, bundle/code split, images/fonts, event handlers, loading states, navigation, caching, and device/network sensitivity. Separate field and lab truth.

### 9 — Startup, build, CI, deployment, and cost

Inspect imports/module loading, initialization, discovery, cold compilation, artifact size, dependency/tool duplication, incremental caching, parallel critical path, container/image startup, autoscaling, readiness, serverless cold start, idle resources, capacity configuration, and paid-service economics.

### 10 — Domain overlay and saturation

Apply repository-specific expertise: real-time/safety deadlines; embedded/RTL timing and bandwidth; AI inference/training quality-throughput-memory; media frame/encode pipelines; game frame-time tails; HPC scaling/communication; mobile battery/thermal; data pipelines freshness/backpressure. Build saturation curves only when authorized.

## 5. Falsification and synthesis

For every candidate ask:

- Is this on a reachable important path?
- Is it actually limiting end-to-end outcome or merely visible?
- Is work required by the product contract?
- Is a guard/cache/batch/compiler/runtime already eliminating it?
- Would the proposed direction shift cost elsewhere?
- Does evidence survive representative scale and cold/warm regimes?
- Can another bottleneck absorb the gain?
- Are correctness, security, quality, compatibility, and operability preserved?

Classify M1/M2/M3/boundary, deduplicate root causes, order dependencies, and retain only high-signal items. Record measured unsuccessful experiments only when methodology and future value justify them.

## 6. SigmaOptimize handoff

Every item contains: ID; evidence class; workflow and operating range; current behavior/baseline; mechanism; repository/runtime evidence; semantic invariants; optimization direction; expected benefit label; primary metric; secondary budgets; reproduction; constraints; validation; acceptance/promotion gate; rollback; dependencies.

Order:

1. Measurement prerequisites and semantic/correctness guards.
2. Highest-confidence/highest-impact independent optimizations.
3. Coupled or architectural optimizations.
4. M3 promotion experiments.

State that future SigmaOptimize defaults to one contract per invocation and must reproduce baseline, implement, validate correctness/performance, keep or revert, and leave no unsuccessful runtime change.
