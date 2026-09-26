# Improvement lenses

Each lens is a question to ask of the target, not a quote to repeat. Use them to generate candidates. Most lenses produce nothing on a given target, and a few produce the best idea of the run.

## Contents

1. Product and focus
2. Simplify and delete
3. Ambition and first principles
4. Experience and craft
5. Weighing
6. Domain prompts

## Product and focus

- **Work backwards from the user (Bezos).** Write the one-sentence announcement for the finished product. What does the user get that they cannot get today? Ideas that do not serve that sentence are noise.
- **Focus means saying no (Jobs).** What are the few things this product must be great at? What is it doing that dilutes them? An improvement can be the removal of a feature that competes for attention.
- **One-way and two-way doors (Bezos).** Data formats, public APIs, and the core loop of a game are hard to reverse. Weigh those ideas slowly and state the cost of undoing them. Most other ideas are cheap to try and undo; favor small experiments there.
- **Jobs to be done.** Which job does the user hire this product for? Where does it do that job only halfway?

## Simplify and delete

- **The algorithm (Musk), in this order:** question every requirement, and name the person who owns it; delete parts and steps; simplify what is left; only then make it faster; only then automate. Never optimize or automate something that should not exist. If you are not adding back at least a little of what you deleted, you did not delete enough.
- **Chesterton's fence.** Find out why something exists before you propose deleting it, and state the reason in the idea.
- **Less, but better (Rams).** Good design is useful, understandable, honest, unobtrusive, thorough down to the last detail, and as little design as possible.

## Ambition and first principles

- **Speed of light (Huang).** What is the theoretical best: zero waiting, zero steps, instant feedback, the physical limit of the hardware? Measure the gap between that limit and today, then propose the step that closes the most of it. Start from what is possible, not from what the last version did.
- **First principles.** Break the product down to its basic truths (what the user needs, what the machine can do, what it costs) and rebuild the answer from those, not from how competitors do it.
- **Zero-billion-dollar markets (Huang).** Is there something valuable that nobody offers yet because it looked impossible or small? One such idea per run is enough.
- **Platform leverage.** Is there one capability that would make many future features cheap? Weigh it against the features themselves.

## Experience and craft

- **The whole experience (Jobs).** Judge from the first contact to the last moment: install, first screen, first win, errors, updates, exit. Care about the parts nobody checks: empty states, error text, the back of the cabinet.
- **Affordance and feedback (Norman).** Can a user see what they can do? Does every action get immediate, honest feedback? Are mistakes easy to undo?
- **Game feel and juice.** For interactive work: input response, animation weight and anticipation, hit feedback, camera, sound, rhythm of tension and release, the difficulty curve, and the moment-to-moment "is this fun?".
- **Delight (Kano).** Sort each idea as a basic need (missing it causes anger), a performance need (more is better), or a delighter (unexpected joy). Basics come first, but a product with no delighters is forgettable.
- **Latency is a feature.** Perceived speed is part of quality: a loading state, optimistic updates, and streaming can matter more than raw speed.

## Weighing

For every option, give:

- **Impact on the vision:** high / medium / low, with the reason.
- **Effort:** S / M / L / XL.
- **Risk:** what could go wrong, including harm to what works today.
- **Door:** one-way or two-way.
- **Kano:** basic / performance / delighter.
- **Signal:** how the user would know it worked.

Recommend one option and say why it beats the others. Never hide the tradeoff.

## Domain prompts

- **Games:** the core loop and its first five minutes; level variety and pacing; boss and enemy design; character animation and readability; art direction consistency; music and sound; difficulty curve; progression and rewards; accessibility options (remapping, subtitles, colorblind modes); replay value.
- **Web and mobile apps:** time to first value; onboarding; the core task in fewer steps; empty, loading, and error states; visual hierarchy, spacing, and typography; mobile ergonomics; accessibility; trust signals.
- **CLI and developer tools:** the zero-config path; defaults that do the obvious thing; help and error messages that tell you the next command; output that people and scripts can both read; speed of the common command.
- **Libraries and APIs:** the smallest useful example; names that explain themselves; a pit of success where the easy way is the right way; migration cost for users.
- **AI products:** where the model should not be used at all; where a smaller or faster model is good enough; how the user sees and corrects output; evaluation of quality.
- **Hardware and firmware:** the first-hour experience; a bill of materials that could be simpler; manufacturability; field updates; diagnostics a user can read.
