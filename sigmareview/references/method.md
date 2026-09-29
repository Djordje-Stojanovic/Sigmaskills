# SigmaReview method

Use this as an investigation protocol, not a checklist to recite. Start from evidence and follow behavior across files and boundaries. Go deepest where the risk is highest. Every pass ends with findings or a short, target-specific "clean" or `N/A` line for the coverage ledger.

## Contents

1. Frame
2. Pass 1 — Promises and system map
3. Pass 2 — Correctness
4. Pass 3 — Data, state, and concurrency
5. Pass 4 — Failure handling and reliability
6. Pass 5 — Security and privacy
7. Pass 6 — Performance and resource use
8. Pass 7 — Architecture that causes defects
9. Pass 8 — Tests and verification
10. Pass 9 — Build, dependencies, release, and operations
11. Pass 10 — Domain overlay and coherence

## Frame

Record the repository, branch, commit SHA, languages, size, and whether the worktree is clean. Sort every tracked path by role: source, tests, config, schemas and migrations, CI, infrastructure, docs, generated, vendored, lockfiles, fixtures, binaries, and assets. Note what you will not read in depth and why.

Do not trust the README. Code, tests, schemas, config, docs, and released behavior are all evidence, and they can contradict each other. A contradiction is often the finding.

## Pass 1 — Promises and system map

Build the smallest model that explains the system:

- entry points, processes, services, jobs, CLIs, UI surfaces, and generated outputs;
- public APIs, commands, events, file formats, and protocols;
- state stores, caches, queues, external services, and devices;
- trust boundaries, user-controlled inputs, and sensitive assets;
- primary journeys, from user action to finished outcome, and the code that owns each step;
- the promises: stated goals, documented features, budgets (latency, frame time, memory, size, cost), compatibility claims, and invariants.

Flag only concrete mismatches here. Examples: an undocumented production entry point, two sources of truth, or a doc that would mislead a maintainer.

## Pass 2 — Correctness

Trace each promise from input to visible result.

- Logic: conditions, precedence, defaults, off-by-one errors, units, time zones, locale, overflow, rounding, precision, parsing, and serialization.
- Inputs: null, empty, duplicate, malformed, stale, partial, out-of-order, replayed, and extreme values.
- State machines: illegal transitions, terminal states, cancellation, retry, resume, and idempotency.
- Contracts: client and server, producer and consumer, schema and model, UI and backend, firmware and hardware, config and runtime.
- Unfinished work: TODOs, stubs, disabled checks, dead feature flags, and documented features that do not exist.
- Rendering and output: wrong layout, wrong frame, wrong text, wrong file — anything the user sees that contradicts the intended result.

A test that asserts current behavior may only preserve the bug. Check tests against what the consumer expects, not against what the code does.

## Pass 3 — Data, state, and concurrency

- Schema constraints versus code assumptions; migrations (ordering, locking, rollback, mixed versions, restart).
- Transactions, lost updates, check-then-act races, double processing, and isolation assumptions.
- Locks, async tasks, cancellation, shared mutable state, deadlocks, starvation, and ordering.
- Cache keys, invalidation, stale reads, and caches that ignore authorization.
- Queues: delivery guarantees, idempotency keys, poison messages, retry storms, and backpressure.
- Clocks: monotonic versus wall time, expiry, and skew.

Report a race only with a concrete interleaving.

## Pass 4 — Failure handling and reliability

Assume that dependencies fail, resources run out, and processes restart at the worst moment.

- Swallowed errors, catch-all handlers, wrong fallbacks, and missing cleanup on some exit path.
- Lifetimes of files, sockets, handles, processes, GPU resources, and memory.
- Timeouts, retries with backoff, retry budgets, backpressure, and cascading failure.
- Startup, shutdown, crash recovery, checkpoint and resume, rollback, and safe defaults.
- Health checks that test real capability, not only that a process exists.
- User-visible failures that nobody can see in logs or metrics.

Silent corruption is worse than a loud failure. Plausible-looking wrong output is a defect.

## Pass 5 — Security and privacy

Model the assets, entry points, trust boundaries, and attacker capabilities first. Then attack the model.

**Source review:**

- Authentication, sessions and tokens, account recovery, and account enumeration.
- Authorization at every object, action, tenant, admin path, and background job (broken object-level authorization is the most common serious flaw).
- Injection into SQL/NoSQL, shells, templates, HTML, headers, paths, URLs, deserializers, and LLM prompts.
- SSRF, path traversal, unsafe upload or archive extraction, open redirects, CORS/CSRF, XSS, prototype pollution, and mass assignment.
- Cryptography: the right primitive for the purpose, key handling, nonce reuse, and verification order.
- Secrets in files and in Git history, unsafe defaults, and secrets leaking through logs, errors, or client bundles.
- Privacy: data minimization, retention, deletion, and personal data in logs and telemetry.
- Denial of service through unbounded input, expensive parsing, regex, decompression, or fan-out.
- CI/CD: workflow token permissions, untrusted pull-request code, unpinned actions, dependency confusion, and artifact provenance.
- AI features: prompt-injection paths to tools or data, output validation, and cost abuse.

**Dynamic testing (authority B, local instance only):** follow [measure.md](measure.md). Test authorization with two users (can user A read or change user B's objects?), fuzz the main inputs, try the injection classes that the source review marked as plausible, and run the dependency-advisory and secret scanners that are already available. Never probe a system you did not start yourself, and never use payloads that can destroy shared data.

State preconditions and the data flow for every vulnerability. Never print a live secret. If a real credential was committed, rotation is part of the fix; deleting it from the tree is not enough. Use OWASP ASVS, the OWASP Top 10 lists (web, API, LLM), CWE, and language-specific secure-coding guides only where they apply. Repository evidence outranks checklist matching.

## Pass 6 — Performance and resource use

Find the real bottleneck on the path that users feel. Measure before you claim (see [measure.md](measure.md)).

1. **Work and data movement:** repeated scans, parsing, serialization, hashing, and copies; bad complexity; wrong data structures; eager work; missing batching, streaming, or pagination.
2. **Database:** N+1 queries, missing or bad indexes, over-fetching, long transactions, pool exhaustion, and lock contention.
3. **Concurrency:** independent work run in sequence, sync calls on async paths, contention, head-of-line blocking, and retry amplification.
4. **CPU and GPU:** hot functions, allocation in hot paths, missed vectorization, kernel launch and transfer cost, batching, and locality.
5. **Memory:** leaks, unbounded maps, queues, and caches, large-object churn, GC pressure, and peak versus steady state.
6. **I/O and network:** round trips, blocking I/O, small writes, payload size, compression, re-reads, and logging volume.
7. **Caching:** correctness first (an invalid fast answer is still wrong), then keys, invalidation, stampedes, and caches that hide a bad algorithm.
8. **Frontend and perceived speed:** LCP, INP, CLS, main-thread blocking, hydration, re-renders, request waterfalls, bundle size, and images and fonts.
9. **Startup, build, and CI:** import cost, cold start, artifact size, build and CI critical path, and idle cost.
10. **Saturation:** the first resource to run out at 10× load or data.

Name the limiting resource and the evidence class. Label estimates as estimates and show their assumptions. When the size of a problem is unknown, the finding is M3 and names the measurement that would settle it.

## Pass 7 — Architecture that causes defects

Report architecture only when it causes a defect or makes one likely: two sources of truth, a leaky contract that callers misuse, duplicated policy that has already drifted, a cycle that blocks a needed change, or a seam so poor that a critical path cannot be tested. Show the concrete cost. A cleaner design with no defect behind it is not a finding: it is an idea for SigmaImprove or a job for SigmaRefactor.

## Pass 8 — Tests and verification

Ask one question: would the current tests catch the findings from passes 2–7?

- Assertions on outcomes versus assertions on mock calls.
- Missing negative, boundary, concurrency, failure, migration, authorization, and abuse cases.
- Flaky, order-dependent, time-dependent, skipped, or never-run tests; CI steps that do not run what people think they run.
- Type checks, linters, sanitizers, and compiler warnings that are off or ignored.

Every P0–P2 finding carries the smallest proof test that fails before the fix. Do not demand 100% coverage; demand tests where the consequences are.

## Pass 9 — Build, dependencies, release, and operations

- Dependencies: purpose, duplication, abandonment, license, advisories, pinning, lockfile drift, and end-of-life runtimes. Verify version claims against primary sources.
- Build: determinism, network dependence, platform assumptions, and generated artifacts that can drift.
- CI: triggers, permissions, matrix gaps, skipped gates, and cache poisoning.
- Release: versioning, changelog, migrations, signing and provenance, rollback, and whether the release path has ever run before it matters.
- Operations: config validation, secret injection, observability, alerting, and runbooks.

Group routine compatible updates into one line. Treat security, end-of-life, and breaking upgrades one by one.

## Pass 10 — Domain overlay and coherence

Apply every overlay that fits the target, and skip the rest.

- **Games:** frame-time percentiles and 1% lows, not average FPS; hitches from GC, shader compilation, or asset loading; fixed versus variable timestep and physics determinism; input latency; render correctness (z-fighting, culling, wrong LOD, pop-in); save and load integrity; state after pause, resume, and alt-tab; memory on the weakest target device.
- **Web and frontend:** accessibility (keyboard, focus, contrast, screen readers), loading, empty, and error states, forms, responsive layout, browser support, and hydration.
- **API, service, and library:** contract clarity, versioning, idempotency, pagination, error shapes, rate limits, and cancellation.
- **CLI and developer tools:** exit codes, stdout and stderr, non-interactive behavior, quoting, signals, config precedence, dry runs, destructive confirmations, and cross-platform paths.
- **Mobile and desktop:** lifecycle, offline behavior, permissions, background work, updates, and crash recovery.
- **AI and data:** data leakage, evaluation validity, reproducibility, prompt and model versioning, structured-output validation, context limits, and cost and latency budgets.
- **Hardware, RTL, and firmware:** reset and initialization, clock-domain crossings, width and signedness, state-machine completeness, timing constraints, interrupts and DMA, register maps, watchdogs, and safe states. Simulation-correct is not silicon-correct.
- **Safety-critical and regulated:** traceability from requirement to code to test, hazards, safe states, and deterministic timing. Never claim certification from source review.

Then check coherence across passes:

1. Merge duplicate symptoms under their root cause.
2. Order fixes by dependency and find fixes that conflict.
3. Compare the promises from Pass 1 with what passes 2–9 found.
4. Find the smallest set of fixes that removes the most risk.
5. Run the evidence gate one last time and drop anything that no longer holds.
