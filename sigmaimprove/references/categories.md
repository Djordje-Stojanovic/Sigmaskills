# Improvement categories

Scan every category that applies to the target. Each line is a question to ask, not a box to tick. The list draws on the ISO/IEC 25010 quality model, Nielsen's usability heuristics, WCAG 2.2, Core Web Vitals, Google's HEART metrics (happiness, engagement, adoption, retention, task success), Apple's Human Interface Guidelines and Material Design, game-feel practice, and DORA delivery metrics. Tag every entry with its category ID, for example `B1 Perceived latency`.

## Measure against the leaders and the bars

For each category, the comparison has two parts. The first is the world's top one to three products in this field: what they achieve, from primary sources. The second is the published bars below, where they apply. Beating the fifth-best product is not the goal. Closing the gap to the best is. Quote the source of each bar and each leader number.

| Area | Bar | Source |
|---|---|---|
| Response to input | Under 0.1 s feels instant; under 1 s keeps the flow of thought; over 10 s loses attention | Nielsen's response-time limits |
| Web interaction | Respond within 100 ms; work in chunks under 50 ms; produce a frame within about 16 ms | Google RAIL model |
| Web loading and stability | LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1 at the 75th percentile | Core Web Vitals |
| Frame rate | 16.7 ms per frame for 60 fps, 8.3 ms for 120 fps; judge by frame-time percentiles and 1% lows, not averages | Display refresh arithmetic, game-performance practice |
| Contrast | 4.5:1 for normal text, 3:1 for large text and UI components (AA) | WCAG 2.2 |
| Touch and click targets | At least 24×24 CSS px (WCAG 2.2 AA); 44×44 pt on Apple platforms; 48×48 dp on Android | WCAG 2.2, Apple HIG, Material Design |
| Delivery | Deploy frequency, lead time, change failure rate, and time to restore compared with the elite group of the latest DORA report | DORA |

A bar is a floor, not the goal. When the leaders are far above it, their level is the target.

**Speed ideas versus SigmaReview:** here, speed is a design choice that goes beyond what the product promises today. Examples: prerender for instant start, stream results, or move work off the critical path. A path that breaks a stated budget, or does measurable waste with one correct fix, is a SigmaReview finding.

## A. Value and product

- **A1 New features:** what job do users need done that the product cannot do yet?
- **A2 Feature depth:** which existing feature is half-finished and would become great with one more step?
- **A3 Delete and simplify:** which feature, setting, mode, or step costs more attention than it returns?
- **A4 Onboarding and time to value:** how many minutes pass before a new user gets the first real outcome?
- **A5 Engagement and retention:** why would a user come back tomorrow, and what makes them leave?
- **A6 Content:** examples, templates, levels, presets, sample data — what would make the empty product feel full?
- **A7 Reach and growth:** sharing, invites, discoverability, SEO, store presence, word of mouth.

## B. Speed and efficiency

- **B1 Perceived latency:** optimistic updates, skeletons, streaming, instant feedback before the work finishes.
- **B2 Load and startup:** time to first useful screen, cold start, lazy loading, precomputation.
- **B3 Runtime speed and throughput:** the common action done faster, a better algorithm or data layout, work done once instead of per use.
- **B4 Rendering and smoothness:** frame rate, frame-time stability, scrolling, animation jank, LCP, INP, and CLS.
- **B5 Network and offline:** fewer round trips, smaller payloads, caching, prefetch, offline-first, sync.
- **B6 Resource use:** memory, battery, thermal load, disk, and download size.
- **B7 Cost:** compute, storage, API, and token cost per user or per action.

## C. Interaction and control

- **C1 Flow and friction:** steps, clicks, waits, and decisions in the core task — which ones can go?
- **C2 Control and responsiveness:** input latency, precision, keyboard, controller, touch, and gesture support; the feeling that the user is in charge.
- **C3 Feedback and status:** does the user always know what is happening, what just happened, and what will happen next?
- **C4 Error prevention and recovery:** constraints that stop mistakes, clear error text, undo, autosave, and safe defaults.
- **C5 Navigation and structure:** can users find things and always know where they are?
- **C6 Discoverability and help:** can a new user find the powerful features without a manual?
- **C7 Power-user efficiency:** shortcuts, command palette, batch actions, scripting, and remembered choices.

## D. Look and feel

- **D1 Hierarchy and layout:** does the most important thing look most important? Spacing, alignment, and density.
- **D2 Typography:** type scale, readability, line length, and weight contrast.
- **D3 Color and theming:** palette harmony, contrast, meaning of color, dark mode, and brand fit.
- **D4 Imagery and art direction:** icons, illustrations, visual style, and consistency of assets.
- **D5 Motion and animation:** timing, easing, anticipation, follow-through, and motion that explains change.
- **D6 Micro-interactions and juice:** hover, press, success, and failure moments; the small rewards that make actions feel good.
- **D7 Sound and haptics:** audio feedback, music, vibration, and silence where it matters.
- **D8 Consistency and design system:** one way to do each thing; shared components, tokens, and voice.
- **D9 Native feel:** follows the platform's conventions (Apple HIG, Material, Windows, terminal norms): system fonts, scroll physics, window behavior, notifications, share sheets, and keyboard conventions.

## E. Reach and inclusion

- **E1 Accessibility:** WCAG 2.2 AA and beyond: contrast, keyboard use, focus, screen readers, captions, reduced motion, and remappable controls.
- **E2 Localization:** translations, right-to-left layout, dates, numbers, currencies, and cultural fit.
- **E3 Platforms and devices:** mobile, desktop, web, consoles, small and large screens, and low-end hardware.
- **E4 Interoperability:** import and export, open formats, integrations, public APIs, and standards.

## F. Intelligence and automation

- **F1 Smart defaults:** the system does the obvious thing without being asked.
- **F2 Personalization:** it remembers and adapts to the user without being creepy.
- **F3 AI features:** where a model adds real value, and where it should not be used at all.
- **F4 Automation of toil:** repeated manual steps for users or maintainers that should happen on their own.
- **F5 Search, ranking, and recommendations:** relevance, speed, and forgiveness of typos.

## G. Trust and robustness

- **G1 Resilience:** degraded modes, offline behavior, autosave, and recovery after a crash.
- **G2 Security hardening:** defense in depth, passkeys, least privilege, and safer defaults beyond today's promises.
- **G3 Privacy and data control:** data minimization, export and delete, and local-first options.
- **G4 Observability and diagnostics:** status a user can read, useful logs, and support bundles.
- **G5 Safety:** protection from harm to users, data, and hardware.

## H. Engineering and delivery

- **H1 Architecture:** a module or boundary that would make many future changes cheap.
- **H2 Code quality:** readability, naming, and removal of clever code where plain code would do.
- **H3 Testing strategy:** tests that would let the team change things fearlessly.
- **H4 Developer experience:** setup time, feedback loop speed, and tooling.
- **H5 Build and release:** CI speed, deploy frequency, lead time, change failure rate, and time to restore (the DORA metrics).
- **H6 Dependencies and platform:** fewer dependencies, current runtimes, and cheaper upgrades.
- **H7 Documentation:** short, true docs for users and contributors.
- **H8 Extensibility:** plugins, configuration, hooks, and APIs for others to build on.

## I. Games (use for interactive entertainment)

- **I1 Core loop:** is the moment-to-moment action fun on its own, within the first five minutes?
- **I2 Levels and world:** variety, pacing, landmarks, secrets, and the teaching of mechanics through level design.
- **I3 Characters and animation:** readability, weight, personality, and transitions.
- **I4 Combat, enemies, and bosses:** telegraphing, variety, fairness, and set pieces.
- **I5 Progression and economy:** rewards, unlocks, upgrades, and a sense of growth.
- **I6 Difficulty and balance:** difficulty curve, options, and dynamic adjustment.
- **I7 Story and world-building:** stakes, lore delivery, and environmental storytelling.
- **I8 Audio and music:** adaptive music, spatial sound, and sound that carries gameplay information.
- **I9 Multiplayer and social:** co-op, competition, sharing, and community.
- **I10 Replay value:** modes, challenges, randomness, and mastery depth.
