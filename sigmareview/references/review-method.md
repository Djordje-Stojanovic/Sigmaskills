# SigmaReview ten-pass method

Use this as an investigation protocol, not a generic checklist. Start from repository evidence, follow behavior across files and boundaries, and deepen the passes that carry the most risk. Complete every pass with either evidence-backed findings or a repository-specific `N/A`/clean result for the coverage ledger.

## Contents

1. Preflight: establish the review frame
2. System map, intent, and coverage
3. Functional correctness and feature completeness
4. Architecture, modularity, and maintainability
5. Data, state, concurrency, and distributed behavior
6. Reliability, failure handling, and safety
7. Security, privacy, secrets, and abuse resistance
8. Performance, efficiency, and scale
9. Tests, verification, and specification quality
10. Dependencies, build, supply chain, CI/CD, and operations
11. Domain overlay, SOTA gap, and cross-pass coherence

## Preflight: establish the review frame

Before Pass 1:

1. Resolve the canonical repository, default branch, reviewed commit SHA, license, primary languages, repository size, and whether the worktree is clean.
2. Inventory all tracked paths by role: first-party source, tests, configuration, schemas/migrations, CI/CD, infrastructure/deployment, documentation, generated, vendored, lockfiles, fixtures, binaries, and assets.
3. Read root and path-specific engineering instructions, README files, architecture decision records, domain glossaries, contribution rules, changelogs, release metadata, and package manifests.
4. Identify declared product purpose, supported platforms, public interfaces, deployment modes, data sensitivity, compatibility promises, and the repository's own validation commands without running them.
5. Record exclusions and why semantic review would be invalid or wasteful; exclusions remain visible in the final coverage ledger.

Do not accept the README as ground truth. Treat documentation, code, tests, schemas, configuration, and released behavior as evidence that may contradict each other.

## Pass 1 — System map, intent, and coverage

Build the smallest accurate model that explains the repository:

- runtime entry points, packages, processes, services, libraries, jobs, CLIs, UI surfaces, hardware blocks, and generated outputs;
- public APIs, commands, events, file formats, protocols, and compatibility surfaces;
- state stores, schemas, caches, queues, external services, devices, and third-party integrations;
- trust boundaries, privilege changes, network boundaries, user-controlled inputs, and sensitive assets;
- build, test, release, deployment, migration, rollback, and recovery paths;
- primary user journeys and the code path responsible for each.

Compare declared structure with actual dependencies. Flag only concrete mismatches: unreachable packages, undocumented production entry points, dead deployment paths, two sources of truth, or architecture documents that would mislead a maintainer.

Pass output in reasoning: component map, boundary map, user-flow map, and file-accounting baseline.

## Pass 2 — Functional correctness and feature completeness

Trace behavior from inputs to externally visible results. Focus on what the product actually promises.

Inspect:

- conditional logic, precedence, default branches, off-by-one boundaries, sign/unit/timezone/locale mistakes, overflow/underflow, rounding, precision, parsing, and serialization;
- null, empty, duplicate, malformed, stale, partial, out-of-order, replayed, and extreme inputs;
- state machines: legal transitions, terminal states, cancellation, retries, resumption, idempotency, and impossible states;
- API/client, producer/consumer, schema/model, UI/backend, CLI/library, firmware/hardware, and config/runtime contract agreement;
- error-to-result conversion, partial success, optimistic state, stale closures, cached state, pagination, filtering, ordering, and boundary semantics;
- incomplete branches, TODO/FIXME markers, feature flags, stubs, placeholder implementations, disabled checks, and code made unreachable by configuration;
- documented features and acceptance behavior against implementation and tests.

Use tests as intent evidence, then test the tests mentally against consumer expectations. A test that asserts current implementation behavior may merely preserve the bug.

## Pass 3 — Architecture, modularity, and maintainability

Evaluate design by change cost and correctness, not aesthetic preference.

Inspect:

- dependency direction, cycles, package boundaries, ownership, locality, and whether responsibilities live with the data/invariant they protect;
- interfaces that expose implementation detail, shallow wrappers, god modules, shotgun surgery, duplicated policy, parallel hierarchies, and feature logic scattered across layers;
- abstractions with one hypothetical caller, configuration that behaves like code, overly generic extension points, and indirection that obscures the primary path;
- deep-module opportunities: a small stable interface hiding substantial complexity, with a clear test seam;
- inconsistent domain concepts, names, units, error types, lifecycle rules, and sources of truth;
- public compatibility, versioning, deprecation, migration, and extension strategy;
- code generation boundaries and whether generated and hand-written code can drift.

Apply three tests before reporting a redesign:

1. **Deletion test:** what machinery disappears if the proposed boundary exists?
2. **Change-amplification test:** show a realistic change that currently touches too many locations.
3. **Seam test:** identify the contract and how it improves isolated verification or replacement.

Offer a migration sequence, not a greenfield fantasy. Preserve sound local conventions.

## Pass 4 — Data, state, concurrency, and distributed behavior

Inspect every stateful boundary:

- schema constraints versus application assumptions; uniqueness, nullability, foreign keys, enum evolution, encoding, precision, and default drift;
- migrations for ordering, backfill, locking, compatibility windows, rollback, partial failure, restartability, and mixed-version deployments;
- transaction boundaries, atomicity, lost updates, check-then-act races, double processing, duplicate delivery, and isolation assumptions;
- locks, atomics, channels, async tasks, cancellation, shared mutable state, reentrancy, memory visibility, deadlocks, livelocks, starvation, and ordering;
- cache keys, invalidation, TTL, stampedes, stale reads, negative caching, and authorization-sensitive caching;
- queues and events: at-least/at-most/exactly-once claims, idempotency keys, poison messages, retry storms, ordering, backpressure, and dead-letter handling;
- clocks, monotonic versus wall time, timezone/DST, expiration, skew, and cross-system timestamp formats;
- replicas, partitions, leader changes, split brain, reconciliation, eventual consistency, and conflict resolution where applicable.

Trace invariants across persistence, retries, and process restarts. Report a race only with a concrete interleaving.

## Pass 5 — Reliability, failure handling, and safety

Assume dependencies fail, resources exhaust, processes restart, and inputs arrive at the worst time.

Inspect:

- exception and error propagation, swallowed failures, catch-all handling, fallback correctness, and cleanup on every exit path;
- file, socket, transaction, process, thread, handle, GPU/device, and memory lifecycle;
- timeouts, retries, jitter, retry budgets, circuit breaking, bulkheads, backpressure, rate limiting, and cascading failure;
- startup, shutdown, cancellation, crash recovery, checkpointing, resume, rollback, safe defaults, and known-safe states;
- configuration absence, invalid values, partial rollout, version skew, region failure, and dependency degradation;
- health/readiness checks that prove meaningful service capability instead of process existence;
- observability of user-visible failures: structured logs, metrics, traces, audit trails, correlation identifiers, actionable messages, and sensitive-data hygiene;
- safety-critical paths: hazard contribution, fail-safe state, prerequisite checks, command ordering, integrity checks, single-event hazards, and recovery time constraints.

Distinguish resilient degradation from silent corruption. Prefer explicit failure over plausible-looking wrong output.

## Pass 6 — Security, privacy, secrets, and abuse resistance

Perform defensive source review grounded in the repository's actual exposure.

Model assets, entry points, trust boundaries, attacker capabilities, and abuse paths. Inspect:

- authentication, session/token lifecycle, identity binding, recovery, impersonation, and account enumeration;
- authorization at every object, action, tenant, admin, background-job, and indirect-access boundary;
- injection into SQL/NoSQL, shells, templates, HTML, headers, logs, paths, URLs, deserializers, interpreters, prompts, and configuration;
- SSRF, request smuggling, traversal, unsafe upload/extraction, insecure redirects, CORS/CSRF, XSS, prototype pollution, and mass assignment where applicable;
- cryptographic purpose, algorithm/mode, key generation/storage/rotation, nonce/IV uniqueness, verification order, downgrade handling, and constant-time requirements;
- secrets in current files and relevant history, insecure examples/defaults, overbroad permissions, and secret exposure through logs, errors, artifacts, or client bundles;
- tenant isolation, data minimization, retention/deletion, consent, export, telemetry, backups, logs, and privacy boundary violations;
- denial-of-service through unbounded inputs, expensive parsing, algorithmic complexity, fan-out, resource allocation, regex, compression, or retry amplification;
- CI/CD permissions, untrusted pull-request execution, dependency confusion, artifact provenance, release signing, and build-secret exposure;
- AI systems: prompt injection boundaries, tool authorization, retrieval poisoning, data exfiltration, output validation, model/provider failure, and cost abuse.

For a vulnerability, state the preconditions and data/control flow. Never include a live secret or unnecessarily weaponized exploit. Recommend revocation/rotation whenever a real credential may have been committed; deleting it from the current tree is insufficient.

Use OWASP ASVS/API/LLM guidance, CWE, NIST SSDF, CERT, or language-specific secure-coding standards only when applicable. Repository evidence outranks checklist matching.

## Pass 7 — Performance, efficiency, and scale

Derive likely bottlenecks from workload and code paths; do not perform benchmark theatre.

Inspect:

- asymptotic complexity, nested scans, repeated parsing/serialization, redundant work, hot-path allocation, copies, boxing, reflection, and synchronization;
- database query counts, N+1 patterns, missing/bad indexes, unbounded result sets, pagination, connection/transaction duration, and pool exhaustion;
- network round trips, fan-out, payload size, compression, batching, streaming, head-of-line blocking, and backpressure;
- memory retention, unbounded maps/queues/caches, leaks, fragmentation, large-object churn, and load-proportional buffering;
- CPU/GPU/device utilization, vectorization, parallelism overhead, kernel launch/data transfer, I/O scheduling, and hardware locality when relevant;
- frontend bundle/runtime cost, rendering waterfalls, unnecessary hydration, layout thrash, image/font delivery, and interaction latency;
- cold starts, startup work, build time, CI time, artifact size, and deployment scaling limits;
- caching correctness before caching opportunity; an invalid fast answer is still wrong.

Quantify the mechanism where repository data permits. Label estimates as estimates and show assumptions. Recommend measurement before optimization when impact cannot be established from source.

## Pass 8 — Tests, verification, and specification quality

Evaluate whether the verification system would detect the failures found in Passes 2–7.

Inspect:

- test pyramid/shape relative to architecture; unit, integration, contract, end-to-end, property, fuzz, mutation, load, chaos, hardware simulation, and formal verification as applicable;
- assertions that prove outcomes versus mocks that prove calls; consumer contracts versus producer snapshots;
- negative, boundary, concurrency, failure, recovery, migration, compatibility, authorization, and abuse cases;
- determinism, isolation, time/randomness control, flaky retries, order dependence, shared fixtures, cleanup, and hermeticity;
- test data realism and whether fixtures conceal encoding, scale, permission, or schema problems;
- coverage configuration, excluded critical paths, generated code, dead tests, skipped tests, expected failures, and CI paths that do not run what maintainers think;
- type checking, linting, static analysis, sanitizers, model checking, assertions, and compiler warnings;
- traceability from requirements/invariants to tests and from defects to regression tests.

For every accepted P0–P2 finding, specify the smallest regression test that would fail before the fix and pass afterward. Do not demand 100% line coverage; demand evidence at consequential behavior boundaries.

## Pass 9 — Dependencies, build, supply chain, CI/CD, and operations

Inspect the path from source to a running, supportable release:

- direct and transitive dependency purpose, duplication, abandonment, license constraints, advisories, update policy, pinning, lockfile consistency, and runtime compatibility;
- supported language/framework/platform versions, end-of-life components, deprecated APIs, and migration blockers;
- build determinism, generated artifacts, environment leakage, timestamps, network dependence, architecture/platform assumptions, and reproducibility;
- CI triggers, branch/tag filters, permissions, cache poisoning, artifact handoff, matrix gaps, skipped gates, race conditions, and protected-environment expectations;
- release versioning, changelog, migrations, signing, provenance/SBOM, rollback, canary/blue-green strategy, and backward compatibility;
- infrastructure defaults, network exposure, identity/permissions, encryption, backups, restore testing, regional assumptions, capacity, and cost traps;
- runtime configuration validation, secret injection, feature flags, observability, alertability, runbooks, SLOs, and on-call diagnosability;
- developer experience only where it affects correctness or delivery: bootstrap reproducibility, command drift, hidden prerequisites, and misleading documentation.

Verify version/update claims from official registries, maintainers, advisories, or platform documentation. Group routine compatible patch updates; give individual treatment to security, end-of-life, breaking, or architecturally meaningful upgrades.

## Pass 10 — Domain overlay, SOTA gap, and cross-pass coherence

Select every applicable overlay; do not force irrelevant disciplines.

### Web and frontend

Inspect accessibility, semantic structure, keyboard/focus behavior, responsive states, loading/empty/error/success states, form semantics, navigation, internationalization, color/contrast, reduced motion, browser support, hydration, and whether the visual system is coherent rather than generically decorative.

### API, service, and library

Inspect contract clarity, versioning, idempotency, pagination, errors, compatibility, rate limits, discoverability, composability, unsafe defaults, resource ownership, cancellation, and behavior under partial failure.

### CLI and developer tool

Inspect exit codes, stdout/stderr separation, non-interactive behavior, shell quoting, signals, config precedence, dry-run semantics, destructive confirmations, stable machine-readable output, cross-platform behavior, and recoverability.

### Mobile and desktop

Inspect lifecycle transitions, offline behavior, persistence, permissions, background execution, updates, deep links, platform conventions, accessibility, resource pressure, and crash recovery.

### Infrastructure and systems

Inspect privilege, isolation, kernel/OS assumptions, signals, process supervision, file-descriptor and memory limits, filesystem semantics, network partitions, immutable deployment, drift, and rollback.

### AI/ML and data science

Inspect dataset lineage, leakage, evaluation validity, reproducibility, seed/control, metric gaming, baseline comparison, drift, prompt/model versioning, structured-output validation, token/context limits, cost/latency budgets, fallbacks, and human oversight.

### Hardware, RTL, firmware, and drivers

Inspect specification traceability; reset and initialization; clock/reset-domain crossings; metastability; combinational loops and inferred latches; width, signedness, overflow, X/unknown propagation; state-machine completeness and illegal-state recovery; timing and resource constraints; interrupts, DMA, memory ordering, register maps, and hardware/software contract agreement; concurrency and reentrancy in firmware; power, thermal, watchdog, and safe-state behavior; synthesizability and portability; lint/CDC/RDC evidence; simulation assertions, functional/code coverage, constrained-random tests, formal properties, equivalence, and sign-off criteria. Separate simulation-correct from synthesis-correct and software-correct from silicon-correct.

### Cryptographic or high-assurance code

Inspect protocol composition, misuse resistance, side channels, constant-time behavior, fault handling, key lifecycle, test vectors, formal claims, unsafe optimization, and dependence on undocumented behavior. Prefer established constructions over novel cryptography.

### Safety-critical or regulated systems

Inspect requirement-to-code-to-test traceability, hazards, failure modes, independence, safe states, deterministic timing, diagnostic coverage, auditability, change control, and evidence required by the repository's actual regulatory domain. Do not claim certification from source inspection.

Finally perform a cross-pass coherence review:

1. Merge duplicate symptoms under common root causes.
2. Detect remediation conflicts and order prerequisite fixes.
3. Compare architecture claims with deployment reality, tests with contracts, schemas with models, docs with code, and security controls with operational configuration.
4. Identify the smallest set of changes that removes the greatest combined risk.
5. Separate **defects**, **engineering upgrades**, and **optional opportunities**. Never inflate optional modernization into a bug.
6. Re-run the evidence gate mentally against every retained finding and discard anything that does not survive.
