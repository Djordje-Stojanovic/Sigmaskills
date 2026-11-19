# SIMPLICITY.md - the collection: delete first, then simplify

The owner's collection of words and examples on simplicity. Add new ones at the bottom of their section; never rewrite a quote. Stefan's chat word for word: `archive/sources/stefan-chat-2026-11.md`.

## Musk's Algorithm, his own words (Lex Fridman podcast, clip by @jaynitx: x.com/jaynitx/status/2066506535250092378)

Transcribed from the auto captions; only caption errors fixed ("lumbic" to "limbic", line breaks joined).

> Well, it's easy to say simplify and very difficult to do. I have this very basic first-principles algorithm that I run kind of as like a mantra, which is: the first question, the requirements, make the requirements less dumb. The requirements are always dumb to some degree. So if you want to start off by reducing the number of requirements, and no matter how smart the person who gave you those requirements, they're still dumb to some degree. You have to start there, because otherwise you could get the perfect answer to the wrong question. So try to make the question the least wrong possible. That's what question the requirements means.
>
> And then the second thing is try to delete whatever the step is, the part or the process step. It sounds very obvious, but people often forget to try deleting it entirely. And if you're not forced to put back at least 10% of what you delete, you're not deleting enough. Somewhat illogically, people often, most of the time, feel as though they've succeeded if they have not been forced to put things back in. But actually they haven't, because they've been overly conservative and have left things in there that shouldn't be.
>
> And only the third thing is try to optimize it or simplify it. Again, these all sound, I think, very obvious when I say them, but the number of times I've made these mistakes is more than I care to remember. That's why I have this mantra. So in fact I'd say the most common mistake of smart engineers is to optimize a thing that should not exist.
>
> (Lex: so you show up to a problem, to the supercomputer cluster, see the process and ask: can this be deleted?) Yeah. First try to delete it. That's not easy to do. What generally makes people uneasy is that at least some of the things that you delete, you will put back in. But going back to where our limbic system can steer us wrong: we tend to remember, with sometimes a jarring level of pain, where we deleted something that we subsequently needed. And so people will remember that one time they forgot to put in this thing three years ago and it caused them trouble, and so they overcorrect, and then they put too much stuff in there and overcomplicate things. So you actually have to say: no, we're deliberately going to delete more than we should. At least one in ten things we're going to add back in. (...) If you're so conservative as to never have to put anything back in, you obviously have a lot of stuff that isn't needed. So you've got to overcorrect. This is, I would say, a cortical override to a limbic instinct.
>
> There's a step four as well, which is: any given thing can be sped up. However fast you think it could be done, whatever the speed it's being done, it can be done faster. But you shouldn't speed things up until it's optimized. And then the fifth thing is to automate it. I have gone backwards so many times where I automated something, sped it up, simplified it, and then deleted it. And I got tired of doing that. So this mantra is a very effective five-step process.

Order matters. `ENGINEERING.md` section 1 quotes the five steps from this passage; no other copy exists.

## Stefan (OSZII), our working partner

- 07-11: "Du musst so viel Zeug rausschmeißen. Des verwirrt AI einfach. AI liebt es Zeugs zu komplizieren, du musst da klar sagen: weg damit." (You must throw out so much stuff. It confuses the AI. AI loves to complicate things; you must say clearly: away with it.)
- 07-11, on a shared core repo: "Des wird viel Komplexität rein bringen." (That brings in a lot of complexity.)
- 08-11, on a boat.dev + vast.ai build guide: "Ne. Komplexität. Es soll so wenig wie möglich da stehen, und i verwend des nit. Des heißt i hätt Anleitung für des ohne des zu brauchen." (No. Complexity. As little as possible should be written there, and I don't use it. I'd have a guide for something I don't need.)
- 08-11, Đorđe: "Die Kunst is echt in simplicity: was erreichen mit so wenig Schritten wie geht." Stefan: "Genau."
- Đorđe, 08-11: 3 months customizing the Pi agent, then mostly T3 Code; 1 month on the video pipeline, 90% deleted, and it runs better.

## Raptor 1 to Raptor 3

SpaceX's Raptor 1 (2019) carried a tangle of outside pipes, wires and a heat shield. Raptor 3 (2024) moved them inside the metal: about 2,080 kg and 185 tf became about 1,525 kg and 250-280 tf, with about 90 % fewer welds. Lighter, stronger, faster to build. (Numbers from web summaries the owner collected 2026-11-09.)

## Steve Jobs

> People think focus means saying yes to the thing you've got to focus on. But that's not what it means at all. It means saying no to the hundred other good ideas that there are.

> I'm actually as proud of the things we haven't done as the things I have done. Innovation is saying no to 1,000 things.

(WWDC 1997)

> That's been one of my mantras — focus and simplicity. Simple can be harder than complex: You have to work hard to get your thinking clean to make it simple. But it's worth it in the end because once you get there, you can move mountains.

(BusinessWeek, 1998)

> It's not just minimalism or the absence of clutter. It involves digging through the depth of complexity. To be truly simple, you have to go really deep. For example, to have no screws on something, you can end up having a product that is so convoluted and so complex. The better way is to go deeper with the simplicity, to understand everything about it and how it's manufactured. You have to deeply understand the essence of a product in order to be able to get rid of the parts that are not essential.

(Walter Isaacson, Steve Jobs)

> In most people's vocabularies, design means veneer. It's interior decorating. It's the fabric of the curtains of the sofa. But to me, nothing could be further from the meaning of design. Design is the fundamental soul of a human-made creation that ends up expressing itself in successive outer layers of the product or service.

(Fortune, 2000)

> When you first start off trying to solve a problem, the first solutions you come up with are very complex, and most people stop there. But if you keep going, and live with the problem and peel more layers of the onion off, you can often times arrive at some very elegant and simple solutions. Most people just don't put in the time or energy to get there.

(no source named)

## How we use this

Before adding a check, rule, script or step: name the one it replaces. Delete until something must come back. The owner's words: every addition cuts something else.
