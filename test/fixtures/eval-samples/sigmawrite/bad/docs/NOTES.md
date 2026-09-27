# Design notes

The tick orchestration layer idempotently hydrates the board on each frame boundary, leveraging the reducer paradigm, while the persistence subsystem retains the high-watermark across session lifecycles in a performant manner that nobody can follow.
