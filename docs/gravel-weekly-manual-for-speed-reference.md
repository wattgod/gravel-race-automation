# Manual for Speed reference study

This is an interface and editorial-mechanics study for Gravel Weekly. It is not
permission to copy Manual for Speed's logo, type treatment, photography,
illustration, gradients, page composition, recurring names, or trade dress.

## Archive sample

The review used five representative Internet Archive captures:

- [December 2012 homepage](https://web.archive.org/web/20121218044342/http://manualforspeed.com/)
- [2012 photo essay: Nice Work. Disappointment.](https://web.archive.org/web/20121101234132/http://manualforspeed.com/2012/09/nice-work-disappointment/)
- [March 2016 homepage](https://web.archive.org/web/20160306025636/http://manualforspeed.com/)
- [2015 Tour de France: Stage 01](https://web.archive.org/web/20160323053644/http://manualforspeed.com/road-racing/2015-tour-de-france-stage-01/)
- [Clown Dreams Lookbook](https://web.archive.org/web/20160323030820/http://manualforspeed.com/bonus-treasures/clown-dreams-lookbook/)

The 2012 and 2016 systems are materially different. The early site is a quiet,
photo-led index of essays with short, pointed headlines. By 2016 it has become a
maximal magazine: full-bleed story cards, huge condensed display type, issue-like
tables of contents, recurring departments, character credits, and deliberately
over-specific field notes. The durable lesson is the editorial structure, not
either skin.

## What made it cultural coverage

Manual for Speed ran two records at the same time:

1. The official race record: route, result, distance, course, date, and place.
2. The lived record: who was there, what went wrong, what people ate, what the
   access hierarchy felt like, overheard lines, visual oddities, travel details,
   jokes, embarrassment, and the author's changing judgment.

The second record is why the work still feels like culture instead of a results
feed. A Tour report can contain a conventional `RACE BIBLE` and a parallel
`MANUAL FOR SPEED BIBLE`, plus a cast, objectives, highs and lows, observations,
meal report, corrections, quote of the day, playlist, and chronological diary.
Those departments create continuity without forcing every item into a generic
article template.

## Layout and UI patterns worth translating

### 1. Photograph or graphic as the front door

The early homepage lets one documentary image carry a story card. The later
homepage turns each story into a full-bleed visual poster with only the minimum
metadata needed to enter it.

**Gravel Weekly translation:** keep the automatic story graphic as the issue's
front door. Follow it with compact, rights-safe culture artifacts and verified
source-video facades. Never use synthetic documentary imagery or hotlinked
publisher media.

### 2. Extreme hierarchy, quiet metadata

The headline is enormous; date, place, category, and production notes are tiny.
This makes the editorial judgment unmistakable without losing the archival
record.

**Gravel Weekly translation:** make the point or headline the largest element.
Keep receipt count, dates, confidence, and source mechanics in the data face.
Do not let review controls or evidence plumbing compete with the story.

### 3. An issue has departments, not a pile of cards

The Tour report's Roman-numeral contents turn a long scroll into an issue with a
rhythm. Repeated departments reward return readers and allow strange material to
belong without pretending it is hard news.

**Gravel Weekly translation:** use a compact contents rail and a fixed family of
departments. The data may leave a department empty; the renderer must never pad
an issue with weak material.

Recommended public departments:

- `THE CURRENT THING` — the one change-point that explains the week.
- `THE RECORD` — verified facts, results, dates, and race intelligence.
- `THE SCENE REPORT` — approved culture artifacts and the lived texture around
  the story.
- `THE CAST` — only people materially involved in the story, with sourced roles.
- `WHAT EVERYONE IS SLAGGING` — recurring jokes or criticism, labeled as sampled
  attention rather than consensus.
- `FIELD NOTES` — specific details that make the scene legible.
- `THE TAKE` — Matti's approved judgment.
- `WHAT THIS CHANGES` — controlled implications for race profiles and earlier
  Gravel Weekly judgments.
- `CORRECTIONS / THINGS WE GOT WRONG` — a permanent memory mechanism.

### 4. Cast creates a scene

Manual for Speed credits photographers, producers, logistics people, and odd
roles as a cast rather than treating the author as a disembodied narrator.

**Gravel Weekly translation:** generate a cast strip from approved entities in
the evidence graph. Each entry needs a sourced role and relationship to the
story. No inferred motives, personality labels, or synthetic portraits.

### 5. Structured chaos

The pages permit abrupt shifts between facts, jokes, photographs, logistics,
quoted speech, and self-correction. The structure is strict enough that the
content can be loose.

**Gravel Weekly translation:** the schema remains rigid while the issue cadence
can vary. A short oddity can be one field note; it does not need a fake thesis.
A strong story can expand into multiple chapters. A dead week can remain short.

### 6. A visual sequence can be the argument

The photo essays do not treat imagery as decoration between paragraphs. The
sequence itself supplies pacing, character, and evidence of atmosphere.

**Gravel Weekly translation:** use a sequence of locally rendered culture cards,
timestamped source-video facades, and deterministic story graphics. Each item
must have an editorial job: establish the cast, reveal the turn, show recurrence,
or provide comic release. Remove any item that only makes the page longer.

### 7. Specific language beats category language

The archive's strongest headlines and departments are concrete and sometimes
strange. The taxonomy sounds like a publication made by people inside a scene,
not a CMS navigation menu.

**Gravel Weekly translation:** retain stable machine-readable story kinds, but
let the visible department label be specific. `Culture artifact` is a schema
term, not a reader-facing headline.

## Proposed issue anatomy

```text
MASTHEAD / ISSUE DATE / ONE-SENTENCE POINT
STORY GRAPHIC OR VERIFIED SOURCE VIDEO

CONTENTS
I.   THE CURRENT THING
II.  THE RECORD
III. THE SCENE REPORT
IV.  THE CAST
V.   WHAT EVERYONE IS SLAGGING
VI.  THE TAKE
VII. WHAT THIS CHANGES
VIII.CORRECTIONS / MEMORY

SEASON TIMELINE
Each change-point opens the same record/culture/take structure.
```

On mobile, contents is a horizontally scrollable chapter rail. On desktop it may
be sticky only while the issue is in view. Every chapter remains a normal anchor
target; the page works without JavaScript.

### Implemented first pass

The public issue renderer and private historical review desk now generate the
chapter rail from available data. `THE SCENE REPORT` appears only when culture
artifacts survived review; `WHAT THIS CHANGES` enters the public contents only
for a non-`no_change` race impact; draft Takes are labeled as model drafts rather
than approved judgments. The public and historical surfaces now distinguish
`THE RECORD`, `THE SCENE REPORT`, `THE TAKE`, and `WHAT THIS CHANGES` with stable
anchor targets and keyboard-visible focus states.

`THE CAST` and `FIELD NOTES` are also data-aware. They accept only reviewed
items carrying one or more story-receipt claim IDs, preserve those items through
approval, and render numbered source links. The upstream reaction-packet contract
must return empty arrays rather than infer a role, motive, personality,
atmosphere, or colorful detail from a headline, culture post, or publisher
byline.

## What not to import

- No copied masthead, wordmark, gradients, iconography, or condensed-type lockup.
- No copied department names such as `MFS Bible` or `Bonus Treasures`.
- No unlicensed photography, screenshots of social posts, or third-party embeds.
- No small body copy simply because the headline is large.
- No endless undifferentiated scroll; long issues require navigation and a clear
  return to the Current Thing.
- No sponsor placement that can be mistaken for editorial judgment.
- No maximalism without a point. Novelty must carry character, evidence, pacing,
  or an actual joke.

## Acceptance gate for the Gravel Weekly translation

The translated design passes only if:

1. The reader can state the issue's point after the hero and first screen.
2. The official record and cultural record are visibly distinct.
3. Every visual has an editorial job and rights-safe provenance.
4. Repeated departments improve navigation without creating filler quotas.
5. The Scene Report communicates a culture, not an engagement leaderboard.
6. The Take is visibly Matti-approved and cannot be mistaken for model output.
7. The season timeline preserves what was knowable then and what changed later.
8. The result still looks unmistakably like Gravel God.
