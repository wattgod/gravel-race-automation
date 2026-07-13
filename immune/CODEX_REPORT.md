# Codex Report — Immune Data Fixes

## Task 1 — Score-math corrections

The corrected values use `round((sum of 14 criteria + cultural_impact) / 70 * 100)` with `cultural_impact = 0`. `scripts/recalculate_tiers.py --dry-run` was run offline after the score corrections; it identified only GFNY Miami as crossing a tier boundary. Its T3→T4 change was then applied consistently to the rating's tier fields.

| race | old score | new score | tier change (if any) |
|---|---:|---:|---|
| bowral-classic | 57 | 54 | None (T3) |
| etape-caledonia | 56 | 54 | None (T3) |
| gfny-cozumel | 54 | 51 | None (T3) |
| gfny-miami | 46 | 44 | T3 → T4 |
| letape-thailand | 54 | 51 | None (T3) |
| noosa-classic | 50 | 49 | None (T3) |
| ride-across-wisconsin | 51 | 49 | None (T3) |
| tour-de-palm-springs | 54 | 50 | None (T3) |
| tour-de-pologne-amatorow | 53 | 51 | None (T3) |
| tour-of-the-battenkill-road | 53 | 51 | None (T3) |

The nearby `score_note` and score-bearing `tier_note` text was corrected where it still described a nonzero cultural-impact bonus or the superseded score. No scoring criteria were changed.

## Task 2 — Duplicate analysis (proposal only)

This analysis used the local JSON fields (name, website/citations, location, date, and profile completeness) plus general event knowledge. No files were deleted or merged, and no network lookup was performed.

| pair | same event? | keep | remove | reason |
|---|---|---|---|---|
| big-horn-gravel / bighorn-gravel | SAME | `bighorn-gravel` | `big-horn-gravel` | Both describe the June 20 Gypsum event; `bighorn-gravel` uses the standard one-word event spelling and has the more filled-out profile. |
| dreilaendergiro / dreilander-giro | SAME | `dreilander-giro` | `dreilaendergiro` | Same Nauders event and date; `dreilander-giro` is substantially fuller, has five citations including the official site, and preserves “Dreiländergiro” as its display name. |
| el-tour-de-tucson / tour-de-tucson | SAME | `el-tour-de-tucson` | `tour-de-tucson` | Same Tucson route and date; “El Tour de Tucson” is the official name, and that profile has ten citations and far more complete data. |
| gran-fondo-felice-gimondi / granfondo-felice-gimondi | SAME | `granfondo-felice-gimondi` | `gran-fondo-felice-gimondi` | Same Bergamo event and date; the kept profile reflects the current BGY Airport Granfondo name and has six citations plus much richer fields. |
| gran-fondo-guadeloupe / granfondo-la-guadeloupe | SAME | `granfondo-la-guadeloupe` | `gran-fondo-guadeloupe` | Location, date, distance, and climbing align; the kept slug matches the event branding and includes six citations, including the event and UCI sites. |
| gran-fondo-novi-sad / granfondo-novi-sad | SAME | `granfondo-novi-sad` | `gran-fondo-novi-sad` | Same Novi Sad date and near-identical course vitals; the kept profile has more filled fields, precise metric conversions, route options, and rider-video material. |
| gran-fondo-via-del-sale / granfondo-via-del-sale | SAME | `granfondo-via-del-sale` | `gran-fondo-via-del-sale` | Same Cervia event and date; the kept profile is substantially fuller and has seven citations led by the official site and official history. |
| gran-fondo-vosges / granfondo-vosges | SAME | `granfondo-vosges` | `gran-fondo-vosges` | Both identify the La Bresse event; the kept profile follows the event/site's “Granfondo Vosges” spelling, links the official website, and has more filled fields. |
| granfondo-strade-bianche / strade-bianche-gran-fondo | SAME | `strade-bianche-gran-fondo` | `granfondo-strade-bianche` | Same Siena event, date, distance, and elevation; the kept profile is larger and carries 20 citations plus the official event site. |
| istria-gran-fondo / istria-granfondo | SAME | `istria-granfondo` | `istria-gran-fondo` | Same Umag event and date; the kept profile uses the event's “Istria Granfondo” styling and has three citations, an official link, and much richer data. |
| letape-brazil / letape-dubai | DIFFERENT | — | — | Separate L'Étape Series events in Brazil and Dubai with different locations, dates, routes, and official sites. |
| letape-poland / letape-thailand | DIFFERENT | — | — | Separate country editions in Poland and Thailand; shared Tour de France franchise branding does not make them duplicates. |
| letape-slovakia / letape-slovenia | DIFFERENT | — | — | Slovakia (Bratislava) and Slovenia (Kranj) are distinct national editions with different dates and routes. |
| letape-taiwan / letape-thailand | DIFFERENT | — | — | Taiwan's Sun Moon Lake event and Thailand's rotating-host event are separate country editions. |
| oetztaler-radmarathon / otztaler-radmarathon | SAME | `otztaler-radmarathon` | `oetztaler-radmarathon` | Same Sölden event, date, climbing, and near-identical distance; the kept profile is much fuller and has three citations including the official site. Preserve “Ötztaler Radmarathon” as the display spelling when merging. |
| tor-divide / tour-divide | DIFFERENT | — | — | Tor Divide is a roughly 60-mile Peak District event; Tour Divide is the roughly 2,745-mile Banff-to-New Mexico bikepacking race. |
