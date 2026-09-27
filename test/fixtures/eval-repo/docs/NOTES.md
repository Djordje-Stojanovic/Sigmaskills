# Design notes

The tick orchestration layer idempotently hydrates the ephemeral board projection surface on each frame-cadence boundary, leveraging the `step` reducer paradigm to synergistically operationalize state transitions, while the persistence subsystem (`saveBest` in `src/scores.js`) facilitates durable high-watermark retention across session lifecycles in a performant manner.
