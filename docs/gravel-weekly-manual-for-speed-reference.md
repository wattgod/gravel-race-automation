# Manual for Speed reference study

This is an interface and editorial-mechanics study for Gravel Weekly. It is not
permission to copy Manual for Speed's logo, type treatment, photography,
illustration, gradients, page composition, recurring names, or trade dress.

## Archive sample

The review used ten representative Internet Archive captures:

- [February 2012 homepage](https://web.archive.org/web/20120228222408if_/http://www.manualforspeed.com/)
- [December 2012 homepage](https://web.archive.org/web/20121218044342/http://manualforspeed.com/)
- [2012 photo essay: Nice Work. Disappointment.](https://web.archive.org/web/20121101234132/http://manualforspeed.com/2012/09/nice-work-disappointment/)
- [December 2014 homepage](https://web.archive.org/web/20141204191607if_/http://www.manualforspeed.com/)
- [2014 field guide: At the Races, Chapter 1](https://web.archive.org/web/20140607065638/http://www.manualforspeed.com/pro-tour/at-the-races-chapter-1)
- [2014 brief: Hair Care](https://web.archive.org/web/20141205153449if_/http://www.manualforspeed.com/briefs/mfsm-003-bonus-tip-hair-care/)
- [March 2016 homepage](https://web.archive.org/web/20160306025636/http://manualforspeed.com/)
- [2015 Tour de France: Stage 01](https://web.archive.org/web/20160323053644/http://manualforspeed.com/road-racing/2015-tour-de-france-stage-01/)
- [Clown Dreams Lookbook](https://web.archive.org/web/20160323030820/http://manualforspeed.com/bonus-treasures/clown-dreams-lookbook/)
- [November 2021 homepage](https://web.archive.org/web/20211129175253if_/https://manualforspeed.com/)

The 2012 and 2016 systems are materially different. The early site is a quiet,
photo-led index of essays with short, pointed headlines. By 2016 it has become a
maximal magazine: full-bleed story cards, huge condensed display type, issue-like
tables of contents, recurring departments, character credits, and deliberately
over-specific field notes. The durable lesson is the editorial structure, not
either skin.

On August 29, 2026, the Internet Archive captures were intermittently available:
the document structure and copy loaded, but several captured stylesheets and
images did not. The 2014 and 2015 interface structure was therefore independently
cross-checked against the preserved Common Crawl HTML, while the surviving 2021
site and the
[1000% Studio retrospective](https://thousandpercent.studio/work/manual-for-speed/)
provided the reliable visual reference. This recovered document structure and
original asset references, not permission to reuse the assets.

## Three useful interface eras

### 2012: documentary index

The early homepage is a centered publication sheet on a neutral field. A short
manifesto, one large documentary image, and a three-column archive establish the
whole product. Headline decks sit directly on images or in consistent gray
panels. The UI is plain enough that the photography and the specificity of titles
do nearly all the cultural work.

**Useful mechanic:** one dominant scene-setter followed by an honest, regular
index. Gravel Weekly should keep this calm archival mode for historical year
pages, where orientation and retrieval matter more than novelty.

### 2014: magazine front, brief as object

The 2014 homepage uses a centered feature carousel with partial neighboring
images visible at both edges. That small piece of lateral disclosure makes the
publication feel like a sequence rather than a feed. Beneath it, three `Recent
Briefs` cards change scale and tone: a person, an odd detail, and a deliberately
over-specific joke can share the same front page without pretending to be equal
news events.

The `Hair Care` brief is especially instructive. Its page has a compact title and
place, a single oversized visual premise, a metadata strap (`DATE`, `TIME`,
`SUBJECT`), and then the joke played completely straight in editorial typography.
Persistent previous/next controls treat the brief as one artifact in a serial
collection.

**Useful mechanic:** Gravel Weekly culture cards should open as durable artifacts
with a clear premise, source/date/context strap, and adjacent navigation. The
homepage may preview the next and previous season moments, but it must not become
an autoplay carousel or hide the current issue behind gesture-only controls.

### 2015: one publication, several story shapes

The November 2015 homepage is the clearest bridge between the restrained archive
and the later spectacle. A deliberately obsolete scrolling announcement sits
above a deep publication menu organized into `RACE REPORTS`, `PROJECTS`, and
`FEATURES`. The page then alternates among three strong modules instead of forcing
every item into one card grid:

- a split-screen feature with one documentary image, series/date context, a huge
  stage title, small `Location` metadata, and a first-person pull quote;
- a full-viewport image story with the title centered over the scene and two
  compact fact cells for location and date;
- an image-only interstitial that lets a Manual or visual project change the
  rhythm without pretending to be another race report.

Each large feature is followed by a horizontal `MORE FROM THIS SERIES` rail. Its
cards carry an image, title, date, and place, so a reader can move laterally across
one event while the page itself continues chronologically. The homepage lockup
also used an animated gradient, but the useful lesson is not the GIF: one stable
publication shell can support several recurring story shapes and make series
membership visible at the moment of reading.

**Useful mechanic:** Gravel Weekly should choose among a small deterministic set
of issue modules based on the approved material: full visual thesis, split
record/take, compact culture artifact, or quiet issue. A Current Thing should
immediately expose adjacent moments from the same race, conflict, or season arc.
The module choice must follow the story's editorial job; it cannot be random art
direction or a pretext to fill an empty department.

### 2021: archive as spectacle

The final-era homepage drops the conventional publication chrome. A repeating
marquee masthead, full-viewport color field, oversized thesis, large mission
statement, and deliberately misaligned image/caption tiles make the archive feel
like an event. Typography changes register—sans, italic, monospace-like labels—
while color blocks act as caption hardware rather than decoration.

**Useful mechanic:** an issue may have its own controlled art direction while the
underlying data, accessibility, and navigation contracts remain fixed. Gravel
Weekly can vary composition, crop grammar, accent color, and motion by story
shape; it should not randomly mutate the masthead, reading order, evidence model,
or approval state.

## UX decisions for Gravel Weekly

| Manual for Speed mechanic | What it accomplishes | Gravel Weekly translation | Guardrail |
| --- | --- | --- | --- |
| One huge documentary frame | Declares what deserves attention | One explanatory story graphic or verified source-video facade | No synthetic documentary image; no visual without an editorial job |
| Neighboring cards peeking into frame | Makes the issue feel serial | Previous/next season moments visible beside the active change-point | Normal links and anchors remain available; no carousel-only navigation |
| Small metadata strap | Makes an odd artifact legible and retrievable | Source, date, place, story role, and verification status beneath culture artifacts | Evidence mechanics stay subordinate to the point |
| Recurring briefs and typologies | Builds shared lore from small observations | `FIELD NOTES`, `THE CAST`, and approved recurring scene patterns | A recurrence needs multiple reviewed examples; no filler quota |
| Full, split, and interstitial story modules | Gives unlike material distinct pace without losing publication identity | Deterministically choose a visual-thesis, record/take, culture-artifact, or quiet module from approved content | Module choice follows the editorial job; never randomize layout to manufacture novelty |
| `More from this series` rail | Makes one event legible as an evolving sequence | Show adjacent moments from the same race, conflict, or season arc | Normal chronological links remain; no engagement-ranked recommendations |
| Abrupt shifts in scale and type | Creates comic timing and surprise | One visual punch line or register shift per chapter | Body copy remains readable; hierarchy cannot obscure meaning |
| Issue-specific art direction | Keeps a long-running archive alive | Choose composition from the verified story grammar and seeded brand system | Same input remains deterministic; reduced-motion and contrast always pass |
| Persistent lateral navigation | Encourages archive wandering | Previous/next issue and previous/next season change-point | The current item and chronological position are announced in text |

The synthesis is a stable publication shell with variable art direction. The
reader should always know where they are, what the point is, what is evidence,
and what is Matti's approved take—even when the page is allowed to misbehave
visually.

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

### The killer pattern: report the scene as if it deserves a field guide

`At the Races: Chapter 1` turns spectators into a comic but remarkably precise
taxonomy. It names a recurring character type, supplies subtypes, associates,
habitat, diet, proclivities, and dangers, then serializes the idea across ten
weekly installments. The straight-faced structure is what makes the joke work:
the observation is specific enough to be recognizable, the invented bureaucracy
creates comic escalation, and the recurring format turns an otherwise disposable
detail into shared lore.

This is a better model for Gravel Weekly's cultural layer than a generic social
post roundup. The system should look for a repeated, recognizable gravel-world
behavior or character and prepare a possible field-guide treatment only when the
sample supports it. Candidate fields may include `TYPE`, `HABITAT`, `NATURAL
PREDATOR`, `STANDARD DEFENSE`, `EQUIPMENT TELLS`, and `WHERE SIGHTED`, but the
visible labels must be written for the particular joke rather than emitted as
mandatory furniture. One observation is a field note. Multiple independent,
reviewed observations may earn a named type. Neither engagement nor model
confidence can manufacture recurrence.

The visual lesson is equally specific. A bold, deliberately simple illustration
functions as the chapter's front door; the prose and taxonomy carry the factual
and comic precision. Gravel Weekly can translate that division of labor with its
deterministic story graphics: one oversized visual premise, followed by the
evidence-bound labels and Matti's approved take. It should not copy MFS's drawing
style, character names, heavy black frame, typography, or page composition.

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

The public historical timeline also groups approved change-points into year
chapters with a keyboard-accessible jump rail and explicit return links. That
keeps the backfilled record browsable as it grows without turning the page into
an undifferentiated archive scroll.

The live Current Thing now receives a distinct, hash-bound story poster rather
than the generic category motif used by secondary stories. It uses the approved
headline as the visual premise, preserves the Gravel God token and type system,
and identifies itself as abstract automatic editorial art. This is the concrete
translation of Manual for Speed's story-as-front-door mechanic; none of its
trade dress, source photography, illustration style, or title treatment is
copied.

Dated issue pages now expose the adjacent older and newer issues immediately
below the masthead. The rail names the chronological position, previews each
neighbor's actual Current Thing or quiet-week premise, and uses ordinary
`rel="prev"` / `rel="next"` links. This translates the archive's lateral
disclosure without a carousel, autoplay, gesture dependency, or invented teaser.

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

## The quiet-week rule

Weekly cadence is a deadline, not a story quota. If nothing clears the party,
point, friend, story, comedy, and prose gates, Gravel Weekly publishes only
after Matti approves an exact short quiet-week note. The issue carries no
Current Thing, story, or empty department furniture. The note and its edit
summary are hash-bound in the issue and decision receipt, so the system cannot
silently convert a weak candidate into filler.
