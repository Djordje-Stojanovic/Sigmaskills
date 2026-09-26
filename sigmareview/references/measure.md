# Measurement and safe dynamic testing

Use this only under authority B or a custom authority that allows execution. Under authority A, every performance and security finding is M2 or M3.

## Safety boundary

- Work in an isolated copy or workspace. Install only the dependencies the project declares.
- Run only what you start: the test suite, the build, the local app, local benchmarks, and probes against your own local instance.
- Never touch production, staging that others use, paid APIs, cloud resources, external databases, or third-party services. Stub or skip them, and record the gap.
- Cap time, CPU, memory, and disk. Stop a run that exceeds its cap and record why.
- Leave no measurement tools, dumps, or scratch files in the repository diff.

## Baseline first

Before any claim, run the existing checks and record the commands, versions, OS, hardware, and results. A failing baseline is itself evidence. Show it, and do not build performance claims on a broken build.

## Measuring performance

1. **Pick the metric the user feels:** p50/p95/p99 latency for requests, frame-time percentiles and 1% lows for games, time to first useful state for startup, LCP/INP/CLS for web pages, peak memory for constrained devices, and cost per request for paid services.
2. **Control the setup:** the same commit, runtime, hardware, power mode, dataset, concurrency, and cache state. Measure cold and warm separately.
3. **Warm up, then repeat** enough times to see the spread. Report the distribution, not one number.
4. **Profile before you explain.** Use a sampling profiler, flame graph, allocation profile, query plan, or trace, whichever matches the question. The bottleneck is often not where intuition says.
5. **Check correctness with every run.** A faster wrong answer does not count.
6. **Watch for traps:** JIT and GC warm-up, thermal throttling, coordinated omission in load tests, background noise, and caches that make the second run meaningless.

Prefer the project's own benchmark commands, then standard tools, then a small harness. A harness that an M1 claim depends on must be reproducible from the report: embed it if it is short, or downgrade the claim to M3.

## Security testing on your own instance

- **Authorization matrix:** create two ordinary users and an admin if possible. For each sensitive object and action, check that user A cannot read, change, or delete user B's data, and that ordinary users cannot reach admin actions. Include background jobs and indirect paths such as exports and webhooks.
- **Input fuzzing:** send empty, huge, malformed, Unicode-edge, and type-confused values to each main input. Watch for crashes, 500 errors, hangs, and memory growth.
- **Targeted injection:** try only the classes that source review marked as plausible, with harmless markers such as a unique string or a sleep of one second, never destructive payloads.
- **Scanners:** run the dependency-advisory, secret-scanning, and static-analysis tools that are already installed or declared by the project. Treat their output as candidates, and verify each one before reporting it.

## When execution fails

Record the command, the purpose, and the stage where it failed. Try one or two informative fallbacks, then stop. Continue source-led: keep M2 findings, downgrade the claims that depended on the run to M3, and state the smallest action that would unblock measurement. A total execution failure still produces the report, with `Runtime baseline: not established`.
